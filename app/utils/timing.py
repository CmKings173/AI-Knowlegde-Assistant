from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def measure_ms(target: dict[str, int], key: str) -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        target[key] = int((time.perf_counter() - start) * 1000)
