# Past Demo: Weekly Payroll

This is the demo shown in the final report (Listing 3 and Figures 2-3).

## Program

`payroll.py` (the version here still has the three seeded bugs)

## Intent

```text
Calculate each employee's weekly gross pay from regular and overtime hours, their take-home pay after withholding and benefits, and the employee payroll total for each department.
```

## Answer key

1. **Line 74, wrong dictionary key (`weekly_gross`):** overtime pay uses
   `worker["regular_hours"]`; it should use `worker["overtime_hours"]`.
2. **Line 86, wrong variable (`take_home_pay`):** returns `gross`; it should
   return `take_home`.
3. **Line 91, wrong loop collection (`department_payroll`):** loops over
   `contractors`; it should loop over `workers`.

RubberDuck flagged all three lines on the first commit and passed the fixed
version on the second.
