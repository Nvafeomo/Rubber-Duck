# Current Demo: Event Ticketing

Presenter-only: keep this file under `demo-tools/`. Do not move it into `demo/`
or stage it with the demonstration program.

## Program

`event_ticketing.py`

## Intent

```text
Charge each paid order the section price plus service fee for every ticket bought, total revenue by section, list every paid buyer who did not use all their tickets, and report the no-show rate as a percentage of tickets sold.
```

## Answer key

1. **Wrong dictionary key — `order_total`:** The total is
   `order["scanned"] * per_ticket`; it should be `order["quantity"] * per_ticket`.
   Buyers are charged only for tickets that were scanned at the door, not for
   every ticket they bought.
   **Visible effect:** revenue is understated in every section (floor $357.50
   instead of $429.00, balcony $148.50 instead of $297.00, lawn $168.00 instead
   of $196.00; total $674.00 instead of $922.00).
2. **Wrong collection in a loop — `find_no_shows`:** The loop iterates over
   `event["refunded"]` instead of `event["orders"]`.
   **Visible effect:** "Buyers with unused tickets" lists only the refunded
   buyers (Priya Raman, Noah Brooks), who shouldn't appear at all. The real
   no-shows are missing: Jordan Ellis (1 of 4), Lucia Ferreira (1 of 5),
   Hana Sato (1 of 3), and Grace Kim (2 of 2).
3. **Wrong variable — `summarize`:** The `"no_show_rate"` entry is set to
   `no_shows` (a count) instead of `no_show_rate` (the fraction computed on the
   line before). **Visible effect:** "No-show rate" prints 500.0% instead of
   26.3% (5 of 19 tickets).

## Correct output, for reference

With all three bugs fixed: floor $429.00, balcony $297.00, lawn $196.00, total
$922.00. Tickets sold 19 of 220 seats, checked in 14, no-show rate 26.3%.
Buyers with unused tickets: Jordan Ellis, Lucia Ferreira, Hana Sato, Grace Kim.
