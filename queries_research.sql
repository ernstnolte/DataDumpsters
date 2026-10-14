-- 2.1 Rider Cancellation Reasons

-- 2.1.1. Which times during the day are riders more likely to cancel a ride?

SELECT
    EXTRACT(HOUR FROM CAST(request_timestamp AS TIMESTAMP)) AS request_hour,
    COUNT(*) AS total_requests,
    SUM(CASE WHEN UPPER(trip_status) LIKE '%CANCEL%' THEN 1 ELSE 0 END) AS cancellations,
    ROUND(100 * SUM(CASE WHEN UPPER(trip_status) LIKE '%CANCEL%' THEN 1 ELSE 0 END) / COUNT(*), 2) AS cancellation_rate_pct
FROM trip_headers
GROUP BY EXTRACT(HOUR FROM CAST(request_timestamp AS TIMESTAMP))
ORDER BY cancellation_rate_pct DESC;


-- 2.1.2. In which area is it more likely for a rider to cancel a ride?
SELECT
    z.city,
    z.zone_name,
    COUNT(*) AS total_requests,
    SUM(CASE WHEN UPPER(t.trip_status) LIKE '%CANCEL%' THEN 1 ELSE 0 END) AS cancellations,
    ROUND(100 * SUM(CASE WHEN UPPER(t.trip_status) LIKE '%CANCEL%' THEN 1 ELSE 0 END) / COUNT(*), 2) AS cancellation_rate_pct
FROM trip_headers t
JOIN pricing_surge_zones z ON t.zone_id = z.zone_id
GROUP BY z.city, z.zone_name
ORDER BY cancellation_rate_pct DESC;


-- 2.1.3. What drivers have more than average cancellations?


WITH driver_cancellations AS (
    SELECT
        d.driver_id,
        d.first_name,
        d.last_name,
        COUNT(CASE WHEN UPPER(t.trip_status) LIKE '%CANCEL%' THEN 1 END) AS cancellation_count
    FROM sa_drivers d
    LEFT JOIN trip_headers t ON d.driver_id = t.driver_id
    GROUP BY d.driver_id, d.first_name, d.last_name
)
SELECT *
FROM driver_cancellations
WHERE cancellation_count > (
    SELECT AVG(cancellation_count)
    FROM driver_cancellations
)
ORDER BY cancellation_count DESC;


-- 2.1.4. How many cancellations cited safety concerns as a cancellation reason?

SELECT COUNT(*) AS safety_related_cancellations
FROM trip_headers
WHERE UPPER(trip_status) LIKE '%CANCEL%'
AND (
    UPPER(cancellation_reason) LIKE '%SAFETY%'
    OR UPPER(cancellation_reason) LIKE '%SAFE%'
);

-- 2.1.5. At what surge pricing multiplier threshold do cancellations cite PRICING_SURGE spike?

SELECT
    f.surge_multiplier,
    COUNT(*) AS pricing_surge_cancellations
FROM trip_headers t
JOIN trip_fare_breakdown f ON t.trip_id = f.trip_id
WHERE UPPER(t.trip_status) LIKE '%CANCEL%'
AND UPPER(t.cancellation_reason) LIKE '%PRICING_SURGE%'
GROUP BY f.surge_multiplier
ORDER BY f.surge_multiplier;

-- 2.1.6. Does preferred payment method correlate with rider cancellation rates?
SELECT
    r.preferred_payment,
    COUNT(t.trip_id) AS total_requests,
    SUM(CASE WHEN UPPER(t.trip_status) LIKE '%CANCEL%' THEN 1 ELSE 0 END) AS cancellations,
    ROUND(100 * SUM(CASE WHEN UPPER(t.trip_status) LIKE '%CANCEL%' THEN 1 ELSE 0 END) / NULLIF(COUNT(t.trip_id), 0), 2) AS cancellation_rate_pct
FROM sa_riders r
JOIN trip_headers t ON r.rider_id = t.rider_id
GROUP BY r.preferred_payment
ORDER BY cancellation_rate_pct DESC;


