import asyncio
import functools
from typing import Any, Callable, Coroutine

def run_async(f: Callable[..., Coroutine[Any, Any, Any]]) -> Callable[..., Any]:
    """Decorator that runs an async Typer command with asyncio.run()."""
    @functools.wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return asyncio.run(f(*args, **kwargs))
    return wrapper
