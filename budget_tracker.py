
import json
from datetime import date
from pathlib import Path

from config import DAILY_BUDGET


BUDGET_FILE = Path(__file__).with_name("budget_usage.json")


class BudgetExceededError(RuntimeError):
    """Raised when the daily API budget is exhausted."""
    pass


def get_spending():
    """Return today's recorded estimated spending."""

    if not BUDGET_FILE.exists():
        return 0.0

    data = json.loads(BUDGET_FILE.read_text())

    if data.get("date") != date.today().isoformat():
        return 0.0

    return float(data.get("spent", 0.0))


def record_cost(cost):
    """Record estimated API spending."""

    if cost < 0:
        raise ValueError("Cost cannot be negative.")

    total = get_spending() + cost

    BUDGET_FILE.write_text(
        json.dumps(
            {
                "date": date.today().isoformat(),
                "spent": total
            },
            indent=2
        )
    )

    print(f"Daily estimated spending: ${total:.6f}")

    return total


def check_budget():
    """Block new requests after reaching the daily budget."""

    spent = get_spending()

    if spent >= DAILY_BUDGET:
        raise BudgetExceededError(
            f"Daily budget exhausted: "
            f"${spent:.4f} / ${DAILY_BUDGET:.2f}"
        )

    return True
