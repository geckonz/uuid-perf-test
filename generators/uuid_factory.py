"""UUID generation helpers for v4 (random) and v7 (time-ordered)."""

import uuid

from uuid_extensions import uuid7 as _uuid7_fn


def new_uuid4() -> uuid.UUID:
    """Return a new random UUID v4."""
    return uuid.uuid4()


def new_uuid7() -> uuid.UUID:
    """Return a new time-ordered UUID v7 (RFC 9562).

    Generated sequentially in a single process to guarantee monotonic ordering,
    which is the key property that eliminates B-tree page splits.
    """
    return _uuid7_fn()
