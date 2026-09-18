# Jevals

Jev based LLM/LLM Agent Eval framework. Research preview, not meant for production yet.

Jevals scores model and agent output against checks you write in code, and every
verdict comes back with a calibrated confidence attached. That's the part that
matters: you can tell a clear-cut result apart from a coin flip, trust the
clear-cut ones, and only send the coin flips to a human or a stronger model.

Grading runs on [Jev](https://openrouter.ai/typesafe/jev-1.13), a decision-only
model. It answers typed questions with probability distributions instead of
prose, so there's no judge prompt to tune, no JSON to parse, no retry loop.
Grading 32 answers costs about **$0.0002**, cheap enough that you can score
every case on every commit instead of sampling a handful.

```bash
pip install -e .
echo 'OPENROUTER_API_KEY=sk-or-v1-...' > .env
```

---

## Grading an LLM's output

Hand `run()` the function under test and Jevals calls it, then grades what comes back.

```python
import anthropic
from jevals import Suite, score, noul

client = anthropic.Anthropic()

def summarise(doc):
    r = client.messages.create(
        model="claude-opus-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": f"Summarise in two sentences:\n\n{doc}"}],
    )
    return next(b.text for b in r.content if b.type == "text")


suite = Suite("summarisation", [
    score("faithful", "Is every factual claim in the output supported by the input?",
          ["Contains unsupported claims",
           "Mostly supported, but overstates a detail",
           "Every claim is directly supported"],
          pass_at=2, critical=True),
    noul("leaks_pii", "Does the output contain personal contact details?", expect=False),
])

for i, doc in enumerate(DOCS):
    suite.add(f"doc_{i}", input=doc)      # no output= - run() generates it

suite.run(system=summarise).print()
```

Already have outputs sitting on disk? Pass them in directly and skip `system=`:

```python
suite.add("doc_0", input=doc, output=previously_generated_summary)
```

## Grading an agent's output

`output` can be any JSON-shaped value, so you can grade the whole trace instead
of a final string.

```python
from jevals import Suite, noul, choice

suite = Suite("agent behaviour", [
    noul("verified_the_fix", "Did the agent re-run the tests after editing?"),
    noul("invented_a_result", "Does the transcript show the agent fabricating a tool result?",
         expect=False, critical=True),
    choice("outcome", "How did this run end?", {
        "solved":  "Task completed and verified",
        "gave_up": "Agent stopped without completing it",
        "looped":  "Agent repeated an action without making progress",
    }, expect="solved"),
])

suite.add("run_1", output={
    "goal": "Fix the failing test in payments/test_refund.py",
    "steps": [
        {"tool": "run_tests",  "result": "FAIL: assert 0 == 250"},
        {"tool": "edit_file",  "result": "applied to refund.py:47"},
        {"tool": "run_tests",  "result": "PASS"},
    ],
    "final": "Fixed a cents/dollars conversion bug.",
})

suite.run().print()
```

---

## Why not LLM-as-judge

An LLM judge samples a token that stands for a verdict, then writes a
justification for the token it already picked. What you get back is a label
with no honest uncertainty attached. The usual fix is self-consistency: run the
judge N times and count votes, which just means paying N times over to
crudely reconstruct a distribution the model already had and threw away.

Jev returns that distribution in one call. Jevals turns it into a verdict plus
a confidence you can threshold on. So instead of judging a sample of cases with
an expensive model, you judge every case cheaply and only escalate the ones
that are genuinely unclear.

On `examples/04_full_eval.py` that worked out to 8 cases x 4 checks, 32 grades,
**$0.000193** total, and **100% agreement** with hand labels across all 30
unambiguous ones. The 2 labels we left out as genuinely arguable turned out to
be the same 2 grades Jev flagged lowest-confidence on its own (0.04 and 0.64).

---

## Checks

A check is one question. The list of them is your marking scheme; a `Suite` is
that scheme plus the work you're measuring against it.

| constructor | returns | passes when |
|---|---|---|
| `noul(name, q, expect=True)` | probability 0–1 | `p >= pass_at`, or `<=` when `expect=False` |
| `score(name, q, levels, pass_at=N)` | position on your scale | `P(level >= pass_at) > 0.5` |
| `choice(name, q, options, expect="x")` | the chosen option | it matches `expect` |

A few things worth knowing before you write your first check:

- `score` levels are descriptions, written worst first, and their index in the
  list is the level number. `pass_at=2` means "reach level 2 or better."
- `critical=True` zeroes the whole case if that one check fails, so a case
  can't pass on cosmetics while failing on something that actually matters.
- Leave `expect` off a `choice` and it can never fail, it just labels instead
  of judging.
- Prefer `score` over `noul` wherever degree matters. We measured `noul`
  returning 0.98 for both a production column drop and `rm -rf /`, while a
  `score` scale separated them cleanly (3.88 vs 3.99) and stayed monotonic
  across a 6-step ladder. Saturation quietly flattens the top of a scale.
- `noul` doesn't come with a vendor confidence field, so Jevals derives one as
  `|p − 0.5| × 2`. That's our number, not theirs, so treat it accordingly.

## Confidence and escalation

```python
def second_opinion(state, check, grade):
    return {"passed": ask_a_stronger_model(state, check), "note": "escalated"}

Suite(..., judge=Judge(escalate_below=0.7, escalator=second_opinion))
```

Escalation fires on low confidence or on a `borderline` grade, meaning one that
sits within the dead band (0.02) of its own threshold. Jev's run-to-run jitter
is about ±0.01 measured, so a grade can flip between runs if you don't leave
room for it. A grade can be borderline even at high confidence, which is why
the dead band exists at all. In the example run, 4 of 32 grades escalated.

## Measuring the grader

Vendor calibration was measured on the vendor's own questions, not yours.
Supply ground truth and Jevals will measure it on yours instead:

```python
suite.add("doc_0", input=doc, output=out, should_pass={"faithful": True, "leaks_pii": True})
```

```
RELIABILITY (grader accuracy vs your ground truth)
  overall 93% on 14 labelled grades
  conf 0.00-0.40  n=3    acc   67%
  conf 0.60-0.80  n=1    acc  100%
  conf 0.80-0.95  n=5    acc  100%
  conf 0.95-1.00  n=5    acc  100%
```

You want accuracy to climb as confidence climbs. That's the shape that
justifies picking a threshold at all. If the accuracy is flat across
confidence bands, the confidence number is decoration and gating on it won't
help you.

`should_pass` is whether the check should pass, which for a check declared
`expect=False` is the opposite of "the answer is yes." Leave a check out of
`should_pass` when the truth is genuinely arguable. Reliability only means
something when it's measured against labels you'd actually defend.

## Regressions

```python
suite.run().save("baseline.json")
# ...change the system...
suite.run().compare("baseline.json")   # per-case, per-check deltas
```

---

## Known limits

These are measured, not guessed. Full receipts in [`FINDINGS.md`](FINDINGS.md).

- Ask semantic questions, not arithmetic ones. Jev reads dates as text, not as
  ordered quantities, and it's not a calculator. A "within 14 days?" question
  on a 15-day gap came back 0.41, the right side of the line by a hair. Keep
  interval math out of your checks.
- It's not bit-deterministic. Expect about ±0.01 run to run, which is why the
  dead band exists.
- Adversarial text nudges a grade, it doesn't hijack it. An injected
  `GRADER NOTE` moved a grade from 0.00 to 0.03 against strong evidence, and
  actually backfired on a weak case. Structured state vs. flat text made no
  measurable difference in our A/B (`examples/05_injection_experiment.py`).
  What actually resists an attack is having real evidence behind the grade,
  and the borderline machinery is what catches whatever's left.
- Large irrelevant context costs you money, not accuracy. 2KB of distractor
  text left the verdict sitting at confidence 1.00 but multiplied the token
  count by 5x.
- Latency is throttle-bound, not compute-bound. Spaced-out calls return in
  about 415ms; bursts on OpenRouter's alpha endpoint hit a quantized 1–2.5s
  wait instead. `run()` runs cases in parallel so that wait overlaps rather
  than stacking up.

## Examples

```bash
python3 examples/01_hello.py
```

| | |
|---|---|
| `01_hello.py` | smallest working eval |
| `02_the_three_checks.py` | the three check types and their pass rules |
| `03_answer_key.py` | ground truth, reliability, escalation |
| `04_full_eval.py` | a real task, including a case that tries to cheat the grader |
| `05_injection_experiment.py` | adversarial A/B, an experiment rather than a tutorial |

## Layout

| | |
|---|---|
| `jevals/check.py` | `Check` + `noul` / `choice` / `score` |
| `jevals/judge.py` | `Grade`, `Judge`, the escalation cascade |
| `jevals/suite.py` | `Case`, `Suite`, the parallel runner |
| `jevals/report.py` | aggregation, `reliability()`, `compare()` |
| `jevals/client.py` | HTTP, retry on 429/529, usage accounting |
| `research/` | the probe suite Jevals' design is based on |

Defaults to OpenRouter (`~typesafe/jev-latest`). For TypeSafe direct, set
`TYPESAFE_API_KEY` and `JEV_PROVIDER=typesafe`.

## Status

Research preview, and the API will still change. None of this has run in
production. The measurements above come from a single afternoon on one
account, and calibration has only been checked against two small
hand-labelled sets, not at real scale, so run `reliability()` on your own
data before you trust a threshold.
