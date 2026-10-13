# Past Demo: Pet Daycare

## Program

`pet_daycare.py`

## Intent

```text
Calculate late pickup charges from each dog's late hours and fee rate, count medication checks for dogs currently in care, and report their total scheduled care hours.
```

## Answer key

1. **Function:** `estimate_late_fees`
   - **Buggy expression:** `pet["late_hours"] * pet["daily_rate"]`
   - **Correct expression:** `pet["late_hours"] * pet["late_fee_per_hour"]`
   - **Visible effect:** The individual and total late pickup charges are overstated.
2. **Function:** `medication_check_count`
   - **Buggy expression:** `for pet in tomorrow_bookings`
   - **Correct expression:** `for pet in current_pets`
   - **Visible effect:** The report counts tomorrow's medication checks instead of today's.
3. **Function:** `total_care_hours`
   - **Buggy expression:** `return longest_visit`
   - **Correct expression:** `return total_hours`
   - **Visible effect:** The report shows only the longest visit as the total scheduled care hours.