-- 2.2 Safety of Different Operating Areas

-- 2.2.1. Which zones/cities have the highest rates of safety-related cancellations?
SELECT
    z.city,
    z.zone_name,
    COUNT(*) AS total_requests,
    SUM(CASE
        WHEN UPPER(t.trip_status) LIKE '%CANCEL%'
        AND (
            UPPER(t.cancellation_reason) LIKE '%SAFETY%'
            OR UPPER(t.cancellation_reason) LIKE '%SAFE%'
        )
        THEN 1 ELSE 0
    END) AS safety_cancellations,
    ROUND(100 * SUM(CASE
        WHEN UPPER(t.trip_status) LIKE '%CANCEL%'
        AND (
            UPPER(t.cancellation_reason) LIKE '%SAFETY%'
            OR UPPER(t.cancellation_reason) LIKE '%SAFE%'
        )
        THEN 1 ELSE 0
    END) / COUNT(*), 2) AS safety_cancellation_rate_pct
FROM trip_headers t
JOIN pricing_surge_zones z ON t.zone_id = z.zone_id
GROUP BY z.city, z.zone_name
ORDER BY safety_cancellation_rate_pct DESC;


-- 2.2.2. Which zones/cities tend to have lower ratings?
SELECT
    z.city,
    z.zone_name,
    COUNT(r.review_id) AS number_of_reviews,
    ROUND(AVG(r.rider_rating_of_driver), 2) AS avg_driver_rating
FROM pricing_surge_zones z
JOIN trip_headers t ON z.zone_id = t.zone_id
JOIN trip_reviews r ON t.trip_id = r.trip_id
WHERE r.rider_rating_of_driver IS NOT NULL
GROUP BY z.city, z.zone_name
ORDER BY avg_driver_rating ASC;


-- 2.2.3. Which zones have the highest rates of safety-related feedback comments?
SELECT
    z.city,
    z.zone_name,
    COUNT(t.trip_id) AS total_trips,
    SUM(
        CASE
            WHEN UPPER(t.cancellation_reason) LIKE '%SAFETY_CONCERN%'
            THEN 1
            ELSE 0
        END
    ) AS safety_related_cancellations,
    ROUND(
        100 * SUM(
            CASE
                WHEN UPPER(t.cancellation_reason) LIKE '%SAFETY_CONCERN%'
                THEN 1
                ELSE 0
            END
        ) / NULLIF(COUNT(t.trip_id), 0),
        2
    ) AS safety_cancellation_rate_pct
FROM pricing_surge_zones z
JOIN trip_headers t
    ON z.zone_id = t.zone_id
GROUP BY z.city, z.zone_name
ORDER BY safety_cancellation_rate_pct DESC;



-- 2.3 Vehicle Safety Statistics

-- 2.3.1. What is the distribution of vehicle safety ratings across the fleet?
SELECT
    adult_safety_rating AS safety_rating,
    COUNT(*) AS amount_of_cars
FROM safety_rating_vehicle
WHERE adult_safety_rating IN (1, 2, 3, 4, 5)
GROUP BY adult_safety_rating
ORDER BY adult_safety_rating;


-- 2.3.2. Which zones/cities have the highest concentration of lower-rated vehicles?
SELECT 
    z.city,
    z.zone_name,
    COUNT(t.trip_id) AS total_trips,
    SUM(CASE WHEN s.adult_safety_rating <= 2 THEN 1 ELSE 0 END) AS low_adult_safety_trips,
    ROUND(SUM(CASE WHEN s.adult_safety_rating <= 2 THEN 1 ELSE 0 END) * 100.0 / COUNT(t.trip_id), 2) AS low_adult_safety_pct,
    SUM(CASE WHEN s.child_safety_rating <= 2 THEN 1 ELSE 0 END) AS low_child_safety_trips,
    ROUND(SUM(CASE WHEN s.child_safety_rating <= 2 THEN 1 ELSE 0 END) * 100.0 / COUNT(t.trip_id), 2) AS low_child_safety_pct
