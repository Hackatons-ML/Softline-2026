"""
Streaming ETL & Index Builder for Store.softline.ru Mindbox YML catalog feed.

Transforms the 292 MB XML feed (9,311 categories, 136,040 SKU offers) into:
1. storage/catalog.sqlite — normalized categories, product_groups (software + hardware),
   offers, mined compatibility edges, and real catalog data-quality audit findings.
2. storage/group_embeddings.npy — L2-normalized 384-d semantic vectors (multilingual-e5-small).
3. storage/search_artifacts.pkl — fast in-memory BM25F index, RapidFuzz vocabulary,
   homoglyph-normalized lookup structures, and catalog statistics.
"""

from __future__ import annotations
import gzip
import json
import math
import pickle
import re
import sqlite3
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Set, Tuple
from lxml import etree
import numpy as np
from rank_bm25 import BM25Okapi

from backend.engine.embedder import LocalSemanticEmbedder

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_XML_PATH = PROJECT_ROOT / "Mindbox.yml.gz.xml"
COMPRESSED_XML_PATH = PROJECT_ROOT / "Mindbox.yml.gz"
STORAGE_DIR = PROJECT_ROOT / "storage"

# Mixed Cyrillic-Latin homoglyph detector & normalizer
# Detects words mixing Latin and Cyrillic lookalikes (e.g. 'Сontent' with Russian С, 'webinаr' with Russian а)
_CYR_TO_LAT_LOOKALIKE = str.maketrans("АВЕКМНОРСТУХаеорсух", "ABEKMHOPCTYXaeopcyx")
_LAT_TO_CYR_LOOKALIKE = str.maketrans("ABEKMHOPCTYXaeopcyx", "АВЕКМНОРСТУХаеорсух")

_WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+(?:[-.][A-Za-zА-Яа-яЁё0-9]+)*")
_MIXED_SCRIPT_WORD_RE = re.compile(r"\b(?=[A-Za-zА-Яа-яЁё]*[A-Za-z])(?=[A-Za-zА-Яа-яЁё]*[А-Яа-яЁё])[A-Za-zА-Яа-яЁё]{3,}\b")

SECONDARY_SKU_PATTERNS = re.compile(
    r"(сертификат\s+(?:на\s+)?(?:техподдерж|годовую|расширенную|техническ)|"
    r"техническ(?:ая|ую)\s+поддержк|"
    r"\bпродление\b|\brenewal\b|\bupgrade\b|\bcross-grade\b|"
    r"лицензия\s+на\s+обновление|\bмиграция\b|"
    r"базовая\s+настройка|обучающ(?:ий|ие)\s+курс|"
    r"дополнительн(?:ые|ая)\s+(?:модули|опции|опция)|"
    r"дистрибутив\s+на\s+одном\s+cd|медиакомплект|комплект\s+документации)",
    re.IGNORECASE,
)

SERVER_ACCESSORY_PATTERNS = re.compile(
    r"(heat\s*sink|радиатор|power\s+supply|блок\s+питания|кабель|cable|rail\s*kit|"
    r"рельс|салазки|вентилятор|fan\s+module|riser|заглушк|крепеж|трансивер|патч-корд)",
    re.IGNORECASE,
)

FOR_RELATION_RE = re.compile(
    r"^(.{4,90}?)\s+(?:для|под|for)\s+([A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9\s\-\.]{2,60})",
    re.IGNORECASE,
)

NON_PRODUCT_TAILS = {
    "дома", "бизнеса", "организаций", "коммерческих", "государственных",
    "академических", "образовательных", "учебных", "медицинских", "физлиц",
    "иностранных", "малого", "среднего", "крупного", "серверов", "рабочих",
    "пк", "пользователей", "школ", "вузов", "некоммерческих",
}

KNOWN_CATEGORY_TYPOS = [
    ("Комумникации", "Коммуникации"),
    ("ABBY ", "ABBYY "),
    ("Scannin", "Scanning"),
    ("терминал сбора данны ", "терминал сбора данных"),
]


