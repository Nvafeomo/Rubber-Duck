# Current Demo: Gradebook

Presenter-only: keep this file under `demo-tools/`. Do not move it into `demo/`
or stage it with the demonstration program.

## Program

`gradebook.py`

## Intent

```text
Calculate each student's course average using 40% homework and 60% exam scores, find every enrolled student at or above the 70% threshold, and report the student with the highest average.
```

## Answer key

1. **Wrong dictionary key — `calculate_averages`:** The value assigned to
   `exam_average` is calculated from `record["homework"]`; it should use
   `record["exams"]`. As a result, exam performance has no effect on course
   averages. The displayed course averages are based on homework alone.
2. **Wrong collection in a loop — `find_passing_students`:** The function
   iterates over `course["tutoring"]` instead of all enrolled students (the
   keys in `averages`). This leaves passing students who are not in the tutoring
   list off the passing roster and out of the passing count.
3. **Wrong variable — `summarize`:** The `"top_student"` result is set to
   `top_average` rather than `top_student`. The report prints the highest
   numeric average where a student's name should appear.