FROM trip_headers t
JOIN pricing_surge_zones z ON t.zone_id = z.zone_id
JOIN sa_drivers d ON t.driver_id = d.driver_id
JOIN vehicles v ON d.driver_id = v.driver_id
JOIN safety_rating_vehicle s ON v.make = REGEXP_SUBSTR(s.car_model, '^[^ ]+') 
                            AND v.model = REGEXP_SUBSTR(s.car_model, '[^ ]+$') 
                            AND v.vehicle_year = s.vehicle_year
GROUP BY z.city, z.zone_name
ORDER BY low_adult_safety_pct DESC;

-- 2.3.3. Does lower vehicle safety rating coincide with a higher rate of cancellations?
SELECT 
    s.adult_safety_rating,
    COUNT(t.trip_id) AS total_trips,
    SUM(CASE WHEN t.trip_status LIKE 'CANCELLED%' THEN 1 ELSE 0 END) AS total_cancellations,
    ROUND(SUM(CASE WHEN t.trip_status LIKE 'CANCELLED%' THEN 1 ELSE 0 END) * 100.0 / COUNT(t.trip_id), 2) AS overall_cancellation_pct
FROM trip_headers t
JOIN sa_drivers d ON t.driver_id = d.driver_id
JOIN vehicles v ON d.driver_id = v.driver_id
JOIN safety_rating_vehicle s ON v.make = REGEXP_SUBSTR(s.car_model, '^[^ ]+') 
                            AND v.model = REGEXP_SUBSTR(s.car_model, '[^ ]+$') 
                            AND v.vehicle_year = s.vehicle_year
GROUP BY s.adult_safety_rating
ORDER BY s.adult_safety_rating;


-- 2.3.4. What is the average vehicle age per zone/city?
WITH vehicle_zones AS (
    SELECT DISTINCT
        v.vehicle_id,
        v.vehicle_year,
        z.city,
        z.zone_name
    FROM vehicles v
    JOIN trip_headers t ON v.driver_id = t.driver_id
    JOIN pricing_surge_zones z ON t.zone_id = z.zone_id
)
SELECT
    city,
    zone_name,
    COUNT(*) AS total_vehicles,
    ROUND(AVG(EXTRACT(YEAR FROM SYSDATE) - vehicle_year), 2) AS average_vehicle_age_years
FROM vehicle_zones
GROUP BY city, zone_name
ORDER BY average_vehicle_age_years DESC;


-- 2.3.5a Are rider cancellations more sensitive to low Adult Safety Ratings?
SELECT 
    s.adult_safety_rating,
    COUNT(t.trip_id) AS total_trips,
    SUM(CASE WHEN t.trip_status = 'CANCELLED_BY_RIDER' THEN 1 ELSE 0 END) AS rider_cancellations,
    ROUND(SUM(CASE WHEN t.trip_status = 'CANCELLED_BY_RIDER' THEN 1 ELSE 0 END) * 100.0 / COUNT(t.trip_id), 2) AS rider_cancellation_pct
FROM trip_headers t
JOIN sa_drivers d ON t.driver_id = d.driver_id
JOIN vehicles v ON d.driver_id = v.driver_id
JOIN safety_rating_vehicle s ON v.make = REGEXP_SUBSTR(s.car_model, '^[^ ]+') 
                            AND v.model = REGEXP_SUBSTR(s.car_model, '[^ ]+$') 
                            AND v.vehicle_year = s.vehicle_year
GROUP BY s.adult_safety_rating
ORDER BY s.adult_safety_rating;

-- 2.3.5b Are rider cancellations more sensitive to low Child Safety Rating:
SELECT 
    s.child_safety_rating,
    COUNT(t.trip_id) AS total_trips,
    SUM(CASE WHEN t.trip_status = 'CANCELLED_BY_RIDER' THEN 1 ELSE 0 END) AS rider_cancellations,
    ROUND(SUM(CASE WHEN t.trip_status = 'CANCELLED_BY_RIDER' THEN 1 ELSE 0 END) * 100.0 / COUNT(t.trip_id), 2) AS rider_cancellation_pct
