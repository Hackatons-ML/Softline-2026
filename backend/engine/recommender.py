"""
Upsell, Cross-Sell & Import-Substitution Recommendation Engine for Store.softline.ru.

Combines:
1. Verified External Vendor Ecosystem Rules (Ready for Astra, Cyberprotect, Kaspersky,
   CryptoPro, Positive Technologies, MTS Link, UserGate) with official source links.
2. Catalog-mined 'X для Y' compatibility edges from Mindbox.yml.gz.xml.
3. Commercial value enhancers: active discounts (oldprice > price), richer editions (Upsell),
   and verified Russian Registry alternatives when primary items are unavailable.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Set

from backend.data.domain_knowledge import (
    IMPORT_SUBSTITUTION_ALTERNATIVES,
    VERIFIED_ECOSYSTEM_RULES,
    EcosystemRule,
)
from backend.engine.hybrid_search import SmartSearchEngine
from backend.engine.query_processor import ProcessedQuery


class RecommendationEngine:
    def __init__(self, search_engine: SmartSearchEngine) -> None:
        self.se = search_engine

    def _select_ecosystem_rule(
        self, pq: ProcessedQuery, primary_results: List[Dict[str, Any]]
    ) -> EcosystemRule:
        context_blobs = [pq.normalized_query.lower()]
        for item in primary_results[:3]:
            context_blobs.append(
                f"{item['group_title']} {item['vendor']} {item['sub_category_name']} {item['root_category_name']}".lower()
            )
        joined = " | ".join(context_blobs)

        if pq.detected_intent == "hardware" or any(r.get("product_type") == "электроника" for r in primary_results[:2]):
            for rule in VERIFIED_ECOSYSTEM_RULES:
                if rule.ecosystem_id == "server_hardware_stack":
                    return rule

        best_rule = VERIFIED_ECOSYSTEM_RULES[0]
        best_hits = -1
        for rule in VERIFIED_ECOSYSTEM_RULES:
            hits = sum(1 for kw in rule.match_keywords if kw in joined)
            if hits > best_hits:
                best_hits = hits
                best_rule = rule
        return best_rule

    def build_recommendations(
        self,
        pq: ProcessedQuery,
        primary_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        primary_group_ids: Set[str] = {r["group_id"] for r in primary_results}
        primary_vendors: Set[str] = {r["vendor"].lower() for r in primary_results[:2]}

        # -------------------------------------------------------------------
        # 1. Cross-Sell: "Часто покупают вместе / Технологический стек"
        # -------------------------------------------------------------------
        eco_rule = self._select_ecosystem_rule(pq, primary_results)
        cross_sell: List[Dict[str, Any]] = []
        used_gids: Set[str] = set(primary_group_ids)

        # First check catalog-mined 'X для Y' direct companions if applicable (e.g. 'КриптоПро CSP для Astra Linux SE')
        q_context = f"{pq.normalized_query} {primary_results[0]['group_title'] if primary_results else ''}".lower()
        for target_key, comp_entries in self.se.mined_companions.items():
            if target_key in q_context:
                for ce in comp_entries:
                    gid = ce["group_id"]
                    g = self.se.group_by_id.get(gid)
                    if not g or gid in used_gids or not g["available"] or g["vendor"].lower() in primary_vendors:
                        continue
                    if g["flagship_price"] <= 0:
                        continue
                    used_gids.add(gid)
                    cross_sell.append({
                        "group_id": gid,
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
                        "relation_badge": f"Прямая совместимость в каталоге с {target_key.title()}",
                        "source": {
                            "vendor_name": f"{g['vendor']} × Store.softline.ru",
                            "program_title": "Специализированная совместимая позиция каталога",
                            "url": g["flagship_url"],
                            "summary": f"Позиция каталога явно предназначена для совместной работы: «{ce['evidence']}».",
                        },
                    })
                    if len(cross_sell) >= 1:
                        break

        # Enrich with Verified External Vendor Ecosystem companions (up to 4 total)
        for comp_query, rel_badge, v_source in eco_rule.companion_queries:
            if len(cross_sell) >= 4:
                break
            comp_pq = self.se.qp.process(comp_query)
            ranked = self.se.rank_groups(comp_pq, only_available=True, top_k=8)
            for g, _, _ in ranked:
                if g["group_id"] in used_gids or g["flagship_price"] <= 0:
                    continue
                used_gids.add(g["group_id"])
                cross_sell.append({
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
                    "relation_badge": rel_badge,
                    "source": {
                        "vendor_name": v_source.vendor_name,
                        "program_title": v_source.program_title,
                        "url": v_source.url,
                        "summary": v_source.summary,
                    },
                })
                break

        # -------------------------------------------------------------------
        # 2. Upsell, Active Promotions & Import-Substitution Alternatives
        # -------------------------------------------------------------------
        alternatives: List[Dict[str, Any]] = []
        alt_section_title = "Выгодные редакции, акции и альтернативы"
        alt_section_reason = (
            "Решения с расширенной комплектацией, действующей скидкой или более выгодной ценой в смежных линейках."
        )

        has_unavailable_top = any(not r["available"] for r in primary_results[:3])
        imp_cat: Optional[str] = pq.matched_rule.import_substitution_category if pq.matched_rule else None

        # Auto-infer import substitution category if top item is unavailable foreign software
        if not imp_cat and has_unavailable_top and primary_results:
            top_cat = f"{primary_results[0]['root_category_name']} {primary_results[0]['sub_category_name']}".lower()
            if "офис" in top_cat or "текст" in top_cat:
                imp_cat = "office_suite"
            elif "операцион" in top_cat:
                imp_cat = "os"
            elif "график" in top_cat or "документ" in top_cat:
                imp_cat = "pdf_ocr"
            elif "удаленн" in top_cat:
                imp_cat = "remote_access"
            elif "сапр" in top_cat:
                imp_cat = "cad"

        if imp_cat and imp_cat in IMPORT_SUBSTITUTION_ALTERNATIVES:
            alt_query, badge_title, rationale = IMPORT_SUBSTITUTION_ALTERNATIVES[imp_cat]
            alt_section_title = badge_title
            alt_section_reason = rationale
            alt_pq = self.se.qp.process(alt_query)
            alt_ranked = self.se.rank_groups(alt_pq, only_available=True, top_k=10)
            for g, _, _ in alt_ranked:
                if g["group_id"] in used_gids or g["flagship_price"] <= 0:
                    continue
                used_gids.add(g["group_id"])
                alternatives.append({
                    "group_id": g["group_id"],
                    "title": g["title"],
                    "name": g["flagship_name"],
                    "vendor": g["vendor"],
                    "category": g["sub_category_name"],
                    "price": g["flagship_price"],
                    "oldprice": g["flagship_oldprice"],
                    "discount_pct": g["discount_pct"],
                    "price_adv_label": g["price_adv_label"] or "В наличии · Быстрая поставка в РФ",
                    "is_ru_registry": bool(g["is_ru_registry"]),
                    "registry_num": g["registry_num"],
                    "picture": g["picture"],
                    "url": g["flagship_url"],
                    "upsell_type": "import_substitution",
                    "highlight_tag": "Реестр ПО РФ · Доступный аналог" if g["is_ru_registry"] else "Доступная альтернатива в наличии",
                })
                if len(alternatives) >= 4:
                    break

        # Fill remaining Upsell / Promo slots (richer edition of same vendor + best discounted/value items in category)
        if len(alternatives) < 4 and primary_results:
            lead = primary_results[0]
            lead_cat = lead["category_id"]
            lead_root = lead["root_category_name"]

            # Richer edition upsell from same vendor or category
            for g in self.se.groups:
                if len(alternatives) >= 4:
                    break
                if not g["available"] or g["group_id"] in used_gids or g["flagship_price"] <= 0:
                    continue
                is_promo_in_domain = g["discount_pct"] > 0 and (
                    g["category_id"] == lead_cat or g["root_category_name"] == lead_root
                )
                is_richer_edition = (
                    g["vendor"] == lead["vendor"]
                    and g["category_id"] == lead_cat
                    and any(w in g["title"].lower() for w in ("расширен", "про", "pro", "enterprise", "бизнес", "смоленск", "максимал"))
                )
                is_value_leader = g["category_id"] == lead_cat and g["price_adv_pct"] >= 15

                if is_promo_in_domain or is_richer_edition or is_value_leader:
                    used_gids.add(g["group_id"])
                    if is_promo_in_domain:
                        htag = f"Акционное предложение −{g['discount_pct']:.0f}%"
                        utype = "promo"
                    elif is_richer_edition:
                        htag = "Старшая редакция · Богаче комплектация"
                        utype = "upsell_edition"
                    else:
                        htag = g["price_adv_label"] or "Выгодная цена в категории"
                        utype = "price_advantage"

                    alternatives.append({
                        "group_id": g["group_id"],
                        "title": g["title"],
                        "name": g["flagship_name"],
                        "vendor": g["vendor"],
                        "category": g["sub_category_name"],
                        "price": g["flagship_price"],
                        "oldprice": g["flagship_oldprice"],
                        "discount_pct": g["discount_pct"],
                        "price_adv_label": g["price_adv_label"] or htag,
                        "is_ru_registry": bool(g["is_ru_registry"]),
                        "registry_num": g["registry_num"],
                        "picture": g["picture"],
                        "url": g["flagship_url"],
                        "upsell_type": utype,
                        "highlight_tag": htag,
                    })

        # Final promo spotlight fallback if still < 3 items
        if len(alternatives) < 3:
            for g in self.se.groups:
                if len(alternatives) >= 3:
                    break
                if g["available"] and g["discount_pct"] >= 15 and g["group_id"] not in used_gids:
                    used_gids.add(g["group_id"])
                    alternatives.append({
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
                        "registry_num": g["registry_num"],
                        "picture": g["picture"],
                        "url": g["flagship_url"],
                        "upsell_type": "promo",
                        "highlight_tag": f"Спецпредложение каталога −{g['discount_pct']:.0f}%",
                    })

        return {
            "cross_sell": {
                "title": "Часто покупают вместе · Совместимые решения",
                "subtitle": "Подобрано по графу совместимости каталога Store.softline.ru и официальным матрицам технологического партнерства вендоров",
                "items": cross_sell,
            },
            "alternatives_and_upsell": {
                "title": alt_section_title,
                "subtitle": alt_section_reason,
                "has_unavailable_primary": has_unavailable_top,
                "items": alternatives,
            },
        }
