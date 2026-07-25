"""Shared CLI utilities for Kactus packages.

Provides :class:`AsyncTyper` for async command support and
:func:`exit_with_error` for stylized error exits.
"""

import asyncio
import functools
from typing import Any, Callable, Optional

import typer
from typer.models import CommandFunctionType


class AsyncTyper(typer.Typer):
    """Typer subclass that transparently supports ``async def`` commands."""

    def command(
        self, name: Optional[str] = None, *args, **kwargs
    ) -> Callable[[CommandFunctionType], CommandFunctionType]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            fn = func
            if asyncio.iscoroutinefunction(func):

                @functools.wraps(func)
                def sync_wrapper(*inner_args: Any, **inner_kwargs: Any) -> Any:
                    asyncio.run(func(*inner_args, **inner_kwargs))

                fn = sync_wrapper

            return super(AsyncTyper, self).command(name=name, *args, **kwargs)(fn)

        return decorator


def exit_with_error(message: str, code: int = 1, **kwargs) -> None:
    """Print a stylized error message and exit with a non-zero code."""
    kwargs.setdefault("fg", typer.colors.RED)
    typer.secho(message, **kwargs)
    raise typer.Exit(code)
