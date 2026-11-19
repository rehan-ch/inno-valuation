{# The dimensions one advice prompt asks about: the engine's priorities, then any other
   dimension with a target above its score. Shared by templates 5, 6 and 8. Variable:
   focus (a list of app.ai.touchpoints.results.DimensionFact). The gap is the engine's
   (spec 6), given so that the AI never subtracts. The next steps are Amy's
   fixed text from the question set. A change here changes every template that includes
   it: bump their prompt_version. #}
{% for f in focus %}
- {{ f.dimension.name }} (dimension_key: {{ f.dimension.key }})
  Now: {{ f.score }} out of {{ f.maximum }}.{% if f.target is not none %} Target the company set: {{ f.target }} out of {{ f.maximum }}. Gap to the target, as the app worked it out: {{ f.gap }}.{% if f.gap <= 0 %} The target is already reached.{% endif %}{% else %} The company has set no target for it.{% endif %}

  What it covers: {{ f.dimension.description }}
  Its parts: {{ f.dimension.sub_aspects | join("; ") }}
  The method's next steps for it: {{ f.dimension.next_steps }}
{% endfor %}
