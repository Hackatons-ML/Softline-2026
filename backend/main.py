"""
FastAPI Backend for AIForge Smart Search & Recommendation Agent (Store.softline.ru).
Serves REST API + static React SPA on a single port.
"""

from __future__ import annotations
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Optional
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.data.build_index import DEFAULT_XML_PATH, STORAGE_DIR, build_catalog_index
from backend.engine.analytics_service import AnalyticsService
from backend.engine.benchmark import run_full_benchmark
from backend.engine.hybrid_search import SmartSearchEngine
from backend.engine.recommender import RecommendationEngine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"

app = FastAPI(
    title="AIForge · Умный поиск и допродажи Store.softline.ru",
    version="1.0.0",
    description="Гибридный семантический поиск, граф совместимости вендоров и аналитика каталога",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_search_engine: Optional[SmartSearchEngine] = None
_recommender: Optional[RecommendationEngine] = None
_analytics: Optional[AnalyticsService] = None
_benchmark_cache: Optional[Dict[str, Any]] = None


def get_services() -> tuple[SmartSearchEngine, RecommendationEngine, AnalyticsService]:
    global _search_engine, _recommender, _analytics
    if _search_engine is None:
        if not (STORAGE_DIR / "catalog.sqlite").exists():
            build_catalog_index(DEFAULT_XML_PATH, STORAGE_DIR)
        _search_engine = SmartSearchEngine(STORAGE_DIR)
        _recommender = RecommendationEngine(_search_engine)
        _analytics = AnalyticsService(STORAGE_DIR, _search_engine.catalog_stats)
    assert _recommender is not None and _analytics is not None
    return _search_engine, _recommender, _analytics


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    get_services()
    yield


app.router.lifespan_context = _lifespan


@app.get("/api/health")
def api_health() -> Dict[str, Any]:
    se, _, _ = get_services()
    return {
        "status": "ok",
        "catalog_stats": se.catalog_stats,
    }


@app.get("/api/suggest")
def api_suggest(q: str = Query("", max_length=160)) -> Dict[str, Any]:
    se, _, _ = get_services()
    return se.suggest(q, limit_products=4)


@app.get("/api/search")
def api_search(
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(8, ge=4, le=24),
    intent: Optional[str] = Query(None),
    only_available: bool = Query(False),
    registry_only: bool = Query(False),
    promo_only: bool = Query(False),
    log: bool = Query(True),
) -> Dict[str, Any]:
    se, rec, analytics = get_services()
    search_res = se.search(
        raw_query=q,
        limit=limit,
        min_results=4,
        intent_override=intent,
        only_available=only_available,
        registry_only=registry_only,
        promo_only=promo_only,
    )
    pq = search_res.pop("_processed_query")
    recs = rec.build_recommendations(pq, search_res["results"])

    log_id = 0
    if log:
        legacy_probe = se.legacy_baseline_search(q, limit=3)
        zero_or_broken_legacy = (
            legacy_probe["total_returned"] == 0 or len(legacy_probe["issues_detected"]) > 0
        )
        top_item = search_res["results"][0] if search_res["results"] else {}
        log_id = analytics.log_search(
            raw_query=q,
            normalized_query=pq.normalized_query,
            detected_intent=pq.detected_intent,
            rule_applied=pq.matched_rule.rule_id if pq.matched_rule else None,
            results_count=search_res["total_returned"],
            top_group_id=top_item.get("group_id", ""),
            top_title=top_item.get("group_title", ""),
            top_available=bool(top_item.get("available", False)),
            latency_ms=search_res["latency_ms"],
            had_typo_or_slang=bool(pq.transformations or pq.matched_rule),
            zero_in_legacy=zero_or_broken_legacy,
        )

    search_res["recommendations"] = recs
    search_res["log_id"] = log_id
    return search_res


@app.get("/api/compare")
def api_compare(q: str = Query(..., min_length=1, max_length=200)) -> Dict[str, Any]:
    se, rec, _ = get_services()
    legacy = se.legacy_baseline_search(q, limit=6)
    smart = se.search(q, limit=6, min_results=4)
    pq = smart.pop("_processed_query")
    smart["recommendations"] = rec.build_recommendations(pq, smart["results"])
    return {
        "query": q,
        "legacy": legacy,
        "smart": smart,
    }


@app.get("/api/benchmark")
def api_benchmark(refresh: bool = Query(False)) -> Dict[str, Any]:
    global _benchmark_cache
    se, _, _ = get_services()
    if _benchmark_cache is None or refresh:
        _benchmark_cache = run_full_benchmark(se)
    return _benchmark_cache


@app.get("/api/analytics/overview")
def api_analytics_overview() -> Dict[str, Any]:
    _, _, analytics = get_services()
    return analytics.get_dashboard_overview()


class ClickEventPayload(BaseModel):
    log_id: Optional[int] = None
    query: str = ""
    offer_url: str
    block: str = "main"


@app.post("/api/analytics/click")
def api_analytics_click(payload: ClickEventPayload) -> Dict[str, str]:
    _, _, analytics = get_services()
    analytics.log_click(payload.log_id, payload.query, payload.offer_url, payload.block)
    return {"status": "recorded"}


@app.get("/api/analytics/export.xlsx")
def api_analytics_export() -> Response:
    _, _, analytics = get_services()
    xlsx_bytes = analytics.export_excel_report()
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="Softline_Smart_Search_Analytics.xlsx"'
        },
    )


if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str) -> Response:
        target = FRONTEND_DIST / full_path
        if full_path and target.exists() and target.is_file():
            return FileResponse(str(target))
        index_html = FRONTEND_DIST / "index.html"
        if index_html.exists():
            return FileResponse(str(index_html))
        return JSONResponse({"message": "Frontend not built yet. Run `npm run build` in frontend/."})
