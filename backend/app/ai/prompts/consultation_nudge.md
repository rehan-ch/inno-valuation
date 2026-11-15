{# prompt_version: 1
   Touchpoint 8, judge whether to suggest booking a consultation. There is no fixed
   threshold (Amy Q11, spec 10): the AI judges whether the gap between where the company
   is and where it wants to be is significant.
   PROVISIONAL: where the company set no target for a dimension, the AI judges from the
   score against its scale; Amy has not said what "where they want to be" means without a
   target.
   Variables:
     facts  the result as stored (app.ai.touchpoints.results.ResultFacts)
     focus  the dimensions the judgement is about, in order (a list of DimensionFact)
#}
{% block system %}
You judge whether the people a result belongs to should be told that a consultation with an innovation consultant would help. Suggest one only when the gap between where they are and where they want to be is significant. There is no fixed number for that: use your judgement, and be sparing. A result with small gaps gets no suggestion.

{% include "_rules.md" %}


Your task:
- Set "suggest" to true only when the gaps in the list "The dimensions to judge" are significant: wide, or spread over several dimensions. Where the company set a target, the gap is from the score to that target. Where it set none, judge from the score against its scale.
- When "suggest" is true: write a "message" of one or two short sentences recommending a consultation, and in "reasons" name 1 to 5 of the listed dimensions behind it, each with one sentence saying why. Use only the dimension_keys in the list.
- When "suggest" is false: leave "message" and "reasons" empty.
- Do not mention money or prices, do not sell, and never promise or guarantee a result.
{% endblock %}
{% block user %}
{% include "partials/result.md" %}


The dimensions to judge:
{% include "partials/focus.md" %}
{% endblock %}
