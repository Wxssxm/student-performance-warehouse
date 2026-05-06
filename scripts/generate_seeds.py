"""Generate synthetic student-performance seeds.

Re-running with the same SEED produces identical files. Output goes to
data/sample/. Tables modelled to exercise SCD2 (student address /
study_time change over time).
"""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = REPO_ROOT / "data" / "sample"
SEED = 42

N_STUDENTS = 80
N_COURSES = 5
N_SCHOOLS = 3
N_GRADES = 600

GENDERS = ["F", "M"]
PARENT_EDU = ["primary", "secondary", "higher", "graduate"]
COURSE_SUBJECTS = [
    ("MAT101", "Mathematics", "STEM", 4),
    ("PHY201", "Physics", "STEM", 4),
    ("LIT301", "French Literature", "Humanities", 3),
    ("ECO101", "Microeconomics", "Social Science", 3),
    ("INF201", "Programming", "STEM", 4),
]
SCHOOLS = [
    ("LYC001", "Lycee Pasteur", "public", "Paris", "Ile-de-France"),
    ("LYC002", "Saint-Louis Prep", "private", "Lyon", "Rhone-Alpes"),
    ("LYC003", "Voltaire Public", "public", "Marseille", "PACA"),
]
EXAM_TYPES = ["quiz", "midterm", "final"]
EXAM_TYPE_WEIGHTS = [40, 35, 25]

CITIES = ["Paris", "Lyon", "Marseille", "Toulouse", "Nice", "Bordeaux"]
FIRST_NAMES = [
    "Adrien",
    "Alice",
    "Baptiste",
    "Camille",
    "Diane",
    "Elias",
    "Farah",
    "Gabriel",
    "Hugo",
    "Ines",
    "Jules",
    "Karim",
    "Lou",
    "Manon",
    "Nadia",
    "Oscar",
    "Paul",
    "Quentin",
    "Rania",
    "Sophie",
    "Tom",
    "Yann",
]
LAST_NAMES = [
    "Martin",
    "Bernard",
    "Dubois",
    "Robert",
    "Richard",
    "Petit",
    "Durand",
    "Leroy",
    "Moreau",
    "Simon",
    "Laurent",
    "Lefebvre",
    "Michel",
    "Garcia",
    "David",
    "Bertrand",
    "Roux",
    "Vincent",
    "Fournier",
]


def main() -> None:
    rng = random.Random(SEED)
    OUT.mkdir(parents=True, exist_ok=True)

    # ----- schools -----
    with (OUT / "schools.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["school_code", "school_name", "school_type", "city", "region"])
        w.writerows(SCHOOLS)

    # ----- courses -----
    with (OUT / "courses.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["course_code", "course_name", "subject_area", "credit_hours"])
        w.writerows(COURSE_SUBJECTS)

    # ----- students v1 (initial enrollment, first semester) -----
    students_v1 = []
    for i in range(1, N_STUDENTS + 1):
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        gender = rng.choice(GENDERS)
        birth = date(2005, 1, 1) + timedelta(days=rng.randint(0, 365 * 2))
        city = rng.choice(CITIES)
        study_hours = rng.choices([2, 5, 10, 15], weights=[20, 40, 30, 10])[0]
        parent_edu = rng.choice(PARENT_EDU)
        students_v1.append(
            (
                f"STU{i:04d}",
                first,
                last,
                gender,
                birth.isoformat(),
                city,
                study_hours,
                parent_edu,
                "2024-09-01",  # valid_from for the v1 row
            )
        )

    with (OUT / "students_v1.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "student_code",
                "first_name",
                "last_name",
                "gender",
                "birth_date",
                "city",
                "study_hours_per_week",
                "parent_education",
                "snapshot_date",
            ]
        )
        w.writerows(students_v1)

    # ----- students v2 (after first semester: ~20% changed something) -----
    students_v2 = []
    for s in students_v1:
        code, first, last, gender, birth, city, study, parent_edu, _ = s
        if rng.random() < 0.20:
            # change city OR study hours OR both
            if rng.random() < 0.5:
                city = rng.choice([c for c in CITIES if c != city])
            if rng.random() < 0.6:
                study = rng.choices([2, 5, 10, 15], weights=[10, 40, 35, 15])[0]
        students_v2.append(
            (code, first, last, gender, birth, city, study, parent_edu, "2025-02-01")
        )

    with (OUT / "students_v2.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "student_code",
                "first_name",
                "last_name",
                "gender",
                "birth_date",
                "city",
                "study_hours_per_week",
                "parent_education",
                "snapshot_date",
            ]
        )
        w.writerows(students_v2)

    # ----- grades -----
    student_codes = [s[0] for s in students_v1]
    course_codes = [c[0] for c in COURSE_SUBJECTS]
    school_codes = [s[0] for s in SCHOOLS]

    grades = []
    base = date(2024, 9, 1)
    for i in range(1, N_GRADES + 1):
        student = rng.choice(student_codes)
        course = rng.choice(course_codes)
        school = rng.choice(school_codes)
        exam_date = base + timedelta(days=rng.randint(0, 270))
        exam_type = rng.choices(EXAM_TYPES, weights=EXAM_TYPE_WEIGHTS, k=1)[0]
        # mean grade 12, sigma 4, clipped to [0, 20]
        raw = max(0.0, min(20.0, rng.gauss(12, 4)))
        grade = round(raw, 1)
        attempt = 1 if rng.random() > 0.05 else 2
        grades.append(
            (i, student, course, school, exam_date.isoformat(), exam_type, grade, attempt)
        )

    with (OUT / "grades.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "grade_id",
                "student_code",
                "course_code",
                "school_code",
                "exam_date",
                "exam_type",
                "grade_value",
                "attempt_number",
            ]
        )
        w.writerows(grades)

    print(
        f"Wrote {N_STUDENTS} students (v1+v2), {N_COURSES} courses, {N_SCHOOLS} schools, "
        f"{N_GRADES} grades to {OUT}/"
    )


if __name__ == "__main__":
    main()
