"""Intent-sensitive benchmark for RubberDuck.

Each case is a short, new Python file with a one-line developer intent. The
buggy version differs from the clean version on exactly one line, and that line
is valid, runs, and reads naturally on its own. It is only wrong when compared
with the stated intent. This is the situation RubberDuck targets: an agent
writes a new file from an intent and slips on one detail.

Four cases per bug type. Written before any results were collected.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Case:
    name: str
    bug_type: str
    intent: str
    clean: str
    correct_line: str
    buggy_line: str


CASES = [
    # ---------------- wrong dictionary key ----------------
    Case(
        name="weekly_payroll",
        bug_type="wrong_dict_key",
        intent="Pay each employee for the hours they actually worked this week at their hourly rate, plus 1.5x for hours over 40.",
        clean='''\
def weekly_pay(timesheets):
    """Return a mapping of employee name to gross pay for the week."""
    pay = {}
    for entry in timesheets:
        hours = entry["worked_hours"]
        rate = entry["hourly_rate"]
        regular = min(hours, 40)
        overtime = max(hours - 40, 0)
        pay[entry["name"]] = round(regular * rate + overtime * rate * 1.5, 2)
    return pay


TIMESHEETS = [
    {"name": "Ana", "scheduled_hours": 40, "worked_hours": 44, "hourly_rate": 22.0},
    {"name": "Ben", "scheduled_hours": 32, "worked_hours": 30, "hourly_rate": 18.5},
]

if __name__ == "__main__":
    print(weekly_pay(TIMESHEETS))
''',
        correct_line='        hours = entry["worked_hours"]',
        buggy_line='        hours = entry["scheduled_hours"]',
    ),
    Case(
        name="order_revenue",
        bug_type="wrong_dict_key",
        intent="Report total revenue as the amount customers actually paid after discounts, summed across all line items.",
        clean='''\
def total_revenue(orders):
    """Sum revenue across every line item of every order."""
    revenue = 0.0
    for order in orders:
        for item in order["items"]:
            revenue += item["paid_price"] * item["quantity"]
    return round(revenue, 2)


ORDERS = [
    {"id": 1, "items": [{"sku": "A1", "list_price": 20.0, "paid_price": 16.0, "quantity": 2}]},
    {"id": 2, "items": [{"sku": "B7", "list_price": 9.5, "paid_price": 9.5, "quantity": 3}]},
]

if __name__ == "__main__":
    print(total_revenue(ORDERS))
''',
        correct_line='            revenue += item["paid_price"] * item["quantity"]',
        buggy_line='            revenue += item["list_price"] * item["quantity"]',
    ),
    Case(
        name="course_grades",
        bug_type="wrong_dict_key",
        intent="Compute each student's course grade from their exam scores only; quizzes do not count toward the grade.",
        clean='''\
def course_grades(students):
    """Return each student's average score, rounded to one decimal."""
    grades = {}
    for student in students:
        scores = student["exam_scores"]
        grades[student["name"]] = round(sum(scores) / len(scores), 1)
    return grades


STUDENTS = [
    {"name": "Kofi", "quiz_scores": [70, 75, 80], "exam_scores": [88, 92]},
    {"name": "Mia", "quiz_scores": [95, 90, 98], "exam_scores": [72, 68]},
]

if __name__ == "__main__":
    print(course_grades(STUDENTS))
''',
        correct_line='        scores = student["exam_scores"]',
        buggy_line='        scores = student["quiz_scores"]',
    ),
    Case(
        name="warehouse_restock",
        bug_type="wrong_dict_key",
        intent="List products whose warehouse stock has fallen below their reorder point so the warehouse can restock them.",
        clean='''\
def restock_list(products):
    """Return the SKUs that need to be reordered, sorted."""
    needed = []
    for product in products:
        if product["warehouse_qty"] < product["reorder_point"]:
            needed.append(product["sku"])
    return sorted(needed)


