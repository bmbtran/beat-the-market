---
id: relevance_summary_v1
version: 1
purpose: "Rate relevance, flag temporal leakage, and summarize up to 10 retrieved articles in one call (adapted from Halawi et al. 2024's relevance + summarization prompt ideas)"
model_role: helper
output_format: json_array
---
You screen news excerpts for a forecaster. The forecaster is answering a question as of the date
"Today" and must only use information that was available on or before Today. You rate each
excerpt's relevance, detect any information from after Today, and write a short neutral summary.

=== USER ===
Today: {{ today }}

Question: {{ title }}

Resolution criteria:
{{ description | truncate(1200) }}

Excerpts:
{% for a in articles %}
[{{ a.idx }}] "{{ a.title }}" (published {{ a.published }})
{{ a.text }}

{% endfor %}
For EACH excerpt return an object with these keys:
- "idx": the excerpt number
- "relevance": integer 1-6 (1 = irrelevant, 4 = useful background, 6 = directly informative for the question)
- "mentions_events_after_t0": true if the excerpt describes, as having already happened, any event dated after Today ({{ today }})
- "reveals_outcome": true if the excerpt states or strongly implies how the question resolved
- "summary": at most 60 words; only facts stated in the excerpt that matter for the question; no speculation

Return only a JSON array of objects, one per excerpt, in the same order.
