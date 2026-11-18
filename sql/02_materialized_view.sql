WHENEVER SQLERROR EXIT FAILURE ROLLBACK
SET TIMING ON
CREATE MATERIALIZED VIEW mv_customer_day
BUILD IMMEDIATE
REFRESH COMPLETE ON DEMAND
AS
WITH category_flags AS (
    SELECT type_name,
        MAX(CASE WHEN group_id = 2 THEN 1 ELSE 0 END) AS is_cred,
        MAX(CASE WHEN group_id = 3 THEN 1 ELSE 0 END) AS is_cred_car,
        MAX(CASE WHEN group_id = 4 THEN 1 ELSE 0 END) AS is_auto_care
    FROM app.type_category
    GROUP BY type_name
), events AS (
    SELECT
        LOWER(TRIM(f.full_name)) AS name_key,
        REGEXP_REPLACE(f.phone, '^8', '7') AS phone_key,
        TRUNC(f."DATE") AS event_day,
        1 AS mirlada,
        NVL(c.is_cred, 0) AS cred,
        NVL(c.is_cred_car, 0) AS cred_car,
        NVL(c.is_auto_care, 0) AS auto_care,
        0 AS guarant
    FROM datahub.ladaru_mirlada_customers_filt f
    LEFT JOIN category_flags c ON c.type_name = f.type
    WHERE f.full_name IS NOT NULL AND f.phone IS NOT NULL
      AND f."DATE" IS NOT NULL
    UNION ALL
    SELECT
        LOWER(TRIM(s.full_name)),
        REGEXP_REPLACE(s.phone, '^8', '7'),
        TRUNC(s.service_date),
        0, 0, 0, 0, 1
    FROM datahub.lada_guarantee20_customers_filt s
    WHERE s.full_name IS NOT NULL AND s.phone IS NOT NULL
      AND s.service_date IS NOT NULL
)
SELECT name_key, phone_key, event_day,
    MAX(mirlada) AS mirlada,
    MAX(cred) AS cred,
    MAX(cred_car) AS cred_car,
    MAX(auto_care) AS auto_care,
    MAX(guarant) AS guarant
FROM events
WHERE name_key IS NOT NULL AND phone_key IS NOT NULL
GROUP BY name_key, phone_key, event_day;
