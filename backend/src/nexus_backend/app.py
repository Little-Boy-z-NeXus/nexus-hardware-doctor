"""Minimal API entry point for the NeXus backend."""

from fastapi import FastAPI

from nexus_backend import __version__

app = FastAPI(title="nexus-backend", version=__version__)


@app.get("/health")
def health() -> dict[str, str]:
    """Return a dependency-free process health signal."""
    return {"status": "ok", "service": "nexus-backend", "version": __version__}
