"""Faker-based field generation for customers and accounts (no IDs)."""

import random
import uuid
from datetime import datetime, timezone

from faker import Faker

_faker = Faker()
_faker.seed_instance(0)

# Monotonic counter for O(1) guaranteed-unique emails (avoids Faker's
# uniqueness dedup which becomes O(n) and crashes at ~3-4M rows).
_email_counter = 0

ACCOUNT_TYPES = ("checking", "savings", "credit", "investment")
CURRENCIES = ("USD", "EUR", "GBP", "CAD", "AUD")
STATUSES = ("active", "inactive", "frozen", "closed")

# Epoch range for created_at: 2018-01-01 → 2024-01-01
_EPOCH_START = int(datetime(2018, 1, 1, tzinfo=timezone.utc).timestamp())
_EPOCH_END = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp())


def _rand_ts() -> datetime:
    ts = random.randint(_EPOCH_START, _EPOCH_END)
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def customer_fields() -> tuple[dict, datetime]:
    """Return a (dict, datetime) of customer fields (excluding id)."""
    global _email_counter
    _email_counter += 1
    created = _rand_ts()
    # Compose email from Faker user_name + monotonic counter to guarantee
    # uniqueness in O(1) across any number of rows.
    local = _faker.user_name()
    domain = _faker.free_email_domain()
    email = f"{local}{_email_counter}@{domain}"
    fields = {
        "name": _faker.name(),
        "email": email,
        "phone": _faker.phone_number()[:30],
        "address": _faker.address().replace("\n", " "),
        "created_at": created.isoformat(),
        "updated_at": created.isoformat(),
    }
    return fields, created


def account_fields() -> tuple[dict, datetime]:
    """Return a (dict, datetime) of account fields (excluding id and customer_id)."""
    opened = _rand_ts()
    fields = {
        "account_type": random.choice(ACCOUNT_TYPES),
        "balance": round(random.uniform(-10_000, 500_000), 2),
        "currency": random.choice(CURRENCIES),
        "status": random.choice(STATUSES),
        "opened_at": opened.isoformat(),
        "updated_at": opened.isoformat(),
    }
    return fields, opened
