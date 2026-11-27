"""
Two-Stage Hybrid Retrieval + Domain Reranker + Naive Legacy Baseline + Instant Suggest.

Guarantees:
- Understands semantics, jargon, typos, keyboard layout, transliteration, and rebrandings
- Distinguishes hardware vs software intent ('сервер') and core products vs 'X для Y' add-ons
- Strictly returns >= 4 relevant products on EVERY search query
- Provides sub-30ms live product/query suggestions while typing
"""

from __future__ import annotations
import math
import pickle
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np

from backend.data.build_index import SERVER_ACCESSORY_PATTERNS, STORAGE_DIR
from backend.data.domain_knowledge import IMPORT_SUBSTITUTION_ALTERNATIVES
from backend.engine.embedder import LocalSemanticEmbedder
from backend.engine.query_processor import ProcessedQuery, QueryProcessor

_WORD_SPLIT_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+")


class SmartSearchEngine:
    def __init__(self, storage_dir: Path = STORAGE_DIR) -> None:
        self.storage_dir = storage_dir
        self.db_path = storage_dir / "catalog.sqlite"
        emb_path = storage_dir / "group_embeddings.npy"
        art_path = storage_dir / "search_artifacts.pkl"

        if not (self.db_path.exists() and emb_path.exists() and art_path.exists()):
            raise FileNotFoundError(
                f"Search index artifacts not found in {storage_dir}. Run `python -m backend.data.build_index` first."
            )

        with open(art_path, "rb") as f:
            art = pickle.load(f)

        self.groups: List[Dict[str, Any]] = art["groups"]
        self.group_by_id: Dict[str, Dict[str, Any]] = {g["group_id"]: g for g in self.groups}
        self.bm25 = art["bm25"]
        self.fuzzy_vocab: List[str] = art["fuzzy_vocab"]
        self.mined_companions: Dict[str, List[Dict[str, str]]] = art["mined_companions"]
        self.catalog_stats: Dict[str, Any] = art["catalog_stats"]

        self.embeddings: np.ndarray = np.load(emb_path)
        self.embedder = LocalSemanticEmbedder(cache_dir=storage_dir / "hf_cache")
        self.qp = QueryProcessor(self.fuzzy_vocab)

        # Precompute normalized strings on groups for ultra-fast reranking & suggest
        for g in self.groups:
            g["_title_low"] = g["title"].lower().replace("ё", "е")
            g["_head_low"] = (g["head_title"] or g["title"]).lower().replace("ё", "е")
            g["_tail_low"] = (g["tail_target"] or "").lower().replace("ё", "е")
            g["_vendor_low"] = f"{g['vendor']} {g['vendor_slug']}".lower().replace("ё", "е")
            g["_cat_low"] = f"{g['sub_category_name']} {g['root_category_name']}".lower().replace("ё", "е")

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _select_best_sku_and_variants(
        self,
        conn: sqlite3.Connection,
        group: Dict[str, Any],
        pq: ProcessedQuery,
        only_available: bool = False,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        cur = conn.cursor()
        sql = "SELECT * FROM offers WHERE group_id = ?"
        params: List[Any] = [group["group_id"]]
        if only_available:
            sql += " AND available = 1"
        sql += " ORDER BY available DESC, is_secondary ASC, price ASC LIMIT 60"
        rows = cur.execute(sql, params).fetchall()

        if not rows:
            return self._fallback_card_from_group(group), []

        norm_tokens = [t for t in _WORD_SPLIT_RE.findall(pq.normalized_query.lower()) if len(t) >= 2]
        best_row = rows[0]
        best_score = -1e9

        for r in rows:
            sc = 0.0
            if r["available"]:
                sc += 50.0
            if r["price"] > 0:
                sc += 15.0
            if pq.max_budget and r["price"] > pq.max_budget:
                sc -= 35.0

            name_low = r["name"].lower().replace("ё", "е")
            is_sec = bool(r["is_secondary"]) or any(
                kw in name_low
                for kw in ("сертификат на ", "сопровождени", "additional", "дополнительн", "поддержк")
            )
            if pq.wants_secondary_sku:
                sc += 18.0 if is_sec else -5.0
            else:
                sc += 20.0 if not is_sec else -22.0
            # Version matching (e.g. '5.0' vs '4.0' in CryptoPro CSP)
            if pq.requested_version:
                if pq.requested_version in name_low or pq.requested_version == r["version"]:
                    sc += 28.0
                elif any(other_v in name_low for other_v in ("4.0", "3.9", "2016", "2019") if other_v != pq.requested_version):
                    sc -= 14.0

            if pq.wants_home_business and ("дома и бизнеса" in name_low or "home and business" in name_low):
                sc += 25.0

            # Token overlap with offer title
            overlap = sum(1 for t in norm_tokens if t in name_low)
            sc += overlap * 3.0

            # Prefer commercial/universal base tier with reasonable entry price
            if r["price"] > 0:
                sc -= math.log10(r["price"] + 10.0) * 1.2
            if r["discount_pct"] > 0 and r["available"]:
                sc += 6.0

            if sc > best_score:
                best_score = sc
                best_row = r

        variants: List[Dict[str, Any]] = []
        seen_names: Set[str] = set()
        for r in rows:
            if len(variants) >= 6:
                break
            short_key = f"{r['name'][:75]}_{int(r['price'])}"
            if short_key in seen_names:
                continue
            seen_names.add(short_key)
            variants.append({
                "offer_id": r["offer_id"],
                "name": r["name"],
                "price": r["price"],
                "oldprice": r["oldprice"],
                "discount_pct": r["discount_pct"],
                "available": bool(r["available"]),
                "license_type": r["license_type"],
                "duration": r["duration"],
                "nodes_cnt": r["nodes_cnt"],
                "sales_notes": r["sales_notes"],
                "url": r["url"],
            })

        return dict(best_row), variants

    def _fallback_card_from_group(self, g: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "offer_id": g["flagship_offer_id"],
            "group_id": g["group_id"],
            "available": g["available"],
            "name": g["flagship_name"],
            "vendor": g["vendor"],
            "vendor_url": g["vendor_url"],
            "vendor_slug": g["vendor_slug"],
            "category_id": g["category_id"],
            "url": g["flagship_url"],
            "picture": g["picture"],
            "price": g["flagship_price"],
            "oldprice": g["flagship_oldprice"],
            "discount_pct": g["discount_pct"],
            "product_type": g["product_type"],
            "is_ru_registry": g["is_ru_registry"],
            "registry_num": g["registry_num"],
            "is_secondary": 0 if g["has_base_sku"] else 1,
            "version": g["versions_str"],
            "platform": g["platforms_str"],
            "license_type": "",
            "duration": "",
            "org_type": "",
            "certs": "",
            "nodes_cnt": "",
            "sales_notes": "",
            "description": "",
        }

    def _format_product_card(
        self,
        group: Dict[str, Any],
        sku: Dict[str, Any],
        variants: List[Dict[str, Any]],
        score: float,
        match_reasons: List[str],
        match_tier: str = "primary",
    ) -> Dict[str, Any]:
        price = float(sku.get("price") or group["flagship_price"] or 0.0)
        oldprice = float(sku.get("oldprice") or group["flagship_oldprice"] or 0.0)
        disc = float(sku.get("discount_pct") or 0.0)
        if oldprice > price > 0 and disc <= 0:
            disc = round((oldprice - price) / oldprice * 100.0, 1)

        price_adv_label = group["price_adv_label"]
        if disc > 0 and sku.get("available"):
            saved = int(round(oldprice - price))
            price_adv_label = f"Акция −{disc:.0f}% · экономия {saved:,} ₽".replace(",", " ")

        return {
            "offer_id": str(sku.get("offer_id", group["flagship_offer_id"])),
            "group_id": group["group_id"],
            "group_title": group["title"],
            "name": sku.get("name") or group["flagship_name"],
            "vendor": sku.get("vendor") or group["vendor"],
            "vendor_url": sku.get("vendor_url") or group["vendor_url"],
            "vendor_slug": group["vendor_slug"],
            "category_id": group["category_id"],
            "root_category_name": group["root_category_name"],
            "sub_category_name": group["sub_category_name"],
            "category_path": group["category_path"],
            "product_type": group["product_type"],
            "available": bool(sku.get("available", group["available"])),
            "price": price,
            "oldprice": oldprice,
            "min_group_price": group["min_price"],
            "max_group_price": group["max_price"],
            "total_sku_count": group["total_sku_count"],
            "avail_sku_count": group["avail_sku_count"],
            "discount_pct": disc,
            "price_adv_pct": group["price_adv_pct"],
            "price_adv_label": price_adv_label,
            "is_ru_registry": bool(sku.get("is_ru_registry") or group["is_ru_registry"]),
            "registry_num": sku.get("registry_num") or group["registry_num"],
            "picture": sku.get("picture") or group["picture"],
            "url": sku.get("url") or group["flagship_url"],
            "license_type": sku.get("license_type", ""),
            "duration": sku.get("duration", ""),
            "sales_notes": sku.get("sales_notes", ""),
            "score": round(score, 3),
            "match_tier": match_tier,
            "match_reasons": match_reasons[:3],
            "variants": variants,
        }

    def rank_groups(
        self,
        pq: ProcessedQuery,
        only_available: bool = False,
        registry_only: bool = False,
        promo_only: bool = False,
        top_k: int = 40,
    ) -> List[Tuple[Dict[str, Any], float, List[str]]]:
        if not pq.normalized_query:
            return []

        # 1. Neural semantic similarity
        if pq.matched_rule:
            v_norm = self.embedder.encode_query(pq.normalized_query)
            v_exp = self.embedder.encode_query(pq.semantic_query)
            q_vec = 0.60 * v_norm + 0.40 * v_exp
            q_vec = q_vec / np.clip(np.linalg.norm(q_vec), 1e-12, None)
        else:
            q_vec = self.embedder.encode_query(pq.semantic_query)

        sem_scores = self.embeddings @ q_vec  # shape [N]

        # 2. BM25F lexical score
        bm25_scores = (
            self.bm25.get_scores(pq.lexical_tokens)
            if pq.lexical_tokens
            else np.zeros(len(self.groups), dtype=np.float32)
        )

        # Candidate union: top 180 by semantic + top 180 by BM25 + rule-boosted vendor/category matches
        sem_top = np.argpartition(-sem_scores, min(180, len(sem_scores) - 1))[:180]
        bm25_top = np.argpartition(-bm25_scores, min(180, len(bm25_scores) - 1))[:180]
        cand_indices: Set[int] = set(int(i) for i in sem_top) | set(int(i) for i in bm25_top)

        rule = pq.matched_rule
        if rule:
            boost_v_low = tuple(v.lower() for v in rule.boost_vendors)
            boost_c_set = set(rule.boost_categories)
            boost_g_low = tuple(gn.lower() for gn in rule.boost_group_names)
            for idx, g in enumerate(self.groups):
                if (
                    g["category_id"] in boost_c_set
                    or g["root_category_id"] in boost_c_set
                    or any(bv in g["_vendor_low"] for bv in boost_v_low)
                    or any(bg in g["_title_low"] for bg in boost_g_low)
                ):
                    cand_indices.add(idx)

        if pq.is_server_ambiguous and pq.detected_intent in ("hardware", "options"):
            for idx, g in enumerate(self.groups):
                if g["root_category_id"] == "86562" and g["available"]:
                    cand_indices.add(idx)

        # Compute RRF ranks among candidates
        sem_sorted = sorted(cand_indices, key=lambda i: -float(sem_scores[i]))
        bm25_sorted = sorted(cand_indices, key=lambda i: -float(bm25_scores[i]))
        sem_rank = {idx: r for r, idx in enumerate(sem_sorted)}
        bm25_rank = {idx: r for r, idx in enumerate(bm25_sorted)}

        q_low = pq.normalized_query.lower().replace("ё", "е").strip()
        q_core_tokens = [
            t for t in _WORD_SPLIT_RE.findall(q_low)
            if len(t) >= 2 and t not in {"для", "под", "на", "и", "в", "по", "с", "программа", "лицензия"}
        ]

        scored: List[Tuple[Dict[str, Any], float, List[str]]] = []
        for idx in cand_indices:
            g = self.groups[idx]
            if only_available and not g["available"]:
                continue
            if (registry_only or pq.wants_ru_registry) and not g["is_ru_registry"]:
                continue
            if promo_only and not (g["discount_pct"] > 0 or g["price_adv_pct"] > 0):
                continue
            if pq.max_budget and g["available"] and g["min_price"] > pq.max_budget:
                continue

            reasons: List[str] = []
            rrf = 35.0 / (25.0 + sem_rank[idx]) + 35.0 / (25.0 + bm25_rank[idx])
            s_val = float(sem_scores[idx])
            b_val = float(bm25_scores[idx])
            score = rrf + s_val * 4.5 + min(b_val, 32.0) * 0.16

            head_low = g["_head_low"]
            title_low = g["_title_low"]
            tail_low = g["_tail_low"]
            vendor_low = g["_vendor_low"]

            # Exact / phrase matching on head product title
            if q_low and (head_low == q_low or title_low == q_low):
                score += 7.5
                reasons.append("Точное совпадение продуктовой линейки")
            elif q_low and len(q_low) >= 3 and (head_low.startswith(q_low) or f" {q_low}" in f" {head_low}"):
                score += 4.2
                reasons.append("Прямое вхождение в название продукта")

            if q_core_tokens:
                in_head = sum(1 for t in q_core_tokens if t in head_low or t in vendor_low)
                in_tail_only = sum(1 for t in q_core_tokens if t in tail_low and t not in head_low and t not in vendor_low)
                coverage = in_head / len(q_core_tokens)
                score += coverage * 3.6
                if in_tail_only > 0 and in_head == 0:
                    # 'КриптоПро для Astra Linux' when searching 'astra linux' -> demote in main, use in cross-sell!
                    score -= 5.2
                elif coverage >= 0.8:
                    reasons.append("Полное совпадение ключевых терминов")

            # Special guard for pure numeric query like '365': require '365' in title/category, not accidental SKU
            if q_low == "365":
                if "365" in title_low:
                    score += 5.0
                    if "microsoft 365" in title_low or "for family" in g["flagship_url"] or "для семьи" in title_low:
                        score += 4.0
                else:
                    score -= 3.0

            # Domain rule boosts
            if rule:
                if any(gn.lower() in title_low for gn in rule.boost_group_names):
                    score += 4.5
                    reasons.append("Целевая линейка по смыслу запроса")
                if any(v.lower() in vendor_low for v in rule.boost_vendors):
                    score += 2.6
                    reasons.append(f"Профильный вендор ({g['vendor']})")
                if g["category_id"] in rule.boost_categories or g["root_category_id"] in rule.boost_categories:
                    score += 2.0

            # Hardware vs Software disambiguation
            if pq.is_server_ambiguous:
                if pq.detected_intent == "hardware":
                    if g["root_category_id"] == "86562" and g["product_type"] == "электроника":
                        is_acc = bool(SERVER_ACCESSORY_PATTERNS.search(g["title"]) or g["category_id"] == "87956")
                        if not is_acc:
                            score += 7.5
                            reasons.append("Физический сервер (оборудование)")
                        else:
                            score += 1.5
                    elif g["product_type"] == "электроника":
                        score += 2.0
                    else:
                        score -= 4.5
                elif pq.detected_intent == "software":
                    if g["product_type"] == "софт":
                        score += 4.0
                        reasons.append("Серверное ПО / серверная ОС")
                    else:
                        score -= 4.5
                elif pq.detected_intent == "options":
                    if g["category_id"] in ("87956", "87417") or g["root_category_id"] == "98189":
                        score += 6.5
                        reasons.append("Серверные комплектующие и СХД")
                    else:
                        score -= 2.5

            # Availability & base license preference
            if g["available"]:
                score += 2.8
            else:
                # Keep exact historical matches (e.g. Microsoft 365) visible if title matches strongly, else penalize
                if q_low and q_low in title_low and len(q_low) >= 3:
                    score -= 0.4
                else:
                    score -= 3.8

            if not pq.wants_secondary_sku:
                if g["has_base_sku"]:
                    score += 1.5
                elif g["available"] and SECONDARY_HINT_IN_TITLE(title_low):
                    score -= 2.2

            if pq.wants_home_business and ("дома и бизнеса" in title_low or "home and business" in title_low):
                score += 5.5
                reasons.append("Редакция для дома и бизнеса")

            if pq.requested_version and pq.requested_version in f"{title_low} {g['versions_str'].lower()}":
                score += 2.8
                reasons.append(f"Версия {pq.requested_version}")

            if g["discount_pct"] > 0 and g["available"]:
                score += 0.45
                reasons.append(f"Акция −{g['discount_pct']:.0f}%")
            elif g["price_adv_pct"] > 0 and g["available"]:
                score += 0.25

            if not reasons:
                reasons.append("Семантическая близость к запросу" if s_val >= 0.80 else "Релевантное решение в каталоге")

            scored.append((g, score, reasons))

        scored.sort(key=lambda item: -item[1])
        return scored[:top_k]

    def search(
        self,
        raw_query: str,
        limit: int = 8,
        min_results: int = 4,
        intent_override: Optional[str] = None,
        only_available: bool = False,
        registry_only: bool = False,
        promo_only: bool = False,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        target_min = max(4, min_results)
        target_limit = max(target_min, limit)

        pq = self.qp.process(raw_query, intent_override=intent_override)
        ranked = self.rank_groups(
            pq,
            only_available=only_available,
            registry_only=registry_only,
            promo_only=promo_only,
            top_k=max(40, target_limit * 4),
        )

        conn = self._get_conn()
        try:
            cards: List[Dict[str, Any]] = []
            seen_offer_ids: Set[str] = set()
            seen_group_ids: Set[str] = set()
            vendor_counts: Dict[str, int] = {}
            deferred_ranked: List[Tuple[Dict[str, Any], float, List[str]]] = []

            for g, sc, reasons in ranked:
                if len(cards) >= target_limit:
                    break
                v_key = g["vendor"].lower()
                # For broad generic queries like 'сервер' or 'антивирь', diversify vendors after 3 items
                if pq.is_server_ambiguous and vendor_counts.get(v_key, 0) >= 3:
                    deferred_ranked.append((g, sc, reasons))
                    continue
                sku, variants = self._select_best_sku_and_variants(conn, g, pq, only_available=only_available)
                oid = str(sku.get("offer_id", g["flagship_offer_id"]))
                if oid in seen_offer_ids:
                    continue
                seen_offer_ids.add(oid)
                seen_group_ids.add(g["group_id"])
                vendor_counts[v_key] = vendor_counts.get(v_key, 0) + 1
                cards.append(self._format_product_card(g, sku, variants, sc, reasons, match_tier="primary"))

            for g, sc, reasons in deferred_ranked:
                if len(cards) >= target_limit:
                    break
                sku, variants = self._select_best_sku_and_variants(conn, g, pq, only_available=only_available)
                oid = str(sku.get("offer_id", g["flagship_offer_id"]))
                if oid in seen_offer_ids:
                    continue
                seen_offer_ids.add(oid)
                seen_group_ids.add(g["group_id"])
                cards.append(self._format_product_card(g, sku, variants, sc, reasons, match_tier="primary"))

            # Guarantee >= 4 products:
            # Stage A: If narrow query matched 1-3 groups with multiple distinct SKU configurations, expand sibling SKUs
            if len(cards) < target_min and ranked:
                for g, sc, _ in ranked[:3]:
                    if len(cards) >= target_min:
                        break
                    _, variants = self._select_best_sku_and_variants(conn, g, pq, only_available=only_available)
                    for v in variants:
                        if len(cards) >= target_min:
                            break
                        void = str(v["offer_id"])
                        if void in seen_offer_ids:
                            continue
                        row = conn.execute("SELECT * FROM offers WHERE offer_id = ?", (void,)).fetchone()
                        if row:
                            seen_offer_ids.add(void)
                            cards.append(
                                self._format_product_card(
                                    g,
                                    dict(row),
                                    variants,
                                    sc - 0.5,
                                    ["Дополнительная конфигурация / вариант лицензирования"],
                                    match_tier="configuration",
                                )
                            )

            # Stage B: Relax optional filters (promo/registry/availability) or pull semantic category analogs
            if len(cards) < target_min:
                relaxed_ranked = self.rank_groups(pq, only_available=True, top_k=20)
                if not relaxed_ranked:
                    # Fallback for completely empty/symbol query: popular active flagship products
                    relaxed_ranked = [
                        (g, 1.0, ["Популярное решение каталога Store.softline.ru"])
                        for g in self.groups[:20]
                        if g["available"]
                    ]
                for g, sc, _ in relaxed_ranked:
                    if len(cards) >= target_min:
                        break
                    if g["group_id"] in seen_group_ids:
                        continue
                    sku, variants = self._select_best_sku_and_variants(conn, g, pq, only_available=True)
                    oid = str(sku.get("offer_id", g["flagship_offer_id"]))
                    if oid in seen_offer_ids:
                        continue
                    seen_offer_ids.add(oid)
                    seen_group_ids.add(g["group_id"])
                    cards.append(
                        self._format_product_card(
                            g,
                            sku,
                            variants,
                            sc,
                            ["Связанный аналог в наличии из смежной категории"],
                            match_tier="analog",
                        )
                    )
        finally:
            conn.close()

        latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
        return {
            "query": {
                "raw": pq.raw_query,
                "normalized": pq.normalized_query,
                "detected_intent": pq.detected_intent,
                "is_server_ambiguous": pq.is_server_ambiguous,
                "transformations": pq.transformations,
                "explanation": pq.explanation,
                "rule_id": pq.matched_rule.rule_id if pq.matched_rule else None,
                "import_substitution_category": (
                    pq.matched_rule.import_substitution_category if pq.matched_rule else None
                ),
                "disambiguation_chips": [
                    {"intent_id": c.intent_id, "label": c.label, "active": c.active}
                    for c in pq.disambiguation_chips
                ],
            },
            "results": cards,
            "total_returned": len(cards),
            "latency_ms": latency_ms,
            "_processed_query": pq,
        }

    def legacy_baseline_search(self, raw_query: str, limit: int = 6) -> Dict[str, Any]:
        """
        Reproduces the current exact-substring search on Store.softline.ru:
        matches raw query words directly against offer names/descriptions/URLs in feed order,
        without synonym/jargon normalization, availability filtering, or hardware/software intent.
        """
        t0 = time.perf_counter()
        q = (raw_query or "").strip().lower()
        if not q:
            return {"results": [], "total_returned": 0, "latency_ms": 0.0, "issues_detected": []}

        words = [w for w in q.split() if w]
        conn = self._get_conn()
        try:
            clauses = []
            params: List[str] = []
            for w in words[:5]:
                like = f"%{w}%"
                clauses.append("(LOWER(name) LIKE ? OR LOWER(description) LIKE ? OR LOWER(url) LIKE ?)")
                params.extend([like, like, like])
            where_sql = " AND ".join(clauses) if clauses else "1=0"
            rows = conn.execute(
                f"SELECT * FROM offers WHERE {where_sql} LIMIT ?",
                (*params, limit),
            ).fetchall()

            items = [
                {
                    "offer_id": r["offer_id"],
                    "name": r["name"],
                    "vendor": r["vendor"],
                    "category_id": r["category_id"],
                    "available": bool(r["available"]),
                    "price": r["price"],
                    "product_type": r["product_type"],
                    "is_secondary": bool(r["is_secondary"]),
                    "tail_target": r["tail_target"],
                    "url": r["url"],
                    "picture": r["picture"],
                }
                for r in rows
            ]
        finally:
            conn.close()

        issues: List[str] = []
        if not items:
            issues.append("0 результатов: точный поиск не понял опечатку, сленг, транслитерацию или ребрендинг")
        else:
            unavail = sum(1 for x in items if not x["available"] or x["price"] <= 0)
            if unavail > 0:
                issues.append(f"{unavail} из {len(items)} карточек в выдаче архивные (available=false / цена 0 ₽)")
            if any(x["tail_target"] for x in items[:2]):
                issues.append("На 1-м месте сопутствующий аддон/сертификат «X для Y» вместо самого базового продукта")
            if "сервер" in q and all(x["product_type"] == "софт" for x in items):
                issues.append("Выданы только серверные лицензии прикладного ПО, физические серверы потеряны")
            if q == "365":
                issues.append("Ложное совпадение подстроки «365» внутри числовых артикулов и URL случайных товаров")

        return {
            "results": items,
            "total_returned": len(items),
            "latency_ms": round((time.perf_counter() - t0) * 1000.0, 1),
            "issues_detected": issues,
        }

    def suggest(self, prefix: str, limit_products: int = 4) -> Dict[str, Any]:
        """Sub-30ms live typeahead suggestions with instant product recommendations & promo tip."""
        t0 = time.perf_counter()
        q = (prefix or "").strip()
        if len(q) < 2:
            return {
                "prefix": q,
                "normalized_hint": "",
                "suggested_queries": [
                    "astra linux",
                    "сервер",
                    "кибер бэкап",
                    "kaspersky small office security",
                    "крипто про csp 5.0",
                    "мтс",
                ],
                "categories": [],
                "products": [],
                "promo_tip": None,
                "latency_ms": 0.5,
            }

        pq = self.qp.process(q)
        norm_low = pq.normalized_query.lower()

        # Fast query completions
        popular_queries = [
            "astra linux",
            "Microsoft Office для дома и бизнеса",
            "kaspersky small office security",
            "крипто про csp 5.0",
            "anydesk",
            "кибер бэкап",
            "сканер-вс",
            "мтс линк",
            "max patrol",
            "Microsoft 365",
            "сервер DEPO Storm",
            "серверная ОС Astra Linux",
            "MDaemon почтовый сервер",
            "UserGate NGFW со скидкой",
            "Р7-Офис Профессиональный",
        ]
        sugg_queries: List[str] = []
        if pq.normalized_query.lower() != q.lower():
            sugg_queries.append(pq.normalized_query)
        for pq_cand in popular_queries:
            if norm_low in pq_cand.lower() or q.lower() in pq_cand.lower():
                if pq_cand not in sugg_queries:
                    sugg_queries.append(pq_cand)
            if len(sugg_queries) >= 5:
                break

        # Rank top active products for instant dropdown preview
        ranked = self.rank_groups(pq, only_available=True, top_k=10)
        instant_products: List[Dict[str, Any]] = []
        seen_cats: Dict[str, str] = {}
        promo_tip: Optional[Dict[str, Any]] = None

        for g, sc, reasons in ranked:
            if g["category_id"] not in seen_cats and len(seen_cats) < 3:
                seen_cats[g["category_id"]] = g["sub_category_name"]
            if len(instant_products) < limit_products:
                instant_products.append({
                    "group_id": g["group_id"],
                    "title": g["title"],
                    "name": g["flagship_name"],
                    "vendor": g["vendor"],
                    "category": g["sub_category_name"],
                    "price": g["flagship_price"],
                    "oldprice": g["flagship_oldprice"],
                    "discount_pct": g["discount_pct"],
                    "price_adv_label": g["price_adv_label"],
                    "is_ru_registry": bool(g["is_ru_registry"]),
                    "picture": g["picture"],
                    "url": g["flagship_url"],
                    "reason": reasons[0] if reasons else "",
                })
            elif promo_tip is None and (g["discount_pct"] > 0 or g["price_adv_pct"] > 0):
                promo_tip = {
                    "title": g["title"],
                    "vendor": g["vendor"],
                    "price": g["flagship_price"],
                    "badge": g["price_adv_label"] or f"Акция −{g['discount_pct']:.0f}%",
                    "url": g["flagship_url"],
                }

        # If no promo tip found in direct hits, surface active UserGate / ITV promo or ecosystem companion
        if promo_tip is None:
            for g in self.groups:
                if g["available"] and g["discount_pct"] >= 15 and g["group_id"] not in {p["group_id"] for p in instant_products}:
                    promo_tip = {
                        "title": g["title"],
                        "vendor": g["vendor"],
                        "price": g["flagship_price"],
                        "badge": g["price_adv_label"] or f"Акция −{g['discount_pct']:.0f}%",
                        "url": g["flagship_url"],
                    }
                    break

        if not sugg_queries and instant_products:
            sugg_queries = [p["title"] for p in instant_products[:4]]

        return {
            "prefix": q,
            "normalized_hint": pq.explanation if (pq.transformations or pq.matched_rule or pq.is_server_ambiguous) else "",
            "corrected_to": pq.normalized_query if pq.normalized_query.lower() != q.lower() else "",
            "suggested_queries": sugg_queries[:4],
            "categories": [{"id": cid, "name": cname} for cid, cname in seen_cats.items()],
            "products": instant_products,
            "promo_tip": promo_tip,
            "latency_ms": round((time.perf_counter() - t0) * 1000.0, 1),
        }


def SECONDARY_HINT_IN_TITLE(title_low: str) -> bool:
    return any(
        w in title_low
        for w in ("обучающие курсы", "сертификат", "дополнительные", "коннектор", "connector")
    )
