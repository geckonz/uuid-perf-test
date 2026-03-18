"""UUID generation helpers for v4 (random) and v7 (time-ordered)."""

from datetime import datetime
import uuid

from uuid_extensions import uuid7 as _uuid7_fn


def new_uuid4(*args, **kwargs) -> uuid.UUID:
    """Return a new random UUID v4. Arguments are ignored for compatibility."""
    return uuid.uuid4()


def new_uuid7(dt: datetime | None = None) -> uuid.UUID:
    """Return a new time-ordered UUID v7 (RFC 9562).

    If dt is provided, generate a UUIDv7 for that specific timestamp.
    Otherwise, generate a current monotonic UUID.
    """
    if dt:
        # uuid_extensions.uuid7 expects nanoseconds as first argument
        # dt.timestamp() returns seconds as float
        ns = int(dt.timestamp() * 1_000_000_000)
        return _uuid7_fn(ns)
    return _uuid7_fn()