PRODUCTS = [
    {"sku": "LAMP-01", "warehouse_qty": 3, "store_qty": 12, "reorder_point": 5},
    {"sku": "DESK-02", "warehouse_qty": 9, "store_qty": 1, "reorder_point": 4},
]

if __name__ == "__main__":
    print(restock_list(PRODUCTS))
''',
        correct_line='        if product["warehouse_qty"] < product["reorder_point"]:',
        buggy_line='        if product["store_qty"] < product["reorder_point"]:',
    ),
    # ---------------- loop over the wrong collection ----------------
    Case(
        name="membership_renewals",
        bug_type="wrong_loop_collection",
        intent="Send a renewal reminder to every member whose membership expires this month, including members whose accounts are paused.",
        clean='''\
def renewal_reminders(club, month):
    """Return the email addresses that should get a renewal reminder."""
    emails = []
    for member in club["all_members"]:
        if member["expires_month"] == month:
            emails.append(member["email"])
    return emails


CLUB = {
    "all_members": [
        {"email": "ada@example.com", "expires_month": 10, "paused": True},
        {"email": "raj@example.com", "expires_month": 10, "paused": False},
    ],
    "active_members": [
        {"email": "raj@example.com", "expires_month": 10, "paused": False},
    ],
}

if __name__ == "__main__":
    print(renewal_reminders(CLUB, 10))
''',
        correct_line='    for member in club["all_members"]:',
        buggy_line='    for member in club["active_members"]:',
    ),
    Case(
        name="sprint_hours",
        bug_type="wrong_loop_collection",
        intent="Report the total estimated hours for every task in the sprint, both finished and unfinished, plus the hours still open.",
        clean='''\
def sprint_hours(sprint):
    """Return total estimated hours and how many of them are still open."""
    total = 0
    for task in sprint["tasks"]:
        total += task["estimate_hours"]
    remaining = sum(task["estimate_hours"] for task in sprint["open"])
    return {"total_hours": total, "open_hours": remaining}


TASKS = [
    {"title": "Login page", "estimate_hours": 6, "done": True},
    {"title": "Password reset", "estimate_hours": 4, "done": False},
]
SPRINT = {"tasks": TASKS, "open": [task for task in TASKS if not task["done"]]}

if __name__ == "__main__":
    print(sprint_hours(SPRINT))
''',
        correct_line='    for task in sprint["tasks"]:',
        buggy_line='    for task in sprint["open"]:',
    ),
    Case(
        name="attendance_awards",
        bug_type="wrong_loop_collection",
        intent="Give an attendance award to every student on the class roster who attended at least 90% of sessions.",
        clean='''\
def attendance_awards(roster, honor_roll, sessions):
    """Return the names of students who earn the attendance award."""
    winners = []
    for student in roster:
        if student["attended"] / sessions >= 0.9:
            winners.append(student["name"])
    return winners


ROSTER = [
    {"name": "Lena", "attended": 19},
    {"name": "Omar", "attended": 20},
    {"name": "Zoe", "attended": 12},
]
HONOR_ROLL = [ROSTER[0]]

if __name__ == "__main__":
    print(attendance_awards(ROSTER, HONOR_ROLL, 20))
''',
        correct_line='    for student in roster:',
        buggy_line='    for student in honor_roll:',
    ),
    Case(
        name="unpaid_invoices",
        bug_type="wrong_loop_collection",
        intent="Email every customer who has at least one unpaid invoice, regardless of their account tier.",
        clean='''\
def overdue_notices(customers, vip_customers):
    """Return the customer ids that should receive an unpaid-invoice notice."""
    notify = []
    for customer in customers:
        if any(not invoice["paid"] for invoice in customer["invoices"]):
            notify.append(customer["id"])
    return notify


CUSTOMERS = [
    {"id": "C1", "tier": "vip", "invoices": [{"paid": False}]},
    {"id": "C2", "tier": "standard", "invoices": [{"paid": True}, {"paid": False}]},
]
VIPS = [c for c in CUSTOMERS if c["tier"] == "vip"]

