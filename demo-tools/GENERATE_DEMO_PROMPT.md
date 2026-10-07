Read demo-tools/DEMO_RUNBOOK.md and the folder names in demo-tools/past-demos/. Then create a new RubberDuck demo on a topic that is not used there, such as a library checkout, a shopping cart, inventory restocking, payroll, a gym membership tracker, event ticketing, or a recipe scaler. Vary the domain and data shapes from earlier demos.

Write one readable Python program at demo/<topic>.py (a short snake_case name, for example demo/library_checkout.py). Aim for roughly 80-120 lines. It must run with `python <topic>.py`, use only the standard library, include realistic sample data, and print a useful report. Organize it into a few straightforward functions.

Deliberately seed exactly three subtle logic bugs, one of each kind:
1. Wrong dictionary key: read a valid but incorrect field. Both fields must exist with compatible values, so the program still runs.
2. Wrong collection in a loop: iterate over a different, valid collection than the function's purpose requires, so items are wrongly omitted or included.
3. Wrong variable: use a different in-scope variable than the value just computed, in one calculation or return.

Put each bug in a different function. Make each bug visible in the printed output, while keeping the code free of syntax and runtime errors. Do not add comments, names, or output that hint at the bugs, and do not reveal them in chat.

Then create demo-tools/CURRENT_DEMO.md for the presenter, with these sections:
- Program: the file name.
- Intent: one sentence, on a single line inside a `text` code block, describing what the program should correctly do. Mention the behaviors that the bugs break, but not the bugs themselves.
- Answer key: for each bug, the function, the buggy expression, the correct expression, and the visible effect in the output. Use expressions, not line numbers.

Run the program once to confirm that it works. Do not put anything except the program in demo/, do not edit anything else outside demo/ and demo-tools/CURRENT_DEMO.md, and do not stage or commit anything.
