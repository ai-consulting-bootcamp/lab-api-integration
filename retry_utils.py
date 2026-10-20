
import time
import random
from functools import wraps

from budget_tracker import BudgetExceededError


def retry(max_retries=2, base_delay=1):
    """Retry temporary API failures with exponential backoff."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)

                except BudgetExceededError:
                    # Never retry when the budget is exhausted.
                    raise

                except Exception as error:
                    # Authentication and invalid requests should not retry.
                    status = getattr(error, "status_code", None)

                    if status is not None and status not in (
                        408, 409, 429, 500, 502, 503, 504
                    ):
                        raise

                    if attempt == max_retries:
                        raise

                    delay = base_delay * (2 ** attempt)
                    delay += random.uniform(0, 0.5)

                    print(
                        f"Temporary error: {error}. "
                        f"Retrying in {delay:.1f} seconds..."
                    )

                    time.sleep(delay)

        return wrapper

    return decorator
