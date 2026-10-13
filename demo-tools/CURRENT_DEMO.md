# Current Demo

## Program

`payroll.py`

## Intent

```text
Calculate each employee's weekly gross and take-home pay from regular and overtime hours, then report the complete employee gross payroll totals by department.
```

## Answer key

1. **Function:** `weekly_gross`  
   **Buggy expression:** `worker["regular_hours"] * worker["hourly_rate"] * worker["overtime_multiplier"]`  
   **Correct expression:** `worker["overtime_hours"] * worker["hourly_rate"] * worker["overtime_multiplier"]`  
   **Visible effect:** Gross pay is overstated in the employee rows and in the employee gross payroll grand total.

2. **Function:** `department_payroll`  
   **Buggy expression:** `for worker in contractors:`  
   **Correct expression:** `for worker in workers:`  
   **Visible effect:** The department report shows only contractor costs for Cafe and Garden and omits the employee payroll totals, including the Repairs department.

3. **Function:** `take_home_pay`  
   **Buggy expression:** `return gross`  
   **Correct expression:** `return take_home`  
   **Visible effect:** Each employee's displayed take-home pay equals their gross pay instead of reflecting withholding and benefit deductions.
