---
id: query_gen_v1
version: 1
purpose: "Generate diverse news-search queries for a forecasting question (adapted from Halawi et al. 2024's search_query prompt idea)"
model_role: helper
output_format: json_list_of_strings
---
You help a forecaster research a question. You write web news search queries that would surface
recent, factual background information useful for estimating the probability of the question.
You only know information up to the date given as "Today". Never assume the question has resolved.

=== USER ===
Today: {{ today }}

Question: {{ title }}

Resolution criteria:
{{ description | truncate(1500) }}

Write {{ n_queries }} search queries for a news search engine. Make them diverse: one should target the
most direct recent developments, the other the underlying drivers, base rates or historical
precedent. Each query should be short (4-10 words), use specific names/entities, and must NOT
contain dates after {{ today }} or phrases like "result", "outcome", "who won".

Return only a JSON array of {{ n_queries }} strings, e.g. ["query one", "query two"].
