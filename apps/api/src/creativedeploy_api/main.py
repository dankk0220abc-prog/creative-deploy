"""ASGI application entry point."""

from creativedeploy_api.app_factory import create_app

app = create_app()
