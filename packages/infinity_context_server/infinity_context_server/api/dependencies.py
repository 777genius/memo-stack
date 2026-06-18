"""FastAPI dependency helpers."""

from fastapi import Request

from infinity_context_server.composition import Container


def get_container(request: Request) -> Container:
    return request.app.state.container
