"""
Single-command launcher for AIForge Smart Search (Store.softline.ru).
Automatically builds the Mindbox catalog index on first run and starts FastAPI + UI on port 8000.
"""

from __future__ import annotations
import argparse
from pathlib import Path
import uvicorn

from backend.data.build_index import STORAGE_DIR, build_catalog_index, resolve_feed_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Smart Search for Store.softline.ru")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    parser.add_argument("--rebuild-index", action="store_true", help="Force rebuild index from Mindbox feed")
    args = parser.parse_args()

    if args.rebuild_index or not (STORAGE_DIR / "catalog.sqlite").exists():
        feed_path = resolve_feed_path()
        print(f"=== Building catalog index from {feed_path.name} ===")
        build_catalog_index(feed_path, Path(STORAGE_DIR))

    print(f"=== Starting AIForge Smart Search UI & API at http://{args.host}:{args.port} ===")
    uvicorn.run("backend.main:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
