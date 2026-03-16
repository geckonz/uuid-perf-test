"""Account-per-customer count distribution generator.

Produces a NumPy array where each element is the number of accounts for
that customer index. The distribution sums to exactly NUM_ACCOUNTS.
"""

import numpy as np

from config.settings import ACCOUNT_DISTRIBUTION, NUM_ACCOUNTS, NUM_CUSTOMERS


def build_account_counts(
    num_customers: int = NUM_CUSTOMERS,
    num_accounts: int = NUM_ACCOUNTS,
    distribution: dict[int, float] | None = None,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Return an int array of length num_customers with account counts.

    The array values follow the given distribution (keys = account counts,
    values = fractions of customers) and sum to exactly num_accounts.
    """
    if distribution is None:
        distribution = ACCOUNT_DISTRIBUTION
    if rng is None:
        rng = np.random.default_rng(42)

    counts = sorted(distribution.keys())
    probs = np.array([distribution[c] for c in counts], dtype=float)
    probs /= probs.sum()  # normalise in case of rounding

    # Assign each customer a count drawn from the distribution
    assigned = rng.choice(counts, size=num_customers, p=probs)

    # Adjust to hit the exact total
    current_total = int(assigned.sum())
    delta = num_accounts - current_total

    if delta > 0:
        # Need more accounts: add 1 to random customers (no upper cap in plan)
        indices = rng.choice(num_customers, size=delta, replace=True)
        for idx in indices:
            assigned[idx] += 1
    elif delta < 0:
        # Need fewer accounts: subtract 1 from customers with count > 1
        candidates = np.where(assigned > 1)[0]
        need = abs(delta)
        # If not enough candidates, iterate until resolved
        while need > 0 and len(candidates) > 0:
            take = min(need, len(candidates))
            chosen = rng.choice(candidates, size=take, replace=False)
            assigned[chosen] -= 1
            need -= take
            candidates = np.where(assigned > 1)[0]

    return assigned