FROM trip_headers t
JOIN sa_drivers d ON t.driver_id = d.driver_id
JOIN vehicles v ON d.driver_id = v.driver_id
JOIN safety_rating_vehicle s ON v.make = REGEXP_SUBSTR(s.car_model, '^[^ ]+') 
                            AND v.model = REGEXP_SUBSTR(s.car_model, '[^ ]+$') 
                            AND v.vehicle_year = s.vehicle_year
GROUP BY s.child_safety_rating
ORDER BY s.child_safety_rating;



-- 2.4 Fleet Qualty Control

-- 2.4.1. Does vehicle safety rating have a relationship with driver ratings?
SELECT v.model,
       v.vehicle_year,
       ROUND(AVG(r.rider_rating_of_driver), 2) AS avg_driver_rating,
       ROUND(MAX(s.adult_safety_rating), 2) AS adult_safety_rating,
       ROUND(MAX(s.child_safety_rating), 2) AS child_safety_rating
FROM vehicles v
LEFT JOIN safety_rating_vehicle s 
       ON UPPER(TRIM(s.car_model)) LIKE '%' || UPPER(TRIM(v.model)) || '%'
      AND v.vehicle_year = s.vehicle_year
JOIN trip_headers th ON v.driver_id = th.driver_id
JOIN trip_reviews r ON th.trip_id = r.trip_id
GROUP BY v.model, v.vehicle_year;

--2.4. 2. Does vehicle age have a relationship with driver ratings?
SELECT (EXTRACT(YEAR FROM SYSDATE) - v.vehicle_year) AS vehicle_age,
       ROUND(AVG(r.rider_rating_of_driver), 2) AS avg_driver_rating
FROM vehicles v
JOIN trip_headers th ON v.driver_id = th.driver_id
JOIN trip_reviews r ON th.trip_id = r.trip_id
GROUP BY (EXTRACT(YEAR FROM SYSDATE) - v.vehicle_year);

-- 2.4.3. What is the average age of a car upon driver registration?
SELECT ROUND(AVG(EXTRACT(YEAR FROM d.onboarding_date) - v.vehicle_year), 2) AS avg_car_age_at_registration
FROM vehicles v
JOIN sa_drivers d ON v.driver_id = d.driver_id;

-- 2.4.4. What are the ratings of different car makes?
SELECT v.make,
       ROUND(AVG(r.rider_rating_of_driver), 2) AS avg_driver_rating,
       ROUND(AVG(r.driver_rating_of_rider), 2) AS avg_rider_rating
FROM vehicles v
JOIN trip_headers th ON v.driver_id = th.driver_id
JOIN trip_reviews r ON th.trip_id = r.trip_id
GROUP BY v.make;

-- 2.4.5. Is there a correlation between vehicle age and cancellation/completion rates?
SELECT (EXTRACT(YEAR FROM SYSDATE) - v.vehicle_year) AS vehicle_age,
       ROUND(SUM(CASE WHEN th.trip_status = 'CANCELLED_BY_RIDER' THEN 1 ELSE 0 END) / COUNT(*), 2) AS rider_cancel_rate,
       ROUND(SUM(CASE WHEN th.trip_status = 'CANCELLED_BY_DRIVER' THEN 1 ELSE 0 END) / COUNT(*), 2) AS driver_cancel_rate,
       ROUND(SUM(CASE WHEN th.trip_status = 'COMPLETED' THEN 1 ELSE 0 END) / COUNT(*), 2) AS completion_rate
FROM vehicles v
JOIN trip_headers th ON v.driver_id = th.driver_id
GROUP BY (EXTRACT(YEAR FROM SYSDATE) - v.vehicle_year);

--2.4.6. Does vehicle category type influence ratings?
SELECT v.category_type,
       ROUND(AVG(r.rider_rating_of_driver), 2) AS avg_driver_rating
FROM vehicles v
JOIN trip_headers th ON v.driver_id = th.driver_id
JOIN trip_reviews r ON th.trip_id = r.trip_id
GROUP BY v.category_type;

