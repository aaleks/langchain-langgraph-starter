# Splitting a requirement across the determinism boundary

The highest-value move in the method. A requirement that looks `evaluated` is
usually a deterministic **decision** wrapped around an evaluated **judgement**.
Separating them turns an unfalsifiable requirement into a fast exact test plus a
smaller eval.

> The decision is deterministic and belongs in the pure decision layer.
> The judgement feeding the decision is evaluated.

Apply this before accepting any requirement as `evaluated`. Try once, honestly,
and report what you split -- those are the real wins.

## Four angles

| Angle | "Evaluated-looking" requirement | Deterministic half | Evaluated half |
|---|---|---|---|
| Presence vs correctness | "The answer cites its source" | a citation exists and resolves to a chunk that was actually retrieved | the cited source supports the claim |
| Shape vs content | "Returns a useful summary" | conforms to the schema, non-empty, within length bounds | captures the key points |
| Trigger vs output | "Escalates angry customers" | escalates when the sentiment score is below the threshold, given a score | the sentiment score is accurate on a labelled set |
| Policy vs prose | "Never gives medical advice" | the refusal path fires for flagged intents | intent classification catches paraphrases |

## Worked example

The request: *"score the traces so I can see quality regressions."* As stated,
nothing can be false. It became nine requirements:

| Requirement | Kind |
|---|---|
| Only a gateway-routed judge is eligible for automatic scoring | deterministic |
| A model pinned for one provider never repoints another's endpoint | deterministic |
| The sample rate is validated before any judge is touched | deterministic |
| Judge settings default per provider | deterministic |
| A keyless provider still gets a secret entry | deterministic |
| A judge whose registered model drifted is re-registered | deterministic |
| Registering a judge does not start it | deterministic |
| A judge detects a claim absent from its source | **evaluated** |
| The graded judge discriminates good summaries from bad | **evaluated** |

Seven of nine provable in milliseconds with no model. That ratio is the goal.
The two survivors have one thing in common: both are judgements about generated
text. Everything else was a decision -- and every one of those decisions had
already caused a real bug, precisely because it was buried next to a model call
where nobody could test it.

## Signals while mapping

- **More than about eight requirements** -- the change is too big. Split it.
- **A requirement with no example** -- not understood yet. Ask for one.
- **A requirement with no counter-example** -- suspicious: a truism, or two requirements.
- **Many open questions** -- do not start building. A wrong assumption costs more than the question.
- **An example needing three paragraphs of setup** -- the design is wrong, or the requirement spans a layer boundary.

## What this is not

Not Gherkin, not design, not test writing. The scenarios record the cases that
were agreed; `/accept` turns them into tests, one requirement at a time.
