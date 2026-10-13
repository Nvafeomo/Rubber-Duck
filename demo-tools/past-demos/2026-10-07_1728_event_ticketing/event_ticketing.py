"""Box-office report for a one-night concert."""

EVENT_NAME = "Riverside Jazz Night"

SECTIONS = {
    "floor": {"price": 65.00, "service_fee": 6.50, "capacity": 40},
    "balcony": {"price": 45.00, "service_fee": 4.50, "capacity": 60},
    "lawn": {"price": 25.00, "service_fee": 3.00, "capacity": 120},
}

EVENT = {
    "orders": [
        {"id": "T1001", "buyer": "Maya Chen", "section": "floor", "quantity": 2, "scanned": 2},
        {"id": "T1002", "buyer": "Jordan Ellis", "section": "balcony", "quantity": 4, "scanned": 3},
        {"id": "T1004", "buyer": "Sam Okoro", "section": "floor", "quantity": 1, "scanned": 1},
        {"id": "T1005", "buyer": "Lucia Ferreira", "section": "lawn", "quantity": 5, "scanned": 4},
        {"id": "T1007", "buyer": "Hana Sato", "section": "floor", "quantity": 3, "scanned": 2},
        {"id": "T1008", "buyer": "Diego Alvarez", "section": "lawn", "quantity": 2, "scanned": 2},
        {"id": "T1009", "buyer": "Grace Kim", "section": "balcony", "quantity": 2, "scanned": 0},
    ],
    "refunded": [
        {"id": "T1003", "buyer": "Priya Raman", "section": "lawn", "quantity": 3, "scanned": 0},
        {"id": "T1006", "buyer": "Noah Brooks", "section": "balcony", "quantity": 2, "scanned": 0},
    ],
}


def order_total(order: dict, sections: dict) -> float:
    section = sections[order["section"]]
    per_ticket = section["price"] + section["service_fee"]
    return order["quantity"] * per_ticket


def section_revenue(event: dict, sections: dict) -> dict[str, float]:
    revenue = {name: 0.0 for name in sections}
    for order in event["orders"]:
        revenue[order["section"]] += order_total(order, sections)
    return revenue


def find_no_shows(event: dict) -> list[str]:
    no_shows: list[str] = []
    for order in event["refunded"]:
        missing = order["quantity"] - order["scanned"]
        if missing > 0:
            no_shows.append(f"{order['buyer']} ({missing} of {order['quantity']})")
    return no_shows


def summarize(event: dict, sections: dict) -> dict:
    tickets_sold = sum(order["quantity"] for order in event["orders"])
    attended = sum(order["scanned"] for order in event["orders"])
    no_shows = tickets_sold - attended
    no_show_rate = no_shows / tickets_sold if tickets_sold else 0.0
    capacity = sum(section["capacity"] for section in sections.values())
    return {
        "tickets_sold": tickets_sold,
        "attended": attended,
        "capacity": capacity,
        "no_show_rate": no_shows,
    }


def print_report(event: dict, sections: dict) -> None:
    revenue = section_revenue(event, sections)
    no_shows = find_no_shows(event)
    summary = summarize(event, sections)

    print(f"{EVENT_NAME}: Box-Office Report")
    print("=" * 40)
    print("Revenue by section:")
    for name, amount in revenue.items():
        print(f"  {name:<8} ${amount:>9,.2f}")
    print(f"  {'total':<8} ${sum(revenue.values()):>9,.2f}")
    print("-" * 40)
    print(f"Tickets sold:  {summary['tickets_sold']} of {summary['capacity']} seats")
    print(f"Checked in:    {summary['attended']}")
    print(f"No-show rate:  {summary['no_show_rate']:.1%}")
    print("Buyers with unused tickets:")
    for entry in no_shows:
        print(f"  - {entry}")


if __name__ == "__main__":
    print_report(EVENT, SECTIONS)
