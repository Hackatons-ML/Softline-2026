"""
Automated Benchmark Evaluator against:
1. All 10 official ground-truth queries from 'Выборка поисковых запросов.xlsx'
2. Core showcase scenarios from 'ИИкузница_—_Умный поиск на сайте.pdf'
"""

from __future__ import annotations
import statistics
from typing import Any, Callable, Dict, List

from backend.engine.hybrid_search import SmartSearchEngine


OFFICIAL_XLSX_BENCHMARK: List[Dict[str, Any]] = [
    {
        "query": "astra linux",
        "source": "XLSX #1",
        "target_url": "https://store.softline.ru/astralinux/astra-linux-special-edition/",
        "expected_desc": "Astra Linux Special Edition (Группа Астра, а не чужие сертификаты для Astra)",
        "matcher": lambda card: (
            "astralinux" in card["url"].lower()
            and "astra linux special edition" in f"{card['group_title']} {card['name']}".lower()
        ),
    },
    {
        "query": "Microsoft Office для дома и бизнеса",
        "source": "XLSX #2",
        "target_url": "https://store.softline.ru/microsoft/microsoft-office-dlya-doma-i-biznesa-2024/",
        "expected_desc": "Microsoft Office 2024 для дома и бизнеса",
        "matcher": lambda card: (
            "microsoft" in card["url"].lower()
            and "дома и бизнеса" in f"{card['group_title']} {card['name']}".lower()
        ),
    },
    {
        "query": "kaspersky small office security",
        "source": "XLSX #3",
        "target_url": "https://store.softline.ru/kaspersky/kaspersky-small-office-security/",
        "expected_desc": "Kaspersky Small Office Security",
        "matcher": lambda card: "kaspersky small office security" in f"{card['group_title']} {card['name']}".lower(),
    },
    {
        "query": "крипто про csp 5.0",
        "source": "XLSX #4",
        "target_url": "https://store.softline.ru/kripto-pro/cryptopro-csp/",
        "expected_desc": "КриптоПро CSP 5.0 (kripto-pro)",
        "matcher": lambda card: (
            "kripto-pro" in card["url"].lower()
            and "csp" in f"{card['group_title']} {card['name']}".lower()
        ),
    },
    {
        "query": "anydesk",
        "source": "XLSX #5",
        "target_url": "https://store.softline.ru/anydesk/anydesk/",
        "expected_desc": "AnyDesk (лицензия удаленного доступа)",
        "matcher": lambda card: "anydesk" in card["url"].lower() and "anydesk" in card["group_title"].lower(),
    },
    {
        "query": "кибер бэкап",
        "source": "XLSX #6",
        "target_url": "https://store.softline.ru/cyberprotect/?filter%5Bcategory%5D%5B%5D=1033",
        "expected_desc": "Киберпротект Кибер Бэкап (категория 1033)",
        "matcher": lambda card: (
            "cyberprotect" in card["url"].lower()
            and card["category_id"] == "1033"
        ),
    },
    {
        "query": "сканер-вс",
        "source": "XLSX #7",
        "target_url": "https://store.softline.ru/npo-echelon/eshelon-skaner-vs/",
        "expected_desc": "НПО «Эшелон» СКАНЕР-ВС",
        "matcher": lambda card: (
            "npo-echelon" in card["url"].lower()
            and "сканер-вс" in f"{card['group_title']} {card['name']}".lower()
        ),
    },
    {
        "query": "мтс",
        "source": "XLSX #8",
        "target_url": "https://store.softline.ru/webinar/",
        "expected_desc": "МТС Линк / Webinar (store.softline.ru/webinar/)",
        "matcher": lambda card: "/webinar/" in card["url"].lower() or "мтс линк" in card["vendor"].lower(),
    },
    {
        "query": "max patrol",
        "source": "XLSX #9",
        "target_url": "https://store.softline.ru/positive-technologies/maxpatrol-endpoint-protection-platform/",
        "expected_desc": "Positive Technologies MaxPatrol",
        "matcher": lambda card: (
            "positive-technologies" in card["url"].lower()
            and "maxpatrol" in f"{card['group_title']} {card['name']}".lower()
        ),
    },
    {
        "query": "365",
        "source": "XLSX #10",
        "target_url": "https://store.softline.ru/microsoft/microsoft-365-for-family/",
        "expected_desc": "Microsoft 365 / Office или платформа 365 (без мусорных SKU -519365)",
        "matcher": lambda card: (
            "microsoft 365" in f"{card['group_title']} {card['name']}".lower()
            or "microsoft office" in f"{card['group_title']} {card['name']}".lower()
            or "elma365" in card["group_title"].lower()
        ),
    },
]

