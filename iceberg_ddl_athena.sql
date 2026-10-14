-- =====================================================================
-- ShopSphere — Iceberg DDL (Amazon Athena / Trino syntax)
-- MENAT Industry AI Accelerator | Retail Personalization Engine
-- =====================================================================
-- NOTE: This DDL uses ATHENA (Trino) syntax, NOT Spark SQL.
--   * No `USING iceberg` (Spark-only — causes 'mismatched input USING')
--   * LOCATION is REQUIRED
--   * TBLPROPERTIES limited to table_type + format
--   * Use plain PARTITIONED BY (no transforms like days())
-- The Glue PySpark job (glue_etl_customer360.py) creates these tables
-- programmatically; this file is for manual Athena setup / inspection.
-- =====================================================================

CREATE DATABASE IF NOT EXISTS shopsphere;

-- ---- Customer 360 (unified profile + behavioral + monetary features) ----
CREATE TABLE IF NOT EXISTS shopsphere.customer_360 (
    customer_id            string,
    signup_date            string,
    loyalty_tier           string,
    age_band               string,
    gender                 string,
    city_zone              string,
    preferred_language     string,
    email_opt_in           int,
    total_sessions         bigint,
    total_events           bigint,
    add_to_cart_events     bigint,
    view_events            bigint,
    search_events          bigint,
    top_affinity_category  string,
    total_orders           bigint,
    lifetime_spend         double,
    avg_order_value        double,
    cart_conversion_rate   double,
    recency_days           int,
    is_active_90d          int
)
PARTITIONED BY (loyalty_tier)
LOCATION 's3://<YOUR_WAREHOUSE_BUCKET>/lakehouse/customer_360/'
TBLPROPERTIES ('table_type'='ICEBERG', 'format'='parquet');

-- ---- Product performance (catalog + sales rollup) ----
CREATE TABLE IF NOT EXISTS shopsphere.product_performance (
    product_id      string,
    product_name    string,
    category        string,
    subcategory     string,
    brand           string,
    price           double,
    rating          double,
    num_reviews     int,
    in_stock        int,
    color           string,
    is_new_arrival  int,
    units_sold      bigint,
    revenue         double,
    orders_count    bigint
)
PARTITIONED BY (category)
LOCATION 's3://<YOUR_WAREHOUSE_BUCKET>/lakehouse/product_performance/'
TBLPROPERTIES ('table_type'='ICEBERG', 'format'='parquet');

-- ---- Customer x Product interaction matrix (feeds Redshift ML) ----
CREATE TABLE IF NOT EXISTS shopsphere.customer_product_interactions (
    customer_id     string,
    product_id      string,
    click_score     bigint,
    order_score     bigint,
    affinity_score  bigint,
    category        string
)
PARTITIONED BY (category)
LOCATION 's3://<YOUR_WAREHOUSE_BUCKET>/lakehouse/customer_product_interactions/'
TBLPROPERTIES ('table_type'='ICEBERG', 'format'='parquet');

-- Sample analytics query: top categories by revenue
-- SELECT category, SUM(revenue) AS total_rev, SUM(units_sold) AS units
-- FROM shopsphere.product_performance GROUP BY category ORDER BY total_rev DESC;
