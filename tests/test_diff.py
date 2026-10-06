from rubberduck.diff import changed_lines


def test_added_and_replaced_lines_are_marked():
    diff = """\
diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1,4 +1,5 @@
 line1
-line2
+line2 changed
 line3
+inserted
 line4
"""
    assert changed_lines(diff) == {2, 4}


def test_new_file_marks_every_added_line():
    diff = """\
diff --git a/a.py b/a.py
--- /dev/null
+++ b/a.py
@@ -0,0 +1,2 @@
+def ready():
+    return 1
"""
    assert changed_lines(diff) == {1, 2}


def test_deletion_only_hunk_has_no_new_line():
    diff = """\
@@ -2,2 +2,1 @@
 kept
-removed
"""
    assert changed_lines(diff) == set()


def test_hunk_without_counts():
    diff = """\
@@ -1 +1 @@
-old
+new
"""
    assert changed_lines(diff) == {1}
