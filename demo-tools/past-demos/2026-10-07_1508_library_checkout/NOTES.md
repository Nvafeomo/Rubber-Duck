# Current Demo: Library Checkout

Presenter-only: keep this file under `demo-tools/`. Do not move it into `demo/`
or stage it with the demonstration program.

## Program

`library_checkout.py`

## Intent

```text
Charge each member the book's daily fine for every day a loan was returned late, list every member who owes an overdue fine, and report the total and average fine per member.
```

## Answer key

1. **Wrong dictionary key — `calculate_fines`:** The fine is computed as
   `loan["days_out"] * rate`; it should be `loan["days_late"] * rate`. Members
   are charged for every day they had a book, not just the late days.
   **Visible effect:** Chloe Nguyen and Elena Rossi, who returned everything on
   time, show fines of $3.00 and $0.70. Every fine is inflated (Amara $5.40
   instead of $1.00; Ben and Dev hit the $10.00 cap instead of $3.50 and
   $2.50).
2. **Wrong collection in a loop — `find_overdue_members`:** The loop iterates
   over `library["notified"]` (members who already got a notice) instead of
   all members, `fines`. **Visible effect:** "Members with overdue fines" lists
   only Ben Castillo and Dev Patel; Amara Okafor and Farid Haddad are missing.
   The correct count is 4, not 2.
3. **Wrong variable — `summarize`:** The `"average"` entry is set to
   `round(total, 2)` instead of `round(average, 2)`. **Visible effect:**
   "Average per member" equals the total ($32.85 with the other bugs present).

## Correct output, for reference

With all three bugs fixed: Amara $1.00, Ben $3.50, Chloe $0.00, Dev $2.50,
Elena $0.00, Farid $0.25. Four members with overdue fines (Amara, Ben, Dev,
Farid). Total $7.25, average $1.21, highest fine Ben Castillo.
