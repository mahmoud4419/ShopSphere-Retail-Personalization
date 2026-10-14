# ShopSphere — Retail Personalization Engine

**A Data & AI demo package for the MENAT Industry AI Accelerator**

ShopSphere is a *fictional* retailer. This repository is a complete, runnable
"art-of-the-possible" demo showing how a retailer builds a modern
**personalization engine** on AWS — from raw clickstream to an agentic,
bilingual shopping assistant.

> ⚠️ All data in this repo is **synthetic**. No real customers, no real PII.

---

## Why this demo

It mirrors what Amazon shipped in 2026 so it tells a credible, current story:

- **Agentic Shopping Assistant on AWS** (Sept 2026) — long-term memory,
  multimodal photo search, voice-to-voice (Nova Sonic), cart awareness.
  ShopSphere's assistant reflects these capabilities.
- **Rufus** drove an estimated ~$12B in incremental sales; shoppers were ~60%
  more likely to buy — the conversion-lift story baked into the dashboard.
- **Coresight's 5-pillar personalization model**: Unified Customer
  Intelligence → Next-Best-Action → Hyper-Personalized Content → Real-Time
  Orchestration → Continuous Relationship Management. The demo is structured
  around these five pillars.

## The 5 components

| # | Component | AWS services | Pillar |
|---|-----------|--------------|--------|
| 1 | **Customer 360 Lakehouse** | S3 → Glue (PySpark) → Iceberg on Glue Catalog | Unified Customer Intelligence |
| 2 | **Next-Best-Product ML** | Redshift ML (propensity model) | Next-Best-Action |
| 3 | **Semantic / Multimodal Search** | Titan Embeddings → S3 Vectors | Hyper-Personalized Content |
| 4 | **Agentic Shopping Assistant** | Bedrock AgentCore + Bedrock LLM (AR/EN) | Real-Time Orchestration |
| 5 | **Personalization Dashboard** | Redshift (Direct Query) → QuickSight | Continuous Relationship Mgmt |

## Architecture

![ShopSphere Architecture](docs/architecture.svg)

```
Clickstream / Orders / Catalog (CSV)
   → S3 (raw)
   → Glue PySpark ETL (sessionization + feature engineering)
   → Iceberg on Glue Catalog (lakehouse — open-format interoperability)
   → Redshift Serverless (serving layer, Direct Query — no SPICE limits)
   → QuickSight (personalization KPIs)

Personalization & GenAI:
   → Redshift ML (next-best-product propensity)
   → S3 Vectors (product embeddings — Bedrock KB alternative for UAE)
   → Bedrock AgentCore agent (bilingual AR/EN assistant, long-term memory)
```

## Why these choices (UAE / me-central-1)

This demo is designed to run in the **AWS UAE region (me-central-1)**, which
drives a few deliberate decisions:

- **Iceberg on Glue Catalog** (not Databricks — Azure-only in UAE) → open-format
  lakehouse with cross-engine interoperability.
- **S3 Vectors** for the vector store (**Bedrock Knowledge Bases not available
  in UAE**).
- **Redshift Direct Query** from QuickSight (not SPICE) → the dashboard reflects
  new data immediately after each Glue run, and avoids SPICE refresh limits.

## Repository layout

```
ShopSphere/
├── README.md
├── data_generators/
│   └── generate_data.py          # synthetic customers, catalog, clickstream, orders
├── etl/
│   ├── glue_etl_customer360.py   # Glue PySpark: Customer 360 + features → Iceberg
│   └── iceberg_ddl_athena.sql    # Athena/Trino DDL for the Iceberg tables
├── ml/
│   ├── redshift_load.sql         # COPY serving tables into Redshift
│   ├── redshift_ml_recommendations.sql  # Redshift ML next-best-product model
│   └── build_product_embeddings.py      # Titan embeddings → S3 Vectors
├── agent/
│   └── shopping_agent.py         # Bedrock AgentCore bilingual shopping assistant
├── dashboard/
│   └── shopsphere_dashboard.html # personalization KPI dashboard (Highcharts)
└── docs/
    ├── Setup_Guide.md            # step-by-step deployment
    ├── Demo_Script.md            # 15-min live demo walkthrough
    └── architecture.svg
```

## Quick start

```bash
# 1. Generate synthetic data
cd data_generators
python generate_data.py --out ./output --customers 5000 --days 90

# 2. Upload to S3, run Glue ETL (see docs/Setup_Guide.md)
# 3. Load Redshift serving layer + train Redshift ML model
# 4. Build product embeddings into S3 Vectors
# 5. Open dashboard/shopsphere_dashboard.html
# 6. Run the agent:  python agent/shopping_agent.py
```

See **[docs/Setup_Guide.md](docs/Setup_Guide.md)** for full deployment steps and
**[docs/Demo_Script.md](docs/Demo_Script.md)** for the live demo narrative.

---

*Part of the MENAT Industry AI Accelerator use-case repository. Modeled after the
SkyOps (airline) and NovaDrive (automotive) demo packages.*
