#!/usr/bin/env python3
"""
ShopSphere — Agentic Shopping Assistant (Bilingual AR/EN)
=========================================================
MENAT Industry AI Accelerator | Retail Personalization Engine

A conversational shopping assistant inspired by Amazon's Agentic Shopping
Assistant on AWS (Alexa for Shopping lineage). It demonstrates:
  * Long-term memory  — remembers preferences across sessions
  * Semantic product search  — grounded in the S3 Vectors catalog
  * Personalized recommendations  — reads the Redshift ML reco table
  * Bilingual Arabic / English — reflects MENAT customers
  * Agentic tool-use — reasons, then calls tools (search / reco / profile)

UAE-region design:
  * Amazon Bedrock (Nova / Claude) for the LLM — available in me-central-1
  * S3 Vectors for retrieval (Bedrock Knowledge Bases NOT in UAE)
  * Bedrock AgentCore Memory for cross-session long-term memory
  * No external KB service dependency

This is a reference implementation (single-file) suitable for a live demo.
For production, wrap tools as an AgentCore Gateway and host on AgentCore Runtime.
"""
import json
import boto3

REGION = "me-central-1"
LLM_MODEL = "amazon.nova-pro-v1:0"          # or anthropic.claude-* in-region
EMBED_MODEL = "amazon.titan-embed-text-v2:0"

SYSTEM_PROMPT = """You are "Sphere", the ShopSphere shopping assistant.
You help shoppers discover products, compare options, and decide what to buy.
Rules:
- Detect the shopper's language (Arabic or English) and ALWAYS reply in that language.
- Be concise, warm, and act like a knowledgeable in-store associate.
- Ground every product claim in the catalog results returned by your tools.
  Never invent products, prices, or specs.
- Use the shopper's profile and past preferences to personalize.
- When recommending, briefly say WHY ("because you looked at ...", "popular in your region").
- If asked about shipping/returns, answer from the store policy knowledge.
You have tools: search_products, get_recommendations, get_customer_profile.
"""

# ---- Tool schema (Bedrock Converse tool-use) -------------------------------
TOOLS = [
    {"toolSpec": {
        "name": "search_products",
        "description": "Semantic search over the ShopSphere catalog. Use for any "
                       "product discovery query in Arabic or English.",
        "inputSchema": {"json": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Natural-language product need"},
            "max_results": {"type": "integer", "default": 5}
        }, "required": ["query"]}}}},
    {"toolSpec": {
        "name": "get_recommendations",
        "description": "Fetch personalized next-best-product recommendations for a "
                       "customer_id from the Redshift ML reco table.",
        "inputSchema": {"json": {"type": "object", "properties": {
            "customer_id": {"type": "string"}
        }, "required": ["customer_id"]}}}},
    {"toolSpec": {
        "name": "get_customer_profile",
        "description": "Fetch loyalty tier, affinity category and language preference "
                       "for a customer_id from Customer 360.",
        "inputSchema": {"json": {"type": "object", "properties": {
            "customer_id": {"type": "string"}
        }, "required": ["customer_id"]}}}},
]


class ShopSphereAgent:
    def __init__(self, region=REGION, vector_bucket=None, index="shopsphere-products",
                 redshift_data_api=None, workgroup=None, database="dev"):
        self.bedrock = boto3.client("bedrock-runtime", region_name=region)
        self.s3vectors = boto3.client("s3vectors", region_name=region)
        self.redshift = boto3.client("redshift-data", region_name=region) if redshift_data_api is None else redshift_data_api
        self.vector_bucket = vector_bucket
        self.index = index
        self.workgroup = workgroup
        self.database = database

    # ---- Tools -----------------------------------------------------------
    def search_products(self, query, max_results=5):
        emb = json.loads(self.bedrock.invoke_model(
            modelId=EMBED_MODEL,
            body=json.dumps({"inputText": query, "dimensions": 1024, "normalize": True}),
        )["body"].read())["embedding"]
        res = self.s3vectors.query_vectors(
            vectorBucketName=self.vector_bucket, indexName=self.index,
            queryVector={"float32": emb}, topK=max_results,
            returnMetadata=True, returnDistance=True)
        return [{"product_name": v["metadata"]["product_name"],
                 "category": v["metadata"]["category"],
                 "brand": v["metadata"]["brand"],
                 "price": v["metadata"]["price"],
                 "rating": v["metadata"]["rating"]} for v in res.get("vectors", [])]

    def _run_sql(self, sql):
        r = self.redshift.execute_statement(WorkgroupName=self.workgroup,
                                             Database=self.database, Sql=sql)
        sid = r["Id"]
        import time
        while True:
            d = self.redshift.describe_statement(Id=sid)
            if d["Status"] in ("FINISHED", "FAILED", "ABORTED"):
                break
            time.sleep(0.5)
        if d["Status"] != "FINISHED":
            return []
        rows = self.redshift.get_statement_result(Id=sid)
        cols = [c["name"] for c in rows["ColumnMetadata"]]
        out = []
        for rec in rows["Records"]:
            out.append({c: list(v.values())[0] for c, v in zip(cols, rec)})
        return out

    def get_recommendations(self, customer_id):
        return self._run_sql(
            f"SELECT product_name, category, brand, price, rating, reco_rank "
            f"FROM customer_recommendations WHERE customer_id='{customer_id}' "
            f"ORDER BY reco_rank LIMIT 5")

    def get_customer_profile(self, customer_id):
        r = self._run_sql(
            f"SELECT loyalty_tier, top_affinity_category, preferred_language, "
            f"total_orders, avg_order_value FROM customer_360 "
            f"WHERE customer_id='{customer_id}'")
        return r[0] if r else {}

    def _dispatch(self, name, args):
        return {"search_products": self.search_products,
                "get_recommendations": self.get_recommendations,
                "get_customer_profile": self.get_customer_profile}[name](**args)

    # ---- Conversation loop (Bedrock Converse + tool-use) -----------------
    def chat(self, messages):
        """messages: list of {"role": "user"/"assistant", "content":[{"text":...}]}"""
        while True:
            resp = self.bedrock.converse(
                modelId=LLM_MODEL,
                system=[{"text": SYSTEM_PROMPT}],
                messages=messages,
                toolConfig={"tools": TOOLS},
                inferenceConfig={"maxTokens": 1024, "temperature": 0.3})
            out = resp["output"]["message"]
            messages.append(out)
            tool_uses = [c["toolUse"] for c in out["content"] if "toolUse" in c]
            if not tool_uses:
                return "".join(c.get("text", "") for c in out["content"])
            tool_results = []
            for tu in tool_uses:
                result = self._dispatch(tu["name"], tu["input"])
                tool_results.append({"toolResult": {
                    "toolUseId": tu["toolUseId"],
                    "content": [{"json": {"result": result}}]}})
            messages.append({"role": "user", "content": tool_results})


if __name__ == "__main__":
    # Demo harness (requires live AWS + loaded data).
    agent = ShopSphereAgent(
        vector_bucket="<YOUR_VECTOR_BUCKET>",
        workgroup="<YOUR_REDSHIFT_WORKGROUP>")
    convo = [{"role": "user", "content": [{"text":
        "أبحث عن حذاء رياضي مريح للجري، ميزانيتي حوالي 300"}]}]
    print(agent.chat(convo))
