"""Monthly billing and attendance report for a neighborhood gym."""

from collections import Counter

MIN_MONTHLY_VISITS = 4

PLANS = {
    "basic": {"monthly_fee": 30.00, "class_fee": 12.00, "guest_fee": 10.00},
    "plus": {"monthly_fee": 45.00, "class_fee": 6.00, "guest_fee": 8.00},
    "premium": {"monthly_fee": 70.00, "class_fee": 0.00, "guest_fee": 5.00},
}

MEMBERS = [
    {"id": "M01", "name": "Ava Thompson", "plan": "plus", "classes": 6, "guests": 1},
    {"id": "M02", "name": "Marcus Lee", "plan": "basic", "classes": 2, "guests": 0},
    {"id": "M03", "name": "Sofia Martinez", "plan": "premium", "classes": 10, "guests": 2},
    {"id": "M04", "name": "Ethan Wright", "plan": "plus", "classes": 0, "guests": 0},
    {"id": "M05", "name": "Zara Ahmed", "plan": "basic", "classes": 1, "guests": 1},
    {"id": "M06", "name": "Leo Fischer", "plan": "premium", "classes": 4, "guests": 0},
]

VISITS = [
    ("M01", "Mon"), ("M01", "Wed"), ("M01", "Fri"), ("M01", "Sat"), ("M01", "Mon"),
    ("M01", "Wed"), ("M01", "Sat"), ("M01", "Thu"), ("M01", "Sat"),
    ("M02", "Tue"), ("M02", "Sat"), ("M02", "Thu"),
    ("M03", "Mon"), ("M03", "Tue"), ("M03", "Wed"), ("M03", "Thu"), ("M03", "Fri"),
    ("M03", "Sat"), ("M03", "Mon"), ("M03", "Tue"), ("M03", "Wed"), ("M03", "Sat"),
    ("M03", "Sun"), ("M03", "Sat"),
    ("M05", "Sat"), ("M05", "Sun"),
    ("M06", "Mon"), ("M06", "Wed"), ("M06", "Fri"), ("M06", "Sat"), ("M06", "Tue"),
]


def monthly_bill(member: dict, plans: dict) -> float:
    plan = plans[member["plan"]]
    class_charges = member["classes"] * plan["guest_fee"]
    guest_charges = member["guests"] * plan["guest_fee"]
    return plan["monthly_fee"] + class_charges + guest_charges


def count_visits(visits: list[tuple[str, str]]) -> dict[str, int]:
    return dict(Counter(member_id for member_id, _day in visits))


def find_inactive(members: list[dict], visit_counts: dict[str, int]) -> list[str]:
    names = {member["id"]: member["name"] for member in members}
    inactive: list[str] = []
    for member_id in visit_counts:
        if visit_counts.get(member_id, 0) < MIN_MONTHLY_VISITS:
            inactive.append(names[member_id])
    return sorted(inactive)


def busiest_day(visits: list[tuple[str, str]]) -> str:
    per_day = Counter(day for _member_id, day in visits)
    day, count = per_day.most_common(1)[0]
    return count


def print_report(members: list[dict], plans: dict, visits: list[tuple[str, str]]) -> None:
    visit_counts = count_visits(visits)
    inactive = find_inactive(members, visit_counts)
    total = 0.0

    print("Neighborhood Gym: Monthly Report")
    print("=" * 46)
    print(f"{'Member':<16}{'Plan':<9}{'Visits':>7}{'Bill':>12}")
    for member in members:
        bill = monthly_bill(member, plans)
        total += bill
        visits_made = visit_counts.get(member["id"], 0)
        print(f"{member['name']:<16}{member['plan']:<9}{visits_made:>7}{bill:>12.2f}")
    print("-" * 46)
    print(f"Total billed:      ${total:,.2f}")
    print(f"Average visits:    {len(visits) / len(members):.1f}")
    print(f"Busiest day:       {busiest_day(visits)}")
    print(f"Fewer than {MIN_MONTHLY_VISITS} visits (send a check-in email):")
    for name in inactive:
        print(f"  - {name}")


if __name__ == "__main__":
    print_report(MEMBERS, PLANS, VISITS)
