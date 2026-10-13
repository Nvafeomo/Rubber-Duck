from datetime import datetime


def load_daycare_data():
    current_pets = [
        {
            "name": "Milo", "size": "small",
            "dropoff": "08:15", "pickup": "17:45",
            "daily_rate": 48.0, "late_hours": 0.5,
            "late_fee_per_hour": 15.0, "medication": True,
        },
        {
            "name": "Juniper", "size": "large",
            "dropoff": "09:00", "pickup": "18:00",
            "daily_rate": 52.0, "late_hours": 1.25,
            "late_fee_per_hour": 12.0, "medication": False,
        },
        {
            "name": "Otis", "size": "medium",
            "dropoff": "10:00", "pickup": "16:00",
            "daily_rate": 40.0, "late_hours": 0.25,
            "late_fee_per_hour": 10.0, "medication": True,
        },
        {
            "name": "Pepper", "size": "small",
            "dropoff": "08:00", "pickup": "15:30",
            "daily_rate": 44.0, "late_hours": 0.0,
            "late_fee_per_hour": 15.0, "medication": True,
        },
        {
            "name": "Nori", "size": "medium",
            "dropoff": "11:00", "pickup": "17:00",
            "daily_rate": 40.0, "late_hours": 0.0,
            "late_fee_per_hour": 10.0, "medication": False,
        },
        {
            "name": "Basil", "size": "large",
            "dropoff": "08:30", "pickup": "14:00",
            "daily_rate": 52.0, "late_hours": 0.0,
            "late_fee_per_hour": 12.0, "medication": False,
        },
    ]
    tomorrow_bookings = [
        {"name": "Bella", "medication": True},
        {"name": "Lou", "medication": False},
    ]
    return current_pets, tomorrow_bookings


def visit_hours(pet):
    start = datetime.strptime(pet["dropoff"], "%H:%M")
    end = datetime.strptime(pet["pickup"], "%H:%M")
    return (end - start).total_seconds() / 3600


def estimate_late_fees(pets):
    charges = []
    for pet in pets:
        if pet["late_hours"] > 0:
            amount = pet["late_hours"] * pet["daily_rate"]
            charges.append((pet["name"], amount))
    return charges


def medication_check_count(current_pets, tomorrow_bookings):
    count = 0
    for pet in tomorrow_bookings:
        if pet["medication"]:
            count += 1
    return count


def total_care_hours(pets):
    total_hours = sum(visit_hours(pet) for pet in pets)
    longest_visit = max(visit_hours(pet) for pet in pets)
    return longest_visit


def print_report(current_pets, tomorrow_bookings):
    charges = estimate_late_fees(current_pets)
    total_charges = sum(amount for _, amount in charges)
    medication_checks = medication_check_count(current_pets, tomorrow_bookings)
    care_hours = total_care_hours(current_pets)

    print("PET DAYCARE - DAILY OPERATIONS")
    print(f"Dogs currently in care: {len(current_pets)}")
    print("Late pickup charges:")
    if charges:
        for name, amount in charges:
            print(f"  {name}: ${amount:.2f}")
    else:
        print("  None")
    print(f"Total late pickup charges: ${total_charges:.2f}")
    print(f"Medication checks due today: {medication_checks}")
    print(f"Total scheduled care hours: {care_hours:.1f}")


def main():
    current_pets, tomorrow_bookings = load_daycare_data()
    print_report(current_pets, tomorrow_bookings)


if __name__ == "__main__":
    main()