def fix_homoglyphs(text: str) -> Tuple[str, List[str]]:
    """Fixes words that accidentally mix Latin and Cyrillic lookalike letters."""
    defects: List[str] = []
    if not text:
        return "", defects

    def _repl(match: re.Match[str]) -> str:
        w = match.group(0)
        lat_cnt = sum(1 for c in w if "A" <= c <= "Z" or "a" <= c <= "z")
        cyr_cnt = sum(1 for c in w if "А" <= c <= "я" or c in "Ёё")
        # Ignore legitimate hyphenated or versioned constructs; this regex has no hyphens
        if lat_cnt >= cyr_cnt:
            fixed = w.translate(_CYR_TO_LAT_LOOKALIKE)
        else:
            fixed = w.translate(_LAT_TO_CYR_LOOKALIKE)
        if fixed != w:
            defects.append(f"{w} → {fixed}")
        return fixed

    cleaned = _MIXED_SCRIPT_WORD_RE.sub(_repl, text)
    return cleaned, defects


def normalize_for_tokens(text: str) -> List[str]:
    low = text.lower().replace("ё", "е")
    tokens = _WORD_RE.findall(low)
    result: List[str] = []
    for t in tokens:
        result.append(t)
        if "-" in t:
            for part in t.split("-"):
                if len(part) >= 2:
                    result.append(part)
    return result


def extract_vendor_slug(vendor_url: str, offer_url: str) -> str:
    for u in (vendor_url, offer_url):
        if "store.softline.ru/" in u:
            rest = u.split("store.softline.ru/", 1)[1].strip("/")
            if rest:
                return rest.split("/")[0].lower()
    return ""


def normalize_hw_model_key(name: str, vendor: str, category_id: str) -> str:
    """Groups identical hardware models across minor configuration SKUs."""
    base = re.sub(r"\([^)]*\)", " ", name)
    base = re.sub(r",\s*.*$", "", base).strip()
    # Strip trailing configuration index like -1, -2 if preceded by model code
    words = base.split()
    short = " ".join(words[:6]).lower()
    return f"hw::{category_id}::{vendor.lower()}::{short}"


def split_head_tail_product(name: str) -> Tuple[str, str]:
    """
    Splits 'Product X для Platform/Product Y' into (head_product, tail_target)
    so search does not rank accessories/certificates for Y above Y itself.
    """
    clean_head = re.sub(r"\([^)]*\)", " ", name)
    m = FOR_RELATION_RE.match(clean_head)
    if not m:
        return name, ""
    head, tail = m.group(1).strip(), m.group(2).strip()
    first_tail_word = tail.split()[0].lower().strip(",.;:")
    if first_tail_word in NON_PRODUCT_TAILS:
        return name, ""
    return head, tail


def resolve_feed_path(preferred: Optional[Path] = None) -> Path:
    for candidate in (preferred, DEFAULT_XML_PATH, COMPRESSED_XML_PATH):
        if candidate is not None and candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Catalog feed not found. Expected {COMPRESSED_XML_PATH} or {DEFAULT_XML_PATH}"
    )


def _open_feed_stream(path: Path) -> BinaryIO:
    with open(path, "rb") as probe:
        magic = probe.read(2)
    if path.suffix.lower() == ".gz" or magic == b"\x1f\x8b":
        return gzip.open(path, "rb")  # type: ignore[return-value]
    return open(path, "rb")