-- 2.5 Driver Performance and Trip Reliablility

-- 2.5.1. Do drivers with lower ratings have higher trip cancellation/completion rates?
SELECT 
    d.driver_id,
    d.driver_rating,
    CASE 
        WHEN d.driver_rating < 4.0 THEN 'Low (< 4.0)'
        WHEN d.driver_rating BETWEEN 4.0 AND 4.5 THEN 'Medium (4.0 - 4.5)'
        ELSE 'High (> 4.5)'
    END AS rating_tier,
    COUNT(t.trip_id) AS total_trips,
    SUM(CASE WHEN t.trip_status = 'COMPLETED' THEN 1 ELSE 0 END) AS completed_trips,
    SUM(CASE WHEN t.trip_status LIKE 'CANCELLED%' THEN 1 ELSE 0 END) AS cancelled_trips,
    ROUND(SUM(CASE WHEN t.trip_status = 'COMPLETED' THEN 1 ELSE 0 END) * 100.0 / COUNT(t.trip_id), 2) AS completion_rate_pct,
    ROUND(SUM(CASE WHEN t.trip_status LIKE 'CANCELLED%' THEN 1 ELSE 0 END) * 100.0 / COUNT(t.trip_id), 2) AS cancellation_rate_pct
FROM 
    sa_drivers d
JOIN 
    trip_headers t ON d.driver_id = t.driver_id
GROUP BY 
    d.driver_id, 
    d.driver_rating
ORDER BY 
    d.driver_rating ASC;

-- 2.5.2. Does driver experience have a relationship with trip cancellation/completion rates?
SELECT d.driver_id,
       (EXTRACT(YEAR FROM SYSDATE) - EXTRACT(YEAR FROM d.onboarding_date)) AS years_experience,
       ROUND(SUM(CASE WHEN th.trip_status = 'CANCELLED_BY_RIDER' THEN 1 ELSE 0 END) / COUNT(*), 2) AS rider_cancel_rate,
       ROUND(SUM(CASE WHEN th.trip_status = 'CANCELLED_BY_DRIVER' THEN 1 ELSE 0 END) / COUNT(*), 2) AS driver_cancel_rate,
       ROUND(SUM(CASE WHEN th.trip_status = 'COMPLETED' THEN 1 ELSE 0 END) / COUNT(*), 2) AS completion_rate
FROM sa_drivers d
JOIN trip_headers th ON d.driver_id = th.driver_id
GROUP BY d.driver_id, (EXTRACT(YEAR FROM SYSDATE) - EXTRACT(YEAR FROM d.onboarding_date));

-- 2.5.3. Does driver experience increase trip ratings?
SELECT d.driver_id,
       (EXTRACT(YEAR FROM SYSDATE) - EXTRACT(YEAR FROM d.onboarding_date)) AS years_experience,
       ROUND(AVG(r.rider_rating_of_driver), 2) AS avg_driver_rating
FROM sa_drivers d
JOIN trip_headers th ON d.driver_id = th.driver_id
JOIN trip_reviews r ON th.trip_id = r.trip_id
GROUP BY d.driver_id, (EXTRACT(YEAR FROM SYSDATE) - EXTRACT(YEAR FROM d.onboarding_date));

-- 2.5.4. Do trip cancellation/completion rates vary across platforms?
SELECT d.platform_affiliation,
       ROUND(SUM(CASE WHEN th.trip_status = 'CANCELLED_BY_RIDER' THEN 1 ELSE 0 END) / COUNT(*), 2) AS rider_cancel_rate,
       ROUND(SUM(CASE WHEN th.trip_status = 'CANCELLED_BY_DRIVER' THEN 1 ELSE 0 END) / COUNT(*), 2) AS driver_cancel_rate,
       ROUND(SUM(CASE WHEN th.trip_status = 'COMPLETED' THEN 1 ELSE 0 END) / COUNT(*), 2) AS completion_rate
FROM sa_drivers d
JOIN trip_headers th ON d.driver_id = th.driver_id
GROUP BY d.platform_affiliation;





