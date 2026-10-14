# ShopSphere — Live Demo Script (~15 min)

A narrative walkthrough for presenting the Retail Personalization Engine to a
customer. Positioned as "art-of-the-possible", grounded in Amazon's 2026
retail AI launches.

---

## 0 · Opening hook (1 min)

> "In 2026, AI-driven traffic to retail sites grew dramatically, and shoppers
> arriving from AI assistants convert meaningfully higher and spend more time
> on-site. Amazon's own Rufus is credited with billions in incremental sales.
> The question for every retailer in the region is no longer *whether* to
> personalize — it's *how fast* they can. Let me show you what that looks like,
> end to end, built entirely on AWS and runnable here in the UAE region."

## 1 · The data foundation — Customer 360 (3 min)

- Show `data_generators/generate_data.py` → "realistic retail signals:
  clickstream, orders, loyalty tiers, and — importantly for our market —
  Arabic/English language preference."
- Show the Glue job writing **Iceberg** tables.
- **Talking point (competitive):** "We're using Iceberg on the Glue Catalog —
  an *open* table format. Unlike Databricks, which in the UAE is Azure-only,
  this keeps your lakehouse interoperable across Athena, Redshift, EMR and
  Spark. No lock-in."

## 2 · The recommendation engine (3 min)

- Open `ml/redshift_ml_recommendations.sql`.
- "Amazon credits roughly a third of its sales to its recommendation engine.
  Here we build that with **Redshift ML** — a propensity model that scores
  every customer × category, then ranks the next-best-product."
- Show `customer_recommendations` for one customer:
  ```sql
  SELECT * FROM customer_recommendations
  WHERE customer_id = 'CUST100000' ORDER BY reco_rank;
  ```
- **Talking point:** "This runs *inside* the warehouse — no data movement, no
  separate ML platform to operate."

## 3 · The dashboard — see the value (3 min)

- Open `dashboard/shopsphere_dashboard.html`.
- Walk the KPIs: GMV, conversion funnel (Views → Cart → Orders), revenue by
  category, GMV/AOV by loyalty tier, channel mix.
- **Talking point (freshness):** "QuickSight reads Redshift via Direct Query,
  so the moment new data lands and the pipeline runs, this refreshes — no SPICE
  refresh limits to design around."

## 4 · The agentic shopping assistant (4 min) — the showstopper

- Run `agent/shopping_agent.py`.
- Type an **Arabic** query:
  > `أبحث عن حذاء رياضي مريح للجري، ميزانيتي حوالي 300`
  (*"I'm looking for comfortable running shoes for jogging, budget ~300"*)
- The agent:
  1. detects Arabic and replies in Arabic,
  2. calls **semantic search** over S3 Vectors (not keyword matching),
  3. personalizes using the customer's profile + reco table,
  4. returns grounded product suggestions with a reason.
- Then switch to **English** mid-conversation to show bilingual handling and
  long-term memory ("remembers you prefer the Aurora brand").
- **Talking point:** "This is the same shape as Amazon's Agentic Shopping
  Assistant on AWS — long-term memory, multimodal-ready, voice-ready via Nova
  Sonic — but it runs in *your* account, speaks *your* brand voice, and your
  customer data never leaves your environment. And it's bilingual by design for
  our region."

## 5 · Close — the 5 pillars (1 min)

> "What you've seen maps to the five pillars of modern personalization:
> unified customer intelligence, next-best-action, hyper-personalized content,
> real-time orchestration, and continuous relationship management. Each is a
> managed AWS service — you can start with one pillar and expand. Where would
> you like to start?"

---

## Q&A quick-reference

| Question | Answer |
|----------|--------|
| "Is my data safe?" | Everything runs in your account; the agent's data never leaves your VPC/region. |
| "Why not Bedrock Knowledge Bases?" | Not yet in UAE — we use S3 Vectors, which gives the same retrieval grounding. |
| "Databricks?" | Azure-only in UAE on that platform; Iceberg on Glue keeps you open and multi-engine. |
| "SPICE limits?" | We use Direct Query on Redshift — dashboards reflect new data immediately. |
| "Can it do images / voice?" | Yes — swap Titan Text for Titan Multimodal for photo search; Nova Sonic for voice-to-voice. |
