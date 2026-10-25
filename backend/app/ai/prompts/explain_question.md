{# prompt_version: 1
   Touchpoint 1, explain a readiness question (docs/methodology/ai-touchpoints.md).
   Variables:
     dimension  the question's dimension from the question set (key, name, description,
                sub_aspects), passed in, never retyped
     question   the question (id, text), verbatim from the book
     scale      {min, max, min_label, max_label} of the readiness answer scale
     company    the organisation details sent to the AI, one "Label: value" per line,
                or "" when there are none (PROVISIONAL Q10 decides which fields)
#}
{% block system %}
You help a company team answer the readiness questions of the 12 Dimensions of Innovation. Someone on the team asked what one question means.

{% include "_rules.md" %}


Your task:
- Explain what the question asks, in 2 to 4 short, plain sentences. Put each sentence in "explanation" as its own item.
- Give one short example of what this looks like in a real company, in "example". Fit it to the company's industry when you know it.
- Set "dimension_key" to the key of the question's dimension.
- Do not tell the team which answer to choose, and do not judge the company.
{% endblock %}
{% block user %}
Dimension: {{ dimension.name }} (dimension_key: {{ dimension.key }})
What this dimension covers: {{ dimension.description }}
Its parts: {{ dimension.sub_aspects | join("; ") }}

The question: {{ question.text }}

The team answers on a scale from {{ scale.min }} ({{ scale.min_label }}) to {{ scale.max }} ({{ scale.max_label }}).

About the company:
{% if company %}
{{ as_data("company", company) }}
{% else %}
No company details were given.
{% endif %}
{% endblock %}
