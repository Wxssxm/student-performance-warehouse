-- Fact table: one row per graded exam.
CREATE TABLE warehouse.fact_grades (
    grade_id          BIGINT PRIMARY KEY,                 -- natural key from source
    student_sk        BIGINT NOT NULL REFERENCES warehouse.dim_student(student_sk),
    course_sk         INTEGER NOT NULL REFERENCES warehouse.dim_course(course_sk),
    school_sk         INTEGER NOT NULL REFERENCES warehouse.dim_school(school_sk),
    exam_date_sk      INTEGER NOT NULL REFERENCES warehouse.dim_date(date_sk),
    exam_type         TEXT NOT NULL CHECK (exam_type IN ('quiz', 'midterm', 'final')),
    grade_value       NUMERIC(4, 1) NOT NULL CHECK (grade_value BETWEEN 0 AND 20),
    grade_letter      CHAR(1) NOT NULL,
    is_passing        BOOLEAN NOT NULL,
    attempt_number    SMALLINT NOT NULL CHECK (attempt_number > 0),
    loaded_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX fact_grades_student_idx ON warehouse.fact_grades (student_sk);
CREATE INDEX fact_grades_course_idx  ON warehouse.fact_grades (course_sk);
CREATE INDEX fact_grades_school_idx  ON warehouse.fact_grades (school_sk);
CREATE INDEX fact_grades_date_idx    ON warehouse.fact_grades (exam_date_sk);