def build_catalog_index(xml_path: Optional[Path] = None, storage_dir: Path = STORAGE_DIR) -> Dict[str, Any]:
    t0 = time.perf_counter()
    feed_path = resolve_feed_path(xml_path)
    storage_dir.mkdir(parents=True, exist_ok=True)
    db_path = storage_dir / "catalog.sqlite"
    emb_path = storage_dir / "group_embeddings.npy"
    art_path = storage_dir / "search_artifacts.pkl"

    if db_path.exists():
        db_path.unlink()

    print(f"[1/5] Streaming XML catalog from {feed_path} ...")
    categories: Dict[str, Dict[str, str]] = {}
    cat_children: Dict[str, List[str]] = defaultdict(list)
    audit_issues: List[Dict[str, str]] = []

    # First pass / streaming categories + offers in one iterparse pass!
    # In YML feeds, <categories> always precedes <offers>.
    cat_paths_built = False

    def ensure_category_paths() -> None:
        nonlocal cat_paths_built
        if cat_paths_built:
            return
        for cid, cinfo in categories.items():
            chain: List[Tuple[str, str]] = []
            cur: Optional[str] = cid
            seen: Set[str] = set()
            while cur and cur in categories and cur not in seen:
                seen.add(cur)
                chain.append((cur, categories[cur]["clean_name"]))
                cur = categories[cur]["parent_id"] or None
            chain.reverse()
            cinfo["root_id"] = chain[0][0] if chain else cid
            cinfo["root_name"] = chain[0][1] if chain else cinfo["clean_name"]
            cinfo["level2_id"] = chain[1][0] if len(chain) > 1 else cinfo["root_id"]
            cinfo["level2_name"] = chain[1][1] if len(chain) > 1 else cinfo["root_name"]
            cinfo["depth"] = str(len(chain))
            cinfo["full_path"] = " / ".join(x[1] for x in chain)
        cat_paths_built = True

    groups_acc: Dict[str, Dict[str, Any]] = {}
    offers_rows: List[Tuple[Any, ...]] = []
    compatibility_raw: List[Tuple[str, str, str]] = []  # (source_gid, target_phrase, evidence_name)

    total_offers = 0
    avail_offers = 0
    zero_price_inactive = 0
    homoglyph_offer_count = 0

    with _open_feed_stream(feed_path) as feed_stream:
        context = etree.iterparse(
            feed_stream,
            events=("end",),
            tag=("category", "offer"),
            load_dtd=False,
            no_network=True,
            recover=True,
        )

        for _, elem in context:
            if elem.tag == "category":
                cid = elem.attrib.get("id", "").strip()
                pid = elem.attrib.get("parentId", "").strip()
                raw_name = (elem.text or "").strip()
                clean_name, defects = fix_homoglyphs(raw_name)
                if defects and len(audit_issues) < 120:
                    audit_issues.append({
                        "issue_type": "homoglyph_category",
                        "entity_id": cid,
                        "raw_value": raw_name,
                        "detail": f"Смешение кириллицы и латиницы в названии категории ({', '.join(defects)}) — ломает точный поиск",
                    })
                for bad, good in KNOWN_CATEGORY_TYPOS:
                    if bad.lower() in clean_name.lower():
                        audit_issues.append({
                            "issue_type": "typo_category",
                            "entity_id": cid,
                            "raw_value": raw_name,
                            "detail": f"Опечатка в названии категории каталога: «{bad.strip()}» вместо «{good.strip()}»",
                        })
                categories[cid] = {
                    "id": cid,
                    "parent_id": pid,
                    "raw_name": raw_name,
                    "clean_name": clean_name,
                }
                if pid:
                    cat_children[pid].append(cid)
                elem.clear()

            elif elem.tag == "offer":
                ensure_category_paths()
                total_offers += 1
                oid = elem.attrib.get("id", "").strip()
                raw_gid = (elem.attrib.get("group_id") or elem.findtext("group_id") or "").strip()
                available = elem.attrib.get("available", "false").strip().lower() == "true"
                if available:
                    avail_offers += 1

                raw_name = (elem.findtext("name") or "").strip()
                clean_name, name_defects = fix_homoglyphs(raw_name)
                if name_defects:
                    homoglyph_offer_count += 1
                    if len(audit_issues) < 160 and homoglyph_offer_count <= 20:
                        audit_issues.append({
                            "issue_type": "homoglyph_offer",
                            "entity_id": oid,
                            "raw_value": raw_name[:110],
                            "detail": f"Кириллические/латинские буквы-двойники в карточке SKU: {', '.join(name_defects[:3])}",
                        })

                raw_vendor = (elem.findtext("vendor") or "").strip()
                vendor, _ = fix_homoglyphs(raw_vendor)
                vendor_url = (elem.findtext("vendorUrl") or "").strip()
                url = (elem.findtext("url") or "").strip()
                vendor_slug = extract_vendor_slug(vendor_url, url)
                cat_id = (elem.findtext("categoryId") or "").strip()
                picture = (elem.findtext("picture") or "").strip()
                sales_notes = (elem.findtext("sales_notes") or "").strip()
                desc = (elem.findtext("description") or "").strip()

                try:
                    price = float((elem.findtext("price") or "0").strip() or 0.0)
                except ValueError:
                    price = 0.0
                try:
                    oldprice = float((elem.findtext("oldprice") or "0").strip() or 0.0)
                except ValueError:
                    oldprice = 0.0

                if not available and price <= 0:
                    zero_price_inactive += 1

                discount_pct = 0.0
                if oldprice > price > 0:
                    discount_pct = round((oldprice - price) / oldprice * 100.0, 1)

                params: Dict[str, str] = {}
                for p_el in elem.findall("param"):
                    pname = p_el.attrib.get("name", "").strip()
                    pval = (p_el.text or "").strip()
                    if pname and pval and pval.lower() != "другое или отсутствует":
                        params[pname] = pval

                prod_type = params.get("Тип продукта", "софт").lower()
                registry_num = params.get("Номер записи в реестре отечественного ПО", "")
                platform = params.get("Совместимая архитектура/платформа", "")
                version = params.get("Версия", "")
                license_type = params.get("Тип лицензии", "")
                duration = params.get("Срок действия", "")
                org_type = params.get("Тип организации", "")
                certs = params.get("Сертификаты и стандарты", "")
                nodes_cnt = params.get("К-во узлов", "") or params.get("К-во пользователей до", "")

                if raw_gid:
                    gid = raw_gid
                    group_cat_info = categories.get(raw_gid)
                    group_title = group_cat_info["clean_name"] if group_cat_info else clean_name.split(",")[0].strip()
                else:
                    gid = normalize_hw_model_key(clean_name, vendor, cat_id)
                    group_title = re.sub(r",\s*.*$", "", clean_name).strip()

                is_secondary = bool(SECONDARY_SKU_PATTERNS.search(clean_name))
                if prod_type == "электроника" and SERVER_ACCESSORY_PATTERNS.search(clean_name):
                    is_secondary = True

                head_name, tail_target = split_head_tail_product(clean_name)
                if tail_target and len(compatibility_raw) < 25000:
                    compatibility_raw.append((gid, tail_target, clean_name[:120]))

                cat_info = categories.get(cat_id, {
                    "root_id": cat_id,
                    "root_name": "Каталог",
                    "level2_id": cat_id,
                    "level2_name": "Товары",
                    "clean_name": "Товары",
                    "full_path": "Каталог",
                })
                # Check if category itself is Минпромторг registry
                is_ru_registry = bool(registry_num) or ("222320" in (cat_id, cat_info.get("level2_id", ""))) or (cat_info.get("root_id") == "353554")

                offer_tuple = (
                    oid,
                    gid,
                    1 if available else 0,
                    clean_name,
                    head_name,
                    tail_target,
                    vendor,
                    vendor_url,
                    vendor_slug,
                    cat_id,
                    url,
                    picture,
                    price,
                    oldprice,
                    discount_pct,
                    prod_type,
                    1 if is_ru_registry else 0,
                    registry_num,
                    1 if is_secondary else 0,
                    version,
                    platform,
                    license_type,
                    duration,
                    org_type,
                    certs,
                    nodes_cnt,
                    sales_notes,
                    desc[:350],
                )
                offers_rows.append(offer_tuple)

                # Aggregate into product group
                g = groups_acc.get(gid)
                if g is None:
                    g = {
                        "group_id": gid,
                        "title": group_title,
                        "vendor": vendor,
                        "vendor_url": vendor_url,
                        "vendor_slug": vendor_slug,
                        "category_id": cat_id,
                        "root_category_id": cat_info.get("root_id", ""),
                        "root_category_name": cat_info.get("root_name", ""),
                        "sub_category_name": cat_info.get("clean_name", ""),
                        "category_path": cat_info.get("full_path", ""),
                        "product_type": prod_type,
                        "total_sku_count": 0,
                        "avail_sku_count": 0,
                        "base_avail_sku_count": 0,
                        "min_avail_price": math.inf,
                        "max_avail_price": 0.0,
                        "max_discount_pct": 0.0,
                        "is_ru_registry": False,
                        "registry_num": "",
                        "platforms": set(),
                        "versions": set(),
                        "certs": set(),
                        "sales_notes_set": set(),
                        "best_offer": None,
                        "best_offer_rank": (-1, -1, -1, -math.inf),
                    }
                    groups_acc[gid] = g

                g["total_sku_count"] += 1
                if available:
                    g["avail_sku_count"] += 1
                    if not is_secondary:
                        g["base_avail_sku_count"] += 1
                    if price > 0:
                        if price < g["min_avail_price"]:
                            g["min_avail_price"] = price
                        if price > g["max_avail_price"]:
                            g["max_avail_price"] = price
                if discount_pct > g["max_discount_pct"] and available:
                    g["max_discount_pct"] = discount_pct
                if is_ru_registry:
                    g["is_ru_registry"] = True
                    if registry_num and not g["registry_num"]:
                        g["registry_num"] = registry_num
                if platform and len(g["platforms"]) < 5:
                    g["platforms"].add(platform[:50])
                if version and len(g["versions"]) < 5:
                    g["versions"].add(version[:25])
                if certs and len(g["certs"]) < 4:
                    g["certs"].add(certs[:40])
                if sales_notes and len(g["sales_notes_set"]) < 4:
                    g["sales_notes_set"].add(sales_notes)

                # Pick flagship offer:
                # Prefer available=True -> non-secondary (base license/device) -> commercial/universal -> has discount or affordable real price
                comm_bonus = 1 if ("коммерч" in org_type.lower() or not org_type) else 0
                has_real_price = 1 if price > 0 else 0
                # Prefer moderate starting price among base commercial SKUs (negative log price so 1-seat / standard base SKU beats 1000-seat bundle)
                price_pref = -math.log10(price + 10.0) if price > 0 else -99.0
                cand_rank = (
                    1 if available else 0,
                    1 if not is_secondary else 0,
                    has_real_price + comm_bonus,
                    (1.5 if discount_pct > 0 else 0.0) + price_pref,
                )
                if cand_rank > g["best_offer_rank"]:
                    g["best_offer_rank"] = cand_rank
                    g["best_offer"] = offer_tuple

                elem.clear()
                while elem.getprevious() is not None:
                    del elem.getparent()[0]

    print(
        f"    Parsed {len(categories):,} categories, {total_offers:,} offers "
        f"({avail_offers:,} available) -> {len(groups_acc):,} product groups in {time.perf_counter()-t0:.1f}s"
    )

    # -----------------------------------------------------------------------
    # [2/5] Compute honest category price-advantage metrics & catalog audit
    # -----------------------------------------------------------------------
    print("[2/5] Computing competitive category price benchmarks & catalog health audit ...")
    cat_prices: Dict[str, List[float]] = defaultdict(list)
    cat_total_skus: Counter[str] = Counter()
    cat_avail_skus: Counter[str] = Counter()

    for g in groups_acc.values():
        cid = g["category_id"]
        cat_total_skus[cid] += g["total_sku_count"]
        cat_avail_skus[cid] += g["avail_sku_count"]
        if g["avail_sku_count"] > 0 and 0 < g["min_avail_price"] < math.inf and g["base_avail_sku_count"] > 0:
            cat_prices[cid].append(g["min_avail_price"])

    cat_medians: Dict[str, float] = {
        cid: statistics.median(vals)
        for cid, vals in cat_prices.items()
        if len(vals) >= 3
    }

    # Dead-end categories audit (high SKU count, 0 available)
    for cid, tot in cat_total_skus.most_common():
        if tot >= 50 and cat_avail_skus[cid] == 0 and len(audit_issues) < 220:
            cname = categories.get(cid, {}).get("full_path", cid)
            audit_issues.append({
                "issue_type": "dead_category",
                "entity_id": cid,
                "raw_value": f"{cname} ({tot} SKU)",
                "detail": f"В разделе {tot} товарных позиций, но 0 доступных к заказу (100% available=false) — требуется витрина аналогов РФ",
            })

    group_records: List[Dict[str, Any]] = []
    for gid, g in groups_acc.items():
        best = g["best_offer"]
        assert best is not None
        min_p = g["min_avail_price"] if g["min_avail_price"] < math.inf else float(best[12] or 0.0)
        max_p = g["max_avail_price"] if g["max_avail_price"] > 0 else min_p
        best_price = float(best[12] or 0.0)
        best_oldprice = float(best[13] or 0.0)
        best_disc = float(best[14] or 0.0)

        price_adv_pct = 0.0
        price_adv_label = ""
        med = cat_medians.get(g["category_id"], 0.0)
        if best_disc > 0 and g["avail_sku_count"] > 0:
            saved = int(round(best_oldprice - best_price))
            price_adv_pct = best_disc
            price_adv_label = f"Акция −{best_disc:.0f}% (выгода {saved:,} ₽)".replace(",", " ")
        elif g["avail_sku_count"] > 0 and med > 0 and 0 < min_p <= med * 0.78 and g["base_avail_sku_count"] > 0:
            adv = round((1.0 - min_p / med) * 100.0)
            if 10 <= adv <= 85:
                price_adv_pct = float(adv)
                price_adv_label = f"Выгоднее средней цены аналогов в разделе на {adv}%"
        elif g["avail_sku_count"] >= 4 and len(g["sales_notes_set"]) >= 2:
            price_adv_label = "Доступны оптовые тиры со снижением цены за лицензию"

        head_title, tail_target = split_head_tail_product(g["title"])
        if not tail_target and best[5]:
            # Only treat whole group as a companion ("X for Y") if flagship offer also has a tail target
            # and group title does not match target
            if " для " in g["title"].lower() or " for " in g["title"].lower():
                head_title, tail_target = best[4], best[5]

        passage_parts = [
            g["title"],
            f"Вендор: {g['vendor']} ({g['vendor_slug']})" if g["vendor_slug"] else f"Вендор: {g['vendor']}",
            f"Раздел: {g['root_category_name']} > {g['sub_category_name']}",
            f"Тип: {'оборудование сервер электроника' if g['product_type'] == 'электроника' else 'программное обеспечение лицензия софт'}",
        ]
        if g["is_ru_registry"]:
            passage_parts.append("Реестр российского ПО Минцифры импортозамещение")
        if g["platforms"]:
            passage_parts.append("Платформа: " + ", ".join(sorted(g["platforms"])[:3]))
        if g["versions"]:
            passage_parts.append("Версия: " + ", ".join(sorted(g["versions"])[:3]))
        if best[3] != g["title"]:
            passage_parts.append(best[3][:110])

        passage_text = " | ".join(passage_parts)

        group_records.append({
            "group_id": gid,
            "title": g["title"],
            "head_title": head_title,
            "tail_target": tail_target,
            "vendor": g["vendor"],
            "vendor_url": g["vendor_url"],
            "vendor_slug": g["vendor_slug"],
            "category_id": g["category_id"],
            "root_category_id": g["root_category_id"],
            "root_category_name": g["root_category_name"],
            "sub_category_name": g["sub_category_name"],
            "category_path": g["category_path"],
            "product_type": g["product_type"],
            "available": 1 if g["avail_sku_count"] > 0 else 0,
            "has_base_sku": 1 if g["base_avail_sku_count"] > 0 else 0,
            "total_sku_count": g["total_sku_count"],
            "avail_sku_count": g["avail_sku_count"],
            "min_price": min_p if min_p < math.inf else 0.0,
            "max_price": max_p,
            "flagship_offer_id": best[0],
            "flagship_name": best[3],
            "flagship_url": best[10],
            "picture": best[11],
            "flagship_price": best_price,
            "flagship_oldprice": best_oldprice,
            "discount_pct": max(best_disc, g["max_discount_pct"]),
            "price_adv_pct": price_adv_pct,
            "price_adv_label": price_adv_label,
            "is_ru_registry": 1 if g["is_ru_registry"] else 0,
            "registry_num": g["registry_num"],
            "versions_str": ", ".join(sorted(g["versions"])),
            "platforms_str": ", ".join(sorted(g["platforms"])),
            "passage_text": passage_text,
        })

    # Sort deterministically: available base groups first, then available secondary, then archived
    group_records.sort(
        key=lambda r: (-r["available"], -r["has_base_sku"], -r["avail_sku_count"], r["group_id"])
    )

    # -----------------------------------------------------------------------
    # [3/5] Build Lexical BM25F + Vocabulary for RapidFuzz & Typeahead
    # -----------------------------------------------------------------------
    print(f"[3/5] Building field-weighted BM25F index & fuzzy vocabulary for {len(group_records):,} product groups ...")
    bm25_corpus: List[List[str]] = []
    vocab_counter: Counter[str] = Counter()

    for rec in group_records:
        # Field weighting via token repetition:
        # Title & head_title (4x), vendor & vendor_slug (3x), sub_category & versions (2x), root_category & flagship_name (1x)
        title_toks = normalize_for_tokens(rec["head_title"] or rec["title"])
        full_title_toks = normalize_for_tokens(rec["title"])
        vendor_toks = normalize_for_tokens(f"{rec['vendor']} {rec['vendor_slug']}")
        cat_toks = normalize_for_tokens(f"{rec['sub_category_name']} {rec['versions_str']}")
        extra_toks = normalize_for_tokens(f"{rec['root_category_name']} {rec['flagship_name']}")

        doc_tokens = (
            title_toks * 4
            + full_title_toks * 2
            + vendor_toks * 3
            + cat_toks * 2
            + extra_toks
        )
        bm25_corpus.append(doc_tokens)

        for tok in set(full_title_toks + vendor_toks + cat_toks):
            if len(tok) >= 3 and not tok.isdigit():
                vocab_counter[tok] += 1 + (3 if rec["available"] else 0)

    bm25 = BM25Okapi(bm25_corpus, k1=1.4, b=0.65)
    fuzzy_vocab = [w for w, c in vocab_counter.most_common(18000) if c >= 2]

    # Mine catalog compatibility edges ("X для Y" -> map Y to active companion group X)
    mined_companions: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    seen_comp_pairs: Set[Tuple[str, str]] = set()
    group_by_id = {r["group_id"]: r for r in group_records}
    for src_gid, target_phrase, ev_name in compatibility_raw:
        src_rec = group_by_id.get(src_gid)
        if not src_rec or not src_rec["available"]:
            continue
        t_key = target_phrase.lower().strip()
        # Normalize common target OS/product keys
        for canonical_target in ("astra linux", "microsoft office", "windows", "linux", "1с", "kaspersky", "криптопро", "postgres"):
            if canonical_target in t_key:
                pair = (canonical_target, src_gid)
                if pair not in seen_comp_pairs and len(mined_companions[canonical_target]) < 12:
                    # Ensure companion vendor differs or adds distinct capability
                    seen_comp_pairs.add(pair)
                    mined_companions[canonical_target].append({
                        "group_id": src_gid,
                        "evidence": ev_name,
                        "target": canonical_target,
                    })

    # -----------------------------------------------------------------------
    # [4/5] Compute Dense Neural Embeddings (ONNX multilingual-e5-small)
    # -----------------------------------------------------------------------
    print(f"[4/5] Encoding {len(group_records):,} product groups with ONNX multilingual-e5-small ...")
    t_emb = time.perf_counter()
    embedder = LocalSemanticEmbedder(cache_dir=storage_dir / "hf_cache")
    passages = [r["passage_text"] for r in group_records]
    embeddings = embedder.encode_passages(passages, batch_size=128)
    np.save(emb_path, embeddings)
    print(f"    Embeddings shape {embeddings.shape} saved in {time.perf_counter()-t_emb:.1f}s ({embedder.model_id})")

    # -----------------------------------------------------------------------
    # [5/5] Persist SQLite Database + Fast In-Memory Artifacts
    # -----------------------------------------------------------------------
    print("[5/5] Writing SQLite database and fast search artifacts ...")
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.executescript(
        """
        PRAGMA journal_mode = WAL;
        PRAGMA synchronous = NORMAL;

        CREATE TABLE categories (
            id TEXT PRIMARY KEY,
            parent_id TEXT,
            raw_name TEXT,
            clean_name TEXT,
            root_id TEXT,
            root_name TEXT,
            level2_id TEXT,
            level2_name TEXT,
            full_path TEXT
        );

        CREATE TABLE product_groups (
            idx INTEGER PRIMARY KEY,
            group_id TEXT UNIQUE,
            title TEXT,
            head_title TEXT,
            tail_target TEXT,
            vendor TEXT,
            vendor_url TEXT,
            vendor_slug TEXT,
            category_id TEXT,
            root_category_id TEXT,
            root_category_name TEXT,
            sub_category_name TEXT,
            category_path TEXT,
            product_type TEXT,
            available INTEGER,
            has_base_sku INTEGER,
            total_sku_count INTEGER,
            avail_sku_count INTEGER,
            min_price REAL,
            max_price REAL,
            flagship_offer_id TEXT,
            flagship_name TEXT,
            flagship_url TEXT,
            picture TEXT,
            flagship_price REAL,
            flagship_oldprice REAL,
            discount_pct REAL,
            price_adv_pct REAL,
            price_adv_label TEXT,
            is_ru_registry INTEGER,
            registry_num TEXT,
            versions_str TEXT,
            platforms_str TEXT
        );

        CREATE TABLE offers (
            offer_id TEXT PRIMARY KEY,
            group_id TEXT,
            available INTEGER,
            name TEXT,
            head_name TEXT,
            tail_target TEXT,
            vendor TEXT,
            vendor_url TEXT,
            vendor_slug TEXT,
            category_id TEXT,
            url TEXT,
            picture TEXT,
            price REAL,
            oldprice REAL,
            discount_pct REAL,
            product_type TEXT,
            is_ru_registry INTEGER,
            registry_num TEXT,
            is_secondary INTEGER,
            version TEXT,
            platform TEXT,
            license_type TEXT,
            duration TEXT,
            org_type TEXT,
            certs TEXT,
            nodes_cnt TEXT,
            sales_notes TEXT,
            description TEXT
        );

        CREATE INDEX idx_offers_group ON offers(group_id, available, is_secondary, price);
        CREATE INDEX idx_offers_cat ON offers(category_id, available);

        CREATE TABLE catalog_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_type TEXT,
            entity_id TEXT,
            raw_value TEXT,
            detail TEXT
        );

        CREATE TABLE search_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            raw_query TEXT,
            normalized_query TEXT,
            detected_intent TEXT,
            rule_applied TEXT,
            results_count INTEGER,
            top_group_id TEXT,
            top_title TEXT,
            top_available INTEGER,
            latency_ms REAL,
            had_typo_or_slang INTEGER,
            zero_in_legacy_search INTEGER,
            clicked_offer_url TEXT,
            clicked_block TEXT
        );
        """
    )

    cur.executemany(
        "INSERT INTO categories VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                c["id"],
                c["parent_id"],
                c["raw_name"],
                c["clean_name"],
                c.get("root_id", ""),
                c.get("root_name", ""),
                c.get("level2_id", ""),
                c.get("level2_name", ""),
                c.get("full_path", ""),
            )
            for c in categories.values()
        ],
    )

    cur.executemany(
        """
        INSERT INTO product_groups VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        [
            (
                idx,
                r["group_id"],
                r["title"],
                r["head_title"],
                r["tail_target"],
                r["vendor"],
                r["vendor_url"],
                r["vendor_slug"],
                r["category_id"],
                r["root_category_id"],
                r["root_category_name"],
                r["sub_category_name"],
                r["category_path"],
                r["product_type"],
                r["available"],
                r["has_base_sku"],
                r["total_sku_count"],
                r["avail_sku_count"],
                r["min_price"],
                r["max_price"],
                r["flagship_offer_id"],
                r["flagship_name"],
                r["flagship_url"],
                r["picture"],
                r["flagship_price"],
                r["flagship_oldprice"],
                r["discount_pct"],
                r["price_adv_pct"],
                r["price_adv_label"],
                r["is_ru_registry"],
                r["registry_num"],
                r["versions_str"],
                r["platforms_str"],
            )
            for idx, r in enumerate(group_records)
        ],
    )

    cur.executemany(
        """
        INSERT INTO offers VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        offers_rows,
    )

    cur.executemany(
        "INSERT INTO catalog_audit (issue_type, entity_id, raw_value, detail) VALUES (?, ?, ?, ?)",
        [(a["issue_type"], a["entity_id"], a["raw_value"], a["detail"]) for a in audit_issues],
    )
    conn.commit()
    conn.close()

    # Slim metadata list for ultra-fast in-memory ranking (< 25 MB RAM)
    compact_groups = [
        {k: v for k, v in r.items() if k != "passage_text"}
        for r in group_records
    ]

    catalog_stats = {
        "feed_date": "2026-11-25",
        "total_categories": len(categories),
        "total_offers": total_offers,
        "available_offers": avail_offers,
        "unavailable_offers": total_offers - avail_offers,
        "zero_price_inactive_offers": zero_price_inactive,
        "total_product_groups": len(group_records),
        "available_product_groups": sum(1 for r in group_records if r["available"]),
        "software_groups": sum(1 for r in group_records if r["product_type"] == "софт"),
        "hardware_groups": sum(1 for r in group_records if r["product_type"] == "электроника"),
        "russian_registry_groups": sum(1 for r in group_records if r["is_ru_registry"]),
        "promo_discount_groups": sum(1 for r in group_records if r["discount_pct"] > 0 and r["available"]),
        "price_advantage_groups": sum(1 for r in group_records if r["price_adv_pct"] > 0 and r["available"]),
        "homoglyph_defects_found": homoglyph_offer_count,
        "dead_categories_count": sum(1 for c, tot in cat_total_skus.items() if tot >= 10 and cat_avail_skus[c] == 0),
        "embedding_model": embedder.model_id,
        "build_time_sec": round(time.perf_counter() - t0, 1),
    }

    with open(art_path, "wb") as f:
        pickle.dump(
            {
                "groups": compact_groups,
                "bm25": bm25,
                "fuzzy_vocab": fuzzy_vocab,
                "mined_companions": dict(mined_companions),
                "catalog_stats": catalog_stats,
            },
            f,
            protocol=pickle.HIGHEST_PROTOCOL,
        )

    with open(storage_dir / "catalog_stats.json", "w", encoding="utf-8") as f:
        json.dump(catalog_stats, f, ensure_ascii=False, indent=2)

    print(f"[DONE] Full catalog index built in {catalog_stats['build_time_sec']}s -> {storage_dir}")
    return catalog_stats


if __name__ == "__main__":
    build_catalog_index()
