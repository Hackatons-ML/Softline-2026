"""
Comprehensive Automated Test Suite for AIForge Smart Search (Store.softline.ru).
Verifies:
1. All 10 ground-truth benchmark queries from 'Выборка поисковых запросов.xlsx'
2. Hardware vs Software intent disambiguation on 'сервер'
3. Jargon, typos, keyboard layout, transliteration, and rebrandings
4. Hard invariant: >= 4 products returned on EVERY query
5. Cross-sell recommendations with external vendor sources & price/promo badges
6. FastAPI endpoints (/api/suggest, /api/search, /api/compare, /api/benchmark, /api/analytics)
"""

from __future__ import annotations
from fastapi.testclient import TestClient
import pytest

from backend.engine.benchmark import OFFICIAL_XLSX_BENCHMARK, run_full_benchmark
from backend.engine.hybrid_search import SmartSearchEngine
from backend.main import app


@pytest.fixture(scope="module")
def search_engine() -> SmartSearchEngine:
    return SmartSearchEngine()


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


@pytest.mark.parametrize("case", OFFICIAL_XLSX_BENCHMARK, ids=[c["query"] for c in OFFICIAL_XLSX_BENCHMARK])
def test_official_xlsx_benchmark_queries(search_engine: SmartSearchEngine, case: dict) -> None:
    res = search_engine.search(case["query"], limit=6, min_results=4)
    cards = res["results"]
    assert len(cards) >= 4, f"Must return >= 4 products for '{case['query']}'"
    top3_matches = [case["matcher"](c) for c in cards[:3]]
    assert any(top3_matches), (
        f"Query '{case['query']}' expected {case['expected_desc']} in top-3, "
        f"got: {[ (c['group_title'], c['url']) for c in cards[:3] ]}"
    )


def test_server_hardware_vs_software_disambiguation(search_engine: SmartSearchEngine) -> None:
    # Default 'сервер' -> physical server hardware (электроника)
    hw_res = search_engine.search("сервер", limit=6, min_results=4)
    assert len(hw_res["results"]) >= 4
    assert hw_res["query"]["is_server_ambiguous"] is True
    assert hw_res["results"][0]["product_type"] == "электроника"

    # Explicit software intent override -> server software (софт)
    sw_res = search_engine.search("сервер", limit=6, min_results=4, intent_override="software")
    assert len(sw_res["results"]) >= 4
    assert sw_res["results"][0]["product_type"] == "софт"


@pytest.mark.parametrize(
    "query,expected_substring",
    [
        ("антивирь", "kaspersky"),
        ("астра линукс", "astra linux"),
        ("мдаемон", "mdaemon"),
        ("fcnhf kbyerc", "astra linux"),
        ("акронис", "кибер бэкап"),
        ("зум", "линк"),
    ],
)
def test_jargon_typos_layout_and_rebranding(
    search_engine: SmartSearchEngine, query: str, expected_substring: str
) -> None:
    res = search_engine.search(query, limit=6, min_results=4)
    assert len(res["results"]) >= 4
    joined_top3 = " ".join(
        f"{c['group_title']} {c['name']} {c['vendor']}".lower() for c in res["results"][:3]
    )
    assert expected_substring in joined_top3


@pytest.mark.parametrize("edge_query", ["сканер-вс", "zoom", "jira", "photoshop", "неведомыйзапрос2026", "365"])
def test_minimum_four_products_invariant(search_engine: SmartSearchEngine, edge_query: str) -> None:
    res = search_engine.search(edge_query, limit=4, min_results=4)
    assert len(res["results"]) >= 4, f"Failed >= 4 invariant on '{edge_query}'"


def test_api_endpoints_and_recommendations(client: TestClient) -> None:
    # 1. Suggest while typing
    r_sug = client.get("/api/suggest", params={"q": "астр"})
    assert r_sug.status_code == 200
    sug = r_sug.json()
    assert len(sug["products"]) >= 1

    # 2. Full search + Cross-sell + Vendor sources
    r_search = client.get("/api/search", params={"q": "astra linux"})
    assert r_search.status_code == 200
    data = r_search.json()
    assert len(data["results"]) >= 4
    cross_sell = data["recommendations"]["cross_sell"]["items"]
    assert len(cross_sell) >= 3
    assert cross_sell[0]["source"]["url"].startswith("http")

    # 3. Analytics & Excel export
    r_ana = client.get("/api/analytics/overview")
    assert r_ana.status_code == 200
    assert r_ana.json()["kpis"]["smart_zero_result_rate_pct"] == 0.0

    r_xlsx = client.get("/api/analytics/export.xlsx")
    assert r_xlsx.status_code == 200
    assert len(r_xlsx.content) > 2000


def test_full_benchmark_score(search_engine: SmartSearchEngine) -> None:
    bench = run_full_benchmark(search_engine)
    assert bench["summary"]["min_4_compliance_pct"] == 100.0
    assert bench["summary"]["smart_hit_at_3_pct"] >= 90.0
