"""KactusAPIRouter — auto-wraps endpoint responses in ``ResponseModel``.

Inspired by ``reorc-flow-server/app/_internal/router.py``.

Usage::

    from kactus_common.router import KactusAPIRouter

    router = KactusAPIRouter(prefix="/api/projects", tags=["projects"])

    @router.get("")
    async def list_projects(...) -> Pagination[ProjectSchema]:
        return Pagination(total=len(items), items=items)

    # Response is auto-wrapped as ResponseModel(data=Pagination(...))
"""

from __future__ import annotations

import inspect
import sys
from collections.abc import Callable
from typing import Any, get_type_hints

from fastapi import APIRouter
from fastapi.datastructures import DefaultPlaceholder
from kactus_common.schemas import ResponseModel


class KactusAPIRouter(APIRouter):
    """APIRouter subclass that auto-wraps endpoint returns in ``ResponseModel``.

    The wrapper is skipped when:
    * ``response_model`` is explicitly set to a non-default value.
    * ``response_class`` is explicitly set (e.g. ``FileResponse``).
    """

    def add_api_route(
        self, path: str, endpoint: Callable[..., Any], **kwargs: Any
    ) -> None:
        # --- Skip wrapping if response_model is explicitly set ---------------
        response_model = kwargs.get("response_model")
        if response_model is not None and not isinstance(
            response_model, DefaultPlaceholder
        ):
            return super().add_api_route(path, endpoint, **kwargs)

        # --- Skip wrapping for custom response classes -----------------------
        response_class = kwargs.get("response_class")
        if response_class is not None and not isinstance(
            response_class, DefaultPlaceholder
        ):
            return super().add_api_route(path, endpoint, **kwargs)

        # --- Infer return type and wrap --------------------------------------
        # Use the endpoint's module globals for resolving stringified annotations
        # (needed when endpoint module uses `from __future__ import annotations`)
        module = sys.modules.get(endpoint.__module__, None)
        globalns = getattr(module, "__dict__", None)
        try:
            hints = get_type_hints(endpoint, globalns=globalns)
        except Exception:
            hints = {}
        return_type = hints.get("return")

        if return_type is None:
            # Cannot infer return type — skip wrapping
            return super().add_api_route(path, endpoint, **kwargs)

        kwargs["response_model"] = ResponseModel[return_type]

        # Build the wrapper inside the endpoint's module namespace so FastAPI
        # can resolve stringified annotations (from __future__ import annotations).
        wrapper_ns: dict[str, Any] = {
            "_real_endpoint": endpoint,
            "_ResponseModel": ResponseModel,
        }
        if module is not None:
            wrapper_ns.update(module.__dict__)

        exec(
            "async def wrapped_endpoint(*args, **kwargs):\n"
            "    result = await _real_endpoint(*args, **kwargs)\n"
            "    return _ResponseModel(data=result)\n",
            wrapper_ns,
        )
        actual_wrapper = wrapper_ns["wrapped_endpoint"]

        # Preserve the original function metadata for OpenAPI docs
        actual_wrapper.__module__ = endpoint.__module__
        actual_wrapper.__qualname__ = endpoint.__qualname__
        actual_wrapper.__name__ = endpoint.__name__
        actual_wrapper.__doc__ = endpoint.__doc__
        actual_wrapper.__signature__ = inspect.signature(endpoint)

        return super().add_api_route(path, actual_wrapper, **kwargs)
