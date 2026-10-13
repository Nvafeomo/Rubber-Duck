# Current Demo: Gym Membership

Presenter-only: keep this file under `demo-tools/`. Do not move it into `demo/`
or stage it with the demonstration program.

## Program

`gym_membership.py`

## Intent

```text
Bill each member the plan's monthly fee plus its class fee per class and guest fee per guest, list every member with fewer than 4 visits this month (including members who never visited), and report the busiest day of the week.
```

## Answer key

1. **Wrong dictionary key — `monthly_bill`:** Class charges are computed as
   `member["classes"] * plan["guest_fee"]`; they should use
   `plan["class_fee"]`. **Visible effect:** most bills are wrong. Sofia
   Martinez (premium, where classes are free) is billed $130.00 instead of
   $80.00; Ava $101.00 instead of $89.00; Marcus $50.00 instead of $54.00;
   Zara $50.00 instead of $52.00; Leo $90.00 instead of $70.00. Total $466.00
   instead of $390.00.
2. **Wrong collection in a loop — `find_inactive`:** The loop iterates over
   `visit_counts` instead of `names` (every member). Members who never visited
   have no entry in `visit_counts`, so they are skipped. **Visible effect:**
   the check-in list shows only Marcus Lee and Zara Ahmed; Ethan Wright, with
   0 visits, is missing.
3. **Wrong variable — `busiest_day`:** The function returns `count` instead of
   `day` from `per_day.most_common(1)[0]`. **Visible effect:** "Busiest day"
   prints `9` (the number of visits) instead of `Sat`.

## Correct output, for reference

With all three bugs fixed: Ava $89.00, Marcus $54.00, Sofia $80.00, Ethan
$45.00, Zara $52.00, Leo $70.00; total $390.00. Average visits 5.2. Busiest
day Sat. Fewer than 4 visits: Ethan Wright, Marcus Lee, Zara Ahmed.
