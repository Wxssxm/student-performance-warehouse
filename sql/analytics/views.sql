-- Analytical views — created on top of the star schema, used by the Metabase
-- dashboard and addressable directly from any SQL client.

CREATE OR REPLACE VIEW warehouse.v_avg_grade_by_school AS
SELECT
    sch.school_name,
    sch.school_type,
    sch.city,
    COUNT(*)                          AS exam_count,
    ROUND(AVG(g.grade_value), 2)      AS avg_grade,
    ROUND(AVG(CASE WHEN g.is_passing THEN 1.0 ELSE 0.0 END) * 100, 1) AS pass_rate_pct
FROM warehouse.fact_grades g
JOIN warehouse.dim_school sch USING (school_sk)
GROUP BY sch.school_name, sch.school_type, sch.city
ORDER BY avg_grade DESC;


CREATE OR REPLACE VIEW warehouse.v_grade_by_subject_area AS
SELECT
    c.subject_area,
    COUNT(*)                          AS exam_count,
    ROUND(AVG(g.grade_value), 2)      AS avg_grade,
    ROUND(STDDEV_SAMP(g.grade_value)::NUMERIC, 2) AS stddev_grade
FROM warehouse.fact_grades g
JOIN warehouse.dim_course c USING (course_sk)
GROUP BY c.subject_area
ORDER BY avg_grade DESC;


CREATE OR REPLACE VIEW warehouse.v_top_students AS
SELECT
    s.student_code,
    s.first_name || ' ' || s.last_name AS full_name,
    s.gender,
    COUNT(*)                          AS exam_count,
    ROUND(AVG(g.grade_value), 2)      AS avg_grade,
    ROUND(AVG(CASE WHEN g.is_passing THEN 1.0 ELSE 0.0 END) * 100, 1) AS pass_rate_pct
FROM warehouse.fact_grades g
JOIN warehouse.dim_student s ON s.student_sk = g.student_sk AND s.is_current
GROUP BY s.student_code, full_name, s.gender
HAVING COUNT(*) >= 3
ORDER BY avg_grade DESC
LIMIT 20;


CREATE OR REPLACE VIEW warehouse.v_gender_gap AS
SELECT
    c.subject_area,
    s.gender,
    COUNT(*)                          AS exam_count,
    ROUND(AVG(g.grade_value), 2)      AS avg_grade
FROM warehouse.fact_grades g
JOIN warehouse.dim_course c USING (course_sk)
JOIN warehouse.dim_student s ON s.student_sk = g.student_sk AND s.is_current
GROUP BY c.subject_area, s.gender
ORDER BY c.subject_area, s.gender;


CREATE OR REPLACE VIEW warehouse.v_study_hours_impact AS
SELECT
    CASE
        WHEN s.study_hours_per_week <= 2 THEN '0-2 h/wk'
        WHEN s.study_hours_per_week <= 5 THEN '3-5 h/wk'
        WHEN s.study_hours_per_week <= 10 THEN '6-10 h/wk'
        ELSE '10+ h/wk'
    END AS study_bucket,
    COUNT(*)                          AS exam_count,
    ROUND(AVG(g.grade_value), 2)      AS avg_grade,
    ROUND(AVG(CASE WHEN g.is_passing THEN 1.0 ELSE 0.0 END) * 100, 1) AS pass_rate_pct
FROM warehouse.fact_grades g
JOIN warehouse.dim_student s ON s.student_sk = g.student_sk
GROUP BY study_bucket
ORDER BY MIN(s.study_hours_per_week);


CREATE OR REPLACE VIEW warehouse.v_grade_trend_by_month AS
SELECT
    d.year,
    d.month,
    d.month_name,
    COUNT(*)                          AS exam_count,
    ROUND(AVG(g.grade_value), 2)      AS avg_grade
FROM warehouse.fact_grades g
JOIN warehouse.dim_date d ON d.date_sk = g.exam_date_sk
GROUP BY d.year, d.month, d.month_name
ORDER BY d.year, d.month;


CREATE OR REPLACE VIEW warehouse.v_scd2_audit AS
SELECT
    student_code,
    COUNT(*)                          AS version_count,
    MIN(valid_from)                   AS first_seen,
    MAX(valid_to)                     AS last_seen,
    BOOL_OR(is_current)               AS has_current_row
FROM warehouse.dim_student
GROUP BY student_code
HAVING COUNT(*) > 1
ORDER BY version_count DESC, student_code;
