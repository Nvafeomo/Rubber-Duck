from collections import defaultdict


EMPLOYEES = [
    {
        "name": "Maya Chen",
        "department": "Cafe",
        "regular_hours": 38,
        "overtime_hours": 4,
        "hourly_rate": 22.50,
        "overtime_multiplier": 1.5,
        "withholding_rate": 0.18,
        "benefit_deduction": 32.00,
    },
    {
        "name": "Luis Ortega",
        "department": "Garden",
        "regular_hours": 40,
        "overtime_hours": 0,
        "hourly_rate": 19.25,
        "overtime_multiplier": 1.5,
        "withholding_rate": 0.16,
        "benefit_deduction": 24.00,
    },
    {
        "name": "Priya Nair",
        "department": "Cafe",
        "regular_hours": 36,
        "overtime_hours": 2,
        "hourly_rate": 24.00,
        "overtime_multiplier": 1.5,
        "withholding_rate": 0.20,
        "benefit_deduction": 36.00,
    },
    {
        "name": "Evan Brooks",
        "department": "Repairs",
        "regular_hours": 40,
        "overtime_hours": 5,
        "hourly_rate": 27.50,
        "overtime_multiplier": 1.5,
        "withholding_rate": 0.19,
        "benefit_deduction": 28.00,
    },
]

CONTRACTORS = [
    {
        "name": "Northside Cleaning",
        "department": "Cafe",
        "regular_hours": 6,
        "overtime_hours": 0,
        "hourly_rate": 31.00,
        "overtime_multiplier": 1.5,
        "withholding_rate": 0.10,
        "benefit_deduction": 0.00,
    },
    {
        "name": "Greenway Seasonal Help",
        "department": "Garden",
        "regular_hours": 12,
        "overtime_hours": 0,
        "hourly_rate": 26.00,
        "overtime_multiplier": 1.5,
        "withholding_rate": 0.10,
        "benefit_deduction": 0.00,
    },
]


def weekly_gross(worker):
    regular_pay = worker["regular_hours"] * worker["hourly_rate"]
    overtime_pay = (
        worker["regular_hours"]
        * worker["hourly_rate"]
        * worker["overtime_multiplier"]
    )
    return regular_pay + overtime_pay


def take_home_pay(worker):
    gross = weekly_gross(worker)
    withholding = gross * worker["withholding_rate"]
    benefits = worker["benefit_deduction"]
    take_home = gross - withholding - benefits
    return gross


def department_payroll(workers, contractors):
    totals = defaultdict(float)
    for worker in contractors:
        totals[worker["department"]] += weekly_gross(worker)
    return totals


def print_payroll():
    print("WEEKLY PAYROLL")
    print(f"{'Employee':<18} {'Department':<12} {'Gross':>10} {'Take-home':>12}")
    print("-" * 55)
    for employee in EMPLOYEES:
        gross = weekly_gross(employee)
        net = take_home_pay(employee)
        print(
            f"{employee['name']:<18} {employee['department']:<12} "
            f"${gross:>9,.2f} ${net:>11,.2f}"
        )

    totals = department_payroll(EMPLOYEES, CONTRACTORS)
    print("\nEMPLOYEE PAYROLL BY DEPARTMENT")
    for department in sorted(totals):
        print(f"{department:<12} ${totals[department]:>9,.2f}")

    grand_total = sum(weekly_gross(employee) for employee in EMPLOYEES)
    print(f"\nEmployee gross payroll: ${grand_total:,.2f}")


if __name__ == "__main__":
    print_payroll()
