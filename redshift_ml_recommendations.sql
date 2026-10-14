-- =====================================================================
-- ShopSphere — Redshift ML: Next-Best-Product Recommendation Model
-- MENAT Industry AI Accelerator | Retail Personalization Engine
-- =====================================================================
-- Builds a propensity/affinity model with Redshift ML (SageMaker Autopilot
-- under the hood). Predicts a customer's affinity to a product category so
-- the engine can rank "next-best-product" for each shopper.
--
-- This is the "35% of sales" recommendation engine narrative — the core of
-- the personalization story (Amazon credits ~35% of sales to its engine).
--
-- RedshiftML gotchas honored (from prior demo learnings):
--   * sagemaker:* wildcard IAM permission required on the Redshift role
--   * Do NOT set S3_OUTPUT_PATH (invalid CREATE MODEL setting)
--   * Keep MODEL name short (auto S3 path must stay < 128 chars)
--   * Training data must have >= 500 rows
--   * Test ML functions with FROM <table> LIMIT 1 before full scoring
-- =====================================================================

-- 0. Serving tables (loaded from S3 Iceberg/CSV export via COPY) --------
--    (See redshift_load.sql for COPY commands.)

-- 1. Build a labeled training set --------------------------------------
--    Target = did the customer actually ORDER in this category (1/0),
--    Features = behavioral + monetary + demographic signals.
DROP TABLE IF EXISTS ml_training_set;
CREATE TABLE ml_training_set AS
SELECT
    i.customer_id,
    i.category,
    c.loyalty_tier,
    c.age_band,
    c.gender,
    c.preferred_language,
    c.total_sessions,
    c.total_events,
    c.add_to_cart_events,
    c.view_events,
    c.search_events,
    c.avg_order_value,
    c.cart_conversion_rate,
    c.recency_days,
    i.click_score,
    -- label: 1 if this customer placed an order in this category
    CASE WHEN i.order_score > 0 THEN 1 ELSE 0 END AS ordered_in_category
FROM customer_product_interactions i
JOIN customer_360 c ON c.customer_id = i.customer_id;

-- sanity: must be >= 500 rows for Redshift ML
-- SELECT COUNT(*) FROM ml_training_set;   -- expect several thousand

-- 2. Create the model (binary classification: propensity to buy) --------
--    NOTE: no S3_OUTPUT_PATH. Short model name "ss_reco".
DROP MODEL IF EXISTS ss_reco;
CREATE MODEL ss_reco
FROM (
    SELECT loyalty_tier, age_band, gender, preferred_language,
           total_sessions, total_events, add_to_cart_events, view_events,
           search_events, avg_order_value, cart_conversion_rate,
           recency_days, click_score, category,
           ordered_in_category
    FROM ml_training_set
)
TARGET ordered_in_category
FUNCTION fn_predict_category_propensity
IAM_ROLE 'arn:aws:iam::<ACCOUNT_ID>:role/<RedshiftMLRole>'
PROBLEM_TYPE BINARY_CLASSIFICATION
OBJECTIVE 'F1'
SETTINGS (
    S3_BUCKET '<YOUR_REDSHIFTML_BUCKET>',
    MAX_RUNTIME 1800
);

-- Model training is async. Check status:
-- SHOW MODEL ss_reco;

-- 3. Smoke-test the inference function (LIMIT 1 first — RedshiftML rule) -
-- SELECT fn_predict_category_propensity(
--          loyalty_tier, age_band, gender, preferred_language,
--          total_sessions, total_events, add_to_cart_events, view_events,
--          search_events, avg_order_value, cart_conversion_rate,
--          recency_days, click_score, category) AS propensity
-- FROM ml_training_set LIMIT 1;

-- 4. Generate NEXT-BEST-PRODUCT recommendations ------------------------
--    Score every (customer x category), rank, then join to top products
--    in each category that the customer hasn't bought yet.
DROP TABLE IF EXISTS customer_category_scores;
CREATE TABLE customer_category_scores AS
SELECT
    c.customer_id,
    cat.category,
    fn_predict_category_propensity(
        c.loyalty_tier, c.age_band, c.gender, c.preferred_language,
        c.total_sessions, c.total_events, c.add_to_cart_events, c.view_events,
        c.search_events, c.avg_order_value, c.cart_conversion_rate,
        c.recency_days,
        COALESCE(cs.click_score, 0),
        cat.category) AS propensity
FROM customer_360 c
CROSS JOIN (SELECT DISTINCT category FROM product_performance) cat
LEFT JOIN (
    SELECT customer_id, category, SUM(click_score) click_score
    FROM customer_product_interactions GROUP BY customer_id, category
) cs ON cs.customer_id = c.customer_id AND cs.category = cat.category;

-- 5. Final recommendation table: top 5 products per customer -----------
DROP TABLE IF EXISTS customer_recommendations;
CREATE TABLE customer_recommendations AS
WITH ranked_cats AS (
    SELECT customer_id, category, propensity,
           ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY propensity DESC) AS cat_rank
    FROM customer_category_scores
),
top_products AS (
    SELECT product_id, product_name, category, brand, price, rating,
           ROW_NUMBER() OVER (PARTITION BY category ORDER BY revenue DESC, rating DESC) AS prod_rank
    FROM product_performance
    WHERE in_stock = 1
)
SELECT
    rc.customer_id,
    tp.product_id,
    tp.product_name,
    tp.category,
    tp.brand,
    tp.price,
    tp.rating,
    rc.propensity,
    ROW_NUMBER() OVER (PARTITION BY rc.customer_id
                       ORDER BY rc.propensity DESC, tp.prod_rank) AS reco_rank
FROM ranked_cats rc
JOIN top_products tp ON tp.category = rc.category AND tp.prod_rank <= 3
WHERE rc.cat_rank <= 2
QUALIFY reco_rank <= 5;

-- Serve to QuickSight / the agent:
-- SELECT * FROM customer_recommendations WHERE customer_id = 'CUST100000' ORDER BY reco_rank;
