-- Dimensions

-- Date dimension: surrogate key = YYYYMMDD as INTEGER (compact + sortable).
CREATE TABLE warehouse.dim_date (
    date_sk         INTEGER PRIMARY KEY,
    full_date       DATE NOT NULL UNIQUE,
    year            SMALLINT NOT NULL,
    quarter         SMALLINT NOT NULL,
    month           SMALLINT NOT NULL,
    month_name      TEXT NOT NULL,
    day_of_month    SMALLINT NOT NULL,
    day_of_week     SMALLINT NOT NULL,           -- 1 = Monday, 7 = Sunday
    day_name        TEXT NOT NULL,
    week_of_year    SMALLINT NOT NULL,
    is_weekend      BOOLEAN NOT NULL,
    academic_year   TEXT NOT NULL                -- "2024-2025" if month >= 9 else "2023-2024"
);

-- Course dimension (Type 1: in-place updates).
CREATE TABLE warehouse.dim_course (
    course_sk       SERIAL PRIMARY KEY,
    course_code     TEXT NOT NULL UNIQUE,
    course_name     TEXT NOT NULL,
    subject_area    TEXT NOT NULL,
    credit_hours    SMALLINT NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- School dimension (Type 1: in-place updates).
CREATE TABLE warehouse.dim_school (
    school_sk       SERIAL PRIMARY KEY,
    school_code     TEXT NOT NULL UNIQUE,
    school_name     TEXT NOT NULL,
    school_type     TEXT NOT NULL CHECK (school_type IN ('public', 'private')),
    city            TEXT NOT NULL,
    region          TEXT NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Student dimension (Type 2: new row per attribute change).
-- The natural key is `student_code`; each version gets its own surrogate key.
-- Tracked attributes: city, study_hours_per_week, parent_education.
-- Untracked (Type 0, fixed at first insert): first_name, last_name, gender, birth_date.
CREATE TABLE warehouse.dim_student (
    student_sk            BIGSERIAL PRIMARY KEY,
    student_code          TEXT NOT NULL,
    first_name            TEXT NOT NULL,
    last_name             TEXT NOT NULL,
    gender                CHAR(1) NOT NULL CHECK (gender IN ('F', 'M')),
    birth_date            DATE NOT NULL,
    city                  TEXT NOT NULL,
    study_hours_per_week  SMALLINT NOT NULL,
    parent_education      TEXT NOT NULL,
    valid_from            DATE NOT NULL,
    valid_to              DATE NOT NULL DEFAULT DATE '9999-12-31',
    is_current            BOOLEAN NOT NULL DEFAULT TRUE,
    -- Exactly one current row per natural key.
    EXCLUDE USING gist (
        student_code WITH =,
        daterange(valid_from, valid_to, '[)') WITH &&
    )
);

-- Indexes that aren't auto-created by the constraints above.
CREATE INDEX dim_student_code_idx ON warehouse.dim_student (student_code);
CREATE INDEX dim_student_current_idx ON warehouse.dim_student (student_code) WHERE is_current;
CREATE INDEX dim_date_year_idx ON warehouse.dim_date (year, month);
