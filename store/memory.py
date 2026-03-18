from __future__ import annotations

import sys
from collections import deque
from typing import Any


ATOMIC_TYPES = (
    bytes,
    bytearray,
    str,
    int,
    float,
    bool,
    complex,
    type(None),
)


def deep_getsizeof(obj: Any, seen: set[int] | None = None) -> int:
    if seen is None:
        seen = set()

    object_id = id(obj)
    if object_id in seen:
        return 0
    seen.add(object_id)

    size = sys.getsizeof(obj)

    if isinstance(obj, ATOMIC_TYPES):
        return size

    if isinstance(obj, dict):
        for key, value in obj.items():
            size += deep_getsizeof(key, seen)
            size += deep_getsizeof(value, seen)
        return size

    if isinstance(obj, (list, tuple, set, frozenset, deque)):
        for item in obj:
            size += deep_getsizeof(item, seen)
        return size

    if hasattr(obj, "__dict__"):
        size += deep_getsizeof(vars(obj), seen)

    slots = getattr(obj.__class__, "__slots__", ())
    if isinstance(slots, str):
        slots = (slots,)

    for slot in slots:
        if slot in ("__dict__", "__weakref__"):
            continue
        if hasattr(obj, slot):
            size += deep_getsizeof(getattr(obj, slot), seen)

    return size
