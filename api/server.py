"""FastAPI application — Clinical Picasso API."""

from __future__ import annotations

import logging

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from api.deps import init_client, load_records, build_graph
from api.routes import corpus, graph, chat, ingest

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(title="Clinical Picasso", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(corpus.router, prefix="/api/corpus", tags=["corpus"])
app.include_router(graph.router, prefix="/api/graph", tags=["graph"])

app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(ingest.router, prefix="/api/ingest", tags=["ingest"])


@app.on_event("startup")
async def startup() -> None:
    log.info("Initialising OmniGraph client...")
    init_client()
    log.info("Loading extraction records...")
    records = load_records()
    log.info("Building graph from cached records...")
    build_graph()
    log.info("Ready — %d records loaded, graph built", len(records))


# Serve the built frontend if the dist folder exists
_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _DIST.exists():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="frontend")