PDF_SHOWCASE_SCENARIOS: List[Dict[str, Any]] = [
    {
        "query": "сервер",
        "source": "PDF · Интент Железо vs ПО",
        "target_url": "https://store.softline.ru/hardware/servers/",
        "expected_desc": "Физическое серверное оборудование (электроника, Rack/Tower серверы)",
        "matcher": lambda card: card["product_type"] == "электроника",
    },
    {
        "query": "антивирь",
        "source": "PDF · ИТ-жаргон",
        "target_url": "https://store.softline.ru/security/antivirus/",
        "expected_desc": "Антивирусные решения (Kaspersky / Dr.Web / PRO32)",
        "matcher": lambda card: card["category_id"] in ("650", "652") or "kaspersky" in card["name"].lower(),
    },
    {
        "query": "винда",
        "source": "PDF · ИТ-жаргон",
        "target_url": "https://store.softline.ru/os/",
        "expected_desc": "ОС Windows или сертифицированные российские ОС",
        "matcher": lambda card: "операционные системы" in card["root_category_name"].lower(),
    },
    {
        "query": "офис",
        "source": "PDF · Разговорный запрос",
        "target_url": "https://store.softline.ru/office/",
        "expected_desc": "Офисные пакеты (Microsoft Office / Р7-Офис / МойОфис)",
        "matcher": lambda card: "офисные программы" in card["root_category_name"].lower(),
    },
    {
        "query": "астра линукс",
        "source": "PDF · Кириллический транслит",
        "target_url": "https://store.softline.ru/astralinux/astra-linux-special-edition/",
        "expected_desc": "Astra Linux Special Edition",
        "matcher": lambda card: "astra linux" in card["group_title"].lower() and "astralinux" in card["url"].lower(),
    },
    {
        "query": "мдаемон",
        "source": "PDF · Транслит / опечатка",
        "target_url": "https://store.softline.ru/alt-n-technologies-ltd/",
        "expected_desc": "MDaemon Messaging Server",
        "matcher": lambda card: "mdaemon" in f"{card['group_title']} {card['name']}".lower(),
    },
    {
        "query": "fcnhf kbyerc",
        "source": "Стресс-тест · Раскладка",
        "target_url": "https://store.softline.ru/astralinux/astra-linux-special-edition/",
        "expected_desc": "Автоисправление раскладки → Astra Linux Special Edition",
        "matcher": lambda card: "astra linux" in card["group_title"].lower(),
    },
    {
        "query": "акронис",
        "source": "Стресс-тест · Ребрендинг",
        "target_url": "https://store.softline.ru/cyberprotect/",
        "expected_desc": "Ребрендинг Acronis → Киберпротект Кибер Бэкап",
        "matcher": lambda card: "кибер бэкап" in card["group_title"].lower() or "cyberprotect" in card["url"].lower(),
    },
]


def run_full_benchmark(se: SmartSearchEngine) -> Dict[str, Any]:
    all_cases = OFFICIAL_XLSX_BENCHMARK + PDF_SHOWCASE_SCENARIOS
    rows: List[Dict[str, Any]] = []
    hit1_cnt = 0
    hit3_cnt = 0
    min4_cnt = 0
    legacy_pass_cnt = 0
    latencies: List[float] = []

    for case in all_cases:
        q = case["query"]
        matcher: Callable[[Dict[str, Any]], bool] = case["matcher"]

        smart = se.search(q, limit=6, min_results=4)
        legacy = se.legacy_baseline_search(q, limit=4)

        results = smart["results"]
        latencies.append(smart["latency_ms"])

        hit_rank = None
        for idx, card in enumerate(results, start=1):
            if matcher(card):
                hit_rank = idx
                break

        hit_at_1 = hit_rank == 1
        hit_at_3 = hit_rank is not None and hit_rank <= 3
        has_min_4 = len(results) >= 4

        # Check if legacy baseline top-1 is available AND matches target without issues
        leg_top = legacy["results"][0] if legacy["results"] else None
        leg_ok = False
        if leg_top and leg_top["available"] and not leg_top["tail_target"]:
            fake_card = {
                "url": leg_top["url"],
                "group_title": leg_top["name"],
                "name": leg_top["name"],
                "vendor": leg_top["vendor"],
                "category_id": leg_top["category_id"],
                "product_type": leg_top["product_type"],
                "root_category_name": "",
            }
            try:
                leg_ok = bool(matcher(fake_card))
            except Exception:
                leg_ok = False

        if hit_at_1:
            hit1_cnt += 1
        if hit_at_3:
            hit3_cnt += 1
        if has_min_4:
            min4_cnt += 1
        if leg_ok:
            legacy_pass_cnt += 1

        top_card = results[0] if results else {}
        rows.append({
            "query": q,
            "source": case["source"],
            "expected_desc": case["expected_desc"],
            "target_url": case["target_url"],
            "smart_top_title": top_card.get("group_title", ""),
            "smart_top_name": top_card.get("name", ""),
            "smart_top_url": top_card.get("url", ""),
            "smart_top_price": top_card.get("price", 0),
            "smart_count": len(results),
            "hit_rank": hit_rank,
            "hit_at_1": hit_at_1,
            "hit_at_3": hit_at_3,
            "min_4_ok": has_min_4,
            "legacy_ok": leg_ok,
            "legacy_top_name": leg_top["name"][:85] if leg_top else "Ничего не найдено (0 результатов)",
            "legacy_issue": legacy["issues_detected"][0] if legacy["issues_detected"] else "",
            "latency_ms": smart["latency_ms"],
        })

    n = len(all_cases)
    return {
        "summary": {
            "total_cases": n,
            "xlsx_cases": len(OFFICIAL_XLSX_BENCHMARK),
            "smart_hit_at_1_pct": round(hit1_cnt / n * 100.0, 1),
            "smart_hit_at_3_pct": round(hit3_cnt / n * 100.0, 1),
            "legacy_hit_at_1_pct": round(legacy_pass_cnt / n * 100.0, 1),
            "min_4_compliance_pct": round(min4_cnt / n * 100.0, 1),
            "median_latency_ms": round(statistics.median(latencies), 1) if latencies else 0.0,
        },
        "cases": rows,
    }
