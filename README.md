# Jevals

Jev based LLM/LLM Agent Eval framework. Research preview, not meant for production yet.

Jevals scores model and agent output against checks you declare in code, and
returns a **calibrated confidence with every verdict**. That confidence is the
point: you can tell a clear-cut result from a coin flip, trust the former, and
route only the latter to a human or a stronger model.

Grading runs on [Jev](https://openrouter.ai/typesafe/jev-1.13), a decision-only
model — it answers typed questions with probability distributions instead of
prose. There is no judge prompt to tune, no JSON to parse, and no retry loop.
Grading 32 answers costs about **$0.0002**, which makes it viable to score
every case on every commit rather than sampling.

```bash
pip install -e .
echo 'OPENROUTER_API_KEY=sk-or-v1-...' > .env
```

---

## Grading an LLM's output

Hand `run()` the function under test. Jevals calls it, then grades what comes back.

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
    suite.add(f"doc_{i}", input=doc)      # no output= — run() generates it

suite.run(system=summarise).print()
```

Already have outputs on disk? Pass them directly and drop `system=`:

```python
suite.add("doc_0", input=doc, output=previously_generated_summary)
```

## Grading an agent's output

`output` can be any JSON-shaped value, so the thing you grade can be the whole
trace rather than a final string.

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
justification for the token it already picked. You get a label with no honest
uncertainty attached — so the standard workaround is self-consistency: run the
judge N times and count, paying N× to crudely estimate a distribution the model
computed and discarded.

Jev returns that distribution in one call. Jevals turns it into a verdict plus a
confidence you can threshold on, which inverts the economics: instead of judging
a *sample* of cases with an expensive model, judge *every* case cheaply and
escalate only what is genuinely unclear.

Measured on `examples/04_full_eval.py` — 8 cases × 4 checks = 32 grades for
**$0.000193**, at **100% agreement** with hand labels across all 30 unambiguous
ones. The 2 labels withheld as genuinely arguable were the 2 grades Jev
independently flagged lowest-confidence (0.04 and 0.64).

---

## Checks

A check is one question. The list of them is your marking scheme; a `Suite` is
that scheme plus the work being measured against it.

| constructor | returns | passes when |
|---|---|---|
| `noul(name, q, expect=True)` | probability 0–1 | `p >= pass_at`, or `<=` when `expect=False` |
| `score(name, q, levels, pass_at=N)` | position on your scale | `P(level >= pass_at) > 0.5` |
| `choice(name, q, options, expect="x")` | the chosen option | it matches `expect` |

- `score` levels are descriptions, written **worst first**; their index is the
  level. `pass_at=2` means "reach level 2 or better".
- `critical=True` zeroes the case score on failure, so a case can't earn partial
  credit for cosmetics while failing something that matters.
- Omit `expect` on a `choice` and it can never fail — it labels rather than judges.
- **Prefer `score` over `noul` wherever degree matters.** Measured: `noul`
  returned 0.98 for *both* a production column drop and `rm -rf /`, while a
  `score` scale separated them (3.88 vs 3.99) and stayed monotonic across a
  6-step ladder. Saturation silently flattens the top of a scale.
- `noul` has no vendor confidence field, so Jevals derives one as
  `|p − 0.5| × 2`. It is not a reported number; treat it accordingly.

## Confidence and escalation

```python
def second_opinion(state, check, grade):
    return {"passed": ask_a_stronger_model(state, check), "note": "escalated"}

Suite(..., judge=Judge(escalate_below=0.7, escalator=second_opinion))
```

Escalation fires on low confidence **or** on a `borderline` grade — one sitting
within the dead band (0.02) of its own threshold, where Jev's measured
run-to-run jitter of ±0.01 could flip it between runs. A grade can be borderline
at high confidence, and without the dead band your numbers would drift for no
reason. In the example run, 4 of 32 grades escalated.

## Measuring the grader

Vendor calibration was measured on the vendor's questions, not yours. Supply
ground truth and Jevals measures it on your own:

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

Accuracy should climb with confidence — that shape is what licenses a threshold.
If it's flat, the confidence is decoration and you shouldn't gate on it.

`should_pass` is whether the **check should pass**, which for a check declared
`expect=False` is the opposite of "the answer is yes". Omit a check when the
truth is genuinely arguable; reliability only means something over labels you'd
defend.

## Regressions

```python
suite.run().save("baseline.json")
# ...change the system...
suite.run().compare("baseline.json")   # per-case, per-check deltas
```

---

## Known limits

Measured, with the receipts in [`FINDINGS.md`](FINDINGS.md):

- **Ask semantic questions, not arithmetic ones.** Jev reads dates as text and
  is not a calculator. A "within 14 days?" question on a 15-day gap returned
  0.41 — correct side of the line, by a hair. Keep interval math out of checks.
- **Not bit-deterministic.** ±0.01 run to run. Hence the dead band.
- **Adversarial text nudges, it doesn't instruct.** An injected `GRADER NOTE`
  moved a grade 0.00 → 0.03 against strong evidence and *backfired* on a weak
  case. Structured vs flat state made no measurable difference (A/B in
  `examples/05_injection_experiment.py`) — real evidence is what resists it, and
  the borderline machinery is what catches the rest.
- **Large irrelevant context costs money, not accuracy.** 2KB of distractors
  held the verdict at conf 1.00 and multiplied tokens 5×.
- **Latency is throttle-bound, not compute-bound.** Spaced calls return in
  ~415ms; bursts on OpenRouter's alpha endpoint take a quantized 1–2.5s.
  `run()` parallelises so that overlaps instead of compounding.

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
| `05_injection_experiment.py` | adversarial A/B — an experiment, not a tutorial |

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

Research preview. The API will change. Nothing here has run in production, the
measurements above are from a single afternoon on one account, and calibration
has been verified on two small hand-labelled sets rather than at scale — check
`reliability()` on your own data before you trust a threshold.