if __name__ == "__main__":
    print(overdue_notices(CUSTOMERS, VIPS))
''',
        correct_line='    for customer in customers:',
        buggy_line='    for customer in vip_customers:',
    ),
    # ---------------- wrong variable ----------------
    Case(
        name="library_late_fees",
        bug_type="wrong_variable",
        intent="Charge the rental fee for every day a book was out, and add the late penalty only when it came back more than the grace period after its due date.",
        clean='''\
def checkout_charge(days_out, loan_days=14, daily_rate=0.25, grace_days=2, penalty=5.0):
    """Return the charge for one book checkout and how many days late it was."""
    days_late = max(days_out - loan_days, 0)
    charge = days_out * daily_rate
    if days_late > grace_days:
        charge += penalty
    return {"days_late": days_late, "charge": round(charge, 2)}


if __name__ == "__main__":
    print(checkout_charge(days_out=14))
    print(checkout_charge(days_out=21))
''',
        correct_line='    if days_late > grace_days:',
        buggy_line='    if days_out > grace_days:',
    ),
    Case(
        name="free_shipping",
        bug_type="wrong_variable",
        intent="Give free shipping when the order subtotal before tax is at least $50; otherwise charge a flat $6.99.",
        clean='''\
def checkout_total(subtotal, tax_rate=0.08):
    """Return the shipping charge and the final amount due."""
    tax = subtotal * tax_rate
    total = subtotal + tax
    shipping = 0.0 if subtotal >= 50 else 6.99
    return {"shipping": shipping, "amount_due": round(total + shipping, 2)}


if __name__ == "__main__":
    print(checkout_total(47.0))
    print(checkout_total(55.0))
''',
        correct_line='    shipping = 0.0 if subtotal >= 50 else 6.99',
        buggy_line='    shipping = 0.0 if total >= 50 else 6.99',
    ),
    Case(
        name="player_rankings",
        bug_type="wrong_variable",
        intent="Rank players by their average points per game, highest first, and show each player's season total next to it.",
        clean='''\
def rank_players(games_by_player):
    """Return (name, average, total) rows, best player first."""
    rows = []
    for name, points in games_by_player.items():
        total = sum(points)
        average = total / len(points)
        rows.append((name, round(average, 1), total))
    rows.sort(key=lambda row: row[1], reverse=True)
    return rows


GAMES = {"Ike": [30, 28, 32], "Jo": [20, 22, 18, 25, 21], "Kai": [27, 29]}

if __name__ == "__main__":
    print(rank_players(GAMES))
''',
        correct_line='    rows.sort(key=lambda row: row[1], reverse=True)',
        buggy_line='    rows.sort(key=lambda row: row[2], reverse=True)',
    ),
    Case(
        name="heat_alerts",
        bug_type="wrong_variable",
        intent="Raise a heat alert for any day whose high temperature is above the alert threshold, and report each day's high and low.",
        clean='''\
def heat_report(readings, threshold=95):
    """Return one line per day with its high, low, and whether to alert."""
    lines = []
    for day, temps in readings.items():
        high = max(temps)
        low = min(temps)
        alert = high > threshold
        lines.append(f"{day}: high {high}, low {low}, alert={alert}")
    return lines


READINGS = {"Mon": [78, 97, 88], "Tue": [96, 99, 97], "Wed": [70, 84, 80]}

if __name__ == "__main__":
    print("\\n".join(heat_report(READINGS)))
''',
        correct_line='        alert = high > threshold',
        buggy_line='        alert = low > threshold',
    ),
]


def buggy_source(case: Case) -> str:
    lines = case.clean.splitlines()
    hits = [i for i, line in enumerate(lines) if line == case.correct_line]
    if len(hits) != 1:
        raise ValueError(f"{case.name}: correct_line must appear exactly once")
    lines[hits[0]] = case.buggy_line
    return "\n".join(lines) + "\n"


def bug_line_number(case: Case) -> int:
    lines = case.clean.splitlines()
    return lines.index(case.correct_line) + 1
