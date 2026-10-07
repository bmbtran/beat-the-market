---
id: disagreement_v1
version: 1
purpose: "AIA Forecaster supervisor step 1: identify disagreements among the ensemble's rationales and propose targeted searches"
model_role: reasoner
output_format: json_object
---
You supervise a team of forecasters who answered the same binary question independently.
Today is {{ today }}. You have no information after this date. Do not assume the question has resolved.
Your job is to find where they disagree and what information would settle it.

=== USER ===
Today: {{ today }}
Question: {{ title }}
Scheduled close: {{ scheduled_close }}

Resolution criteria:
{{ description | truncate(2000) }}

Forecasts and rationales:
{% for f in forecasts %}
--- Forecaster {{ loop.index }} (probability {{ "%.2f" | format(f.p) }}) ---
{{ f.rationale | truncate(2200) }}

{% endfor %}
List the key factual or interpretive disagreements that explain the spread in probabilities. Then
propose at most {{ max_queries }} short news-search queries (4-10 words each, specific entities, no
dates after {{ today }}) whose results would most help resolve those disagreements.

Return only a JSON object: {"disagreements": ["...", "..."], "queries": ["...", "..."]}
