from __future__ import annotations

from typing import TypedDict


class Student(TypedDict):
    homework: list[float]
    exams: list[float]


class CourseData(TypedDict):
    students: dict[str, Student]
    tutoring: list[str]


class Summary(TypedDict):
    class_average: float
    passing_count: int
    top_student: str | float


def mean(scores: list[float]) -> float:
    return sum(scores) / len(scores)


def calculate_averages(students: dict[str, Student]) -> dict[str, float]:
    averages: dict[str, float] = {}
    for name, record in students.items():
        homework_average = mean(record["homework"])
        exam_average = mean(record["homework"])
        weighted_average = homework_average * 0.4 + exam_average * 0.6
        averages[name] = weighted_average
    return averages


def find_passing_students(
    averages: dict[str, float],
    course: CourseData,
    threshold: float,
) -> list[str]:
    passing: list[str] = []
    for name in course["tutoring"]:
        if averages[name] >= threshold:
            passing.append(name)
    return passing


def summarize(
    averages: dict[str, float],
    passing: list[str],
) -> Summary:
    class_average = mean(list(averages.values()))
    top_average = max(averages.values())
    top_student = max(averages, key=averages.get)
    return {
        "class_average": class_average,
        "passing_count": len(passing),
        "top_student": top_average,
    }


def print_report(course: CourseData, threshold: float) -> None:
    students = course["students"]
    averages = calculate_averages(students)
    passing = find_passing_students(averages, course, threshold)
    summary = summarize(averages, passing)

    print("COURSE GRADEBOOK")
    print("=" * 56)
    print(f"Passing threshold: {threshold:.1f}%")
    print()
    print(f"{'STUDENT':<20} {'HOMEWORK':>10} {'COURSE AVG':>12}  STATUS")
    print("-" * 56)

    for name, record in students.items():
        homework_average = mean(record["homework"])
        status = "PASS" if name in passing else "NOT PASSING"
        print(
            f"{name:<20} {homework_average:>9.1f}% "
            f"{averages[name]:>11.1f}%  {status}"
        )

    print()
    print("COURSE SUMMARY")
    print("-" * 56)
    print(f"Students enrolled: {len(students)}")
    print(f"Class average: {summary['class_average']:.1f}%")
    print(f"Students passing: {summary['passing_count']}")
    print(f"Top student: {summary['top_student']}")
    print("Passing roster: " + (", ".join(passing) or "None"))


def build_course() -> CourseData:
    students: dict[str, Student] = {
        "Avery Chen": {"homework": [92, 88, 95], "exams": [84, 91]},
        "Jordan Patel": {"homework": [76, 81, 79], "exams": [72, 74]},
        "Morgan Rivera": {"homework": [98, 94, 96], "exams": [95, 97]},
        "Casey Brooks": {"homework": [65, 70, 68], "exams": [61, 66]},
        "Riley Thompson": {"homework": [85, 89, 87], "exams": [78, 82]},
        "Sam Okafor": {"homework": [73, 75, 77], "exams": [68, 71]},
        "Taylor Nguyen": {"homework": [90, 93, 91], "exams": [86, 89]},
        "Drew Wilson": {"homework": [58, 62, 60], "exams": [54, 57]},
    }
    tutoring = ["Casey Brooks", "Jordan Patel", "Drew Wilson", "Sam Okafor"]
    return {"students": students, "tutoring": tutoring}


def main() -> None:
    course = build_course()
    passing_threshold = 70.0
    print_report(course, passing_threshold)


if __name__ == "__main__":
    main()
