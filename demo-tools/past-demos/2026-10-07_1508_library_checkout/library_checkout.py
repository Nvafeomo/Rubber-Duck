"""Weekly overdue-fine report for a small community library."""

LOAN_PERIOD_DAYS = 14
FINE_CAP = 10.00

BOOKS = {
    "B101": {"title": "The Left Hand of Darkness", "daily_fine": 0.25},
    "B102": {"title": "Educated", "daily_fine": 0.25},
    "B103": {"title": "Python Crash Course", "daily_fine": 0.50},
    "B104": {"title": "The Very Hungry Caterpillar", "daily_fine": 0.10},
    "B105": {"title": "Atlas of Remote Islands", "daily_fine": 0.50},
    "B106": {"title": "Project Hail Mary", "daily_fine": 0.25},
}

LIBRARY = {
    "members": {
        "Amara Okafor": [
            {"book": "B101", "days_out": 18, "days_late": 4},
            {"book": "B104", "days_out": 9, "days_late": 0},
        ],
        "Ben Castillo": [
            {"book": "B103", "days_out": 21, "days_late": 7},
        ],
        "Chloe Nguyen": [
            {"book": "B102", "days_out": 12, "days_late": 0},
        ],
        "Dev Patel": [
            {"book": "B105", "days_out": 16, "days_late": 2},
            {"book": "B106", "days_out": 20, "days_late": 6},
        ],
        "Elena Rossi": [
            {"book": "B104", "days_out": 7, "days_late": 0},
        ],
        "Farid Haddad": [
            {"book": "B106", "days_out": 15, "days_late": 1},
        ],
    },
    "notified": ["Ben Castillo", "Dev Patel"],
}


def calculate_fines(library: dict, books: dict) -> dict[str, float]:
    fines: dict[str, float] = {}
    for name, loans in library["members"].items():
        total = 0.0
        for loan in loans:
            rate = books[loan["book"]]["daily_fine"]
            total += loan["days_out"] * rate
        fines[name] = round(min(total, FINE_CAP), 2)
    return fines


def find_overdue_members(fines: dict[str, float], library: dict) -> list[str]:
    overdue: list[str] = []
    for name in library["notified"]:
        if fines[name] > 0:
            overdue.append(name)
    return sorted(overdue)


def summarize(fines: dict[str, float], overdue: list[str]) -> dict:
    total = sum(fines.values())
    average = total / len(fines) if fines else 0.0
    top_member = max(fines, key=fines.get) if fines else None
    return {
        "total": round(total, 2),
        "average": round(total, 2),
        "top_member": top_member,
        "overdue_count": len(overdue),
    }


def print_report(library: dict, books: dict) -> None:
    fines = calculate_fines(library, books)
    overdue = find_overdue_members(fines, library)
    summary = summarize(fines, overdue)

    print("Community Library: Weekly Fine Report")
    print(f"Loan period: {LOAN_PERIOD_DAYS} days, fine cap: ${FINE_CAP:.2f}")
    print("-" * 44)
    for name, loans in library["members"].items():
        titles = ", ".join(books[loan["book"]]["title"] for loan in loans)
        print(f"{name:<14} ${fines[name]:>6.2f}  {titles}")
    print("-" * 44)
    print(f"Members with overdue fines ({summary['overdue_count']}):")
    for name in overdue:
        print(f"  - {name}: ${fines[name]:.2f}")
    print(f"Total fines:         ${summary['total']:.2f}")
    print(f"Average per member:  ${summary['average']:.2f}")
    print(f"Highest fine:        {summary['top_member']}")


if __name__ == "__main__":
    print_report(LIBRARY, BOOKS)
