"""ASGI entry point: `uvicorn intentlock.main:app`."""

from intentlock.app import create_app

app = create_app()
