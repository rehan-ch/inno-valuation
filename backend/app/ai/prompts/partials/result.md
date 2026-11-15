{# One result, as the app computed and stored it. Shared by the advice templates (4, 5, 6
   and 8). Every number here comes from the scoring engine; every name and description
   from the question set. Variable: facts (app.ai.touchpoints.results.ResultFacts). A
   change here changes every template that includes it: bump their prompt_version. #}
{% if facts.readiness %}
The result is the company's Innovation Readiness: how ready the company is to innovate, from the answers its team agreed on.
Total: {{ facts.total }} out of {{ facts.total_maximum }}.
Band: {{ facts.band.name }}. {{ facts.band.text }}
{% else %}
The result is the Innovation Quotient of one idea: how far the idea moves each dimension, from scores its owner confirmed.
Innovation Quotient: {{ facts.total }} out of {{ facts.total_maximum }}.
How one dimension's score reads:
{% for level in facts.question_set.iq_levels %}
- {{ level.min }} to {{ level.max }}, {{ level.name }}: {{ level.text }}
{% endfor %}
{% endif %}

The dimensions, in order, each with the score the app worked out:
{% for f in facts.dimensions %}
{{ f.dimension.order }}. {{ f.dimension.name }} (dimension_key: {{ f.dimension.key }}): {{ f.score }} out of {{ f.maximum }}{% if f.level %}, {{ f.level.name }}{% endif %}

   What it covers: {{ f.dimension.description }}
   Its parts: {{ f.dimension.sub_aspects | join("; ") }}
{% endfor %}

The priorities, most urgent first, as the app ranked them: {{ facts.priorities | map(attribute="dimension.name") | join(", ") }}.
{% if facts.strengths %}
The strongest dimensions: {{ facts.strengths | map(attribute="dimension.name") | join(", ") }}.
{% else %}
No dimension stands out as a strength.
{% endif %}
{% if facts.idea %}

The idea, in the team's own words:
{{ as_data("idea", facts.idea) }}
{% endif %}

About the company:
{% if facts.company %}
{{ as_data("company", facts.company) }}
{% else %}
No company details were given.
{% endif %}
