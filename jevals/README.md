# jevals

Evals for AI systems, graded by a calibrated decision model instead of an LLM judge.

```python
from jevals import Suite, Judge, score, noul

suite = Suite("summarisation", [
    score("faithful", "Is every claim in the output supported by the input?",
          ["Contains unsupported claims", "Overstates a detail", "Fully supported"],
          pass_at=2, critical=True),
    noul("leaks_pii", "Does the output contain personal contact details?", expect=False),
])

suite.add("case-1", input=source, output=candidate,
          should_pass={"faithful": True, "leaks_pii": True})

report = suite.run()          # or run(system=my_model) to generate outputs first
report.print()
report.save("out/run.json")
```

## Why not an LLM judge

An LLM judge samples a token that stands for a verdict, so you recover a
distribution only by running it N times and counting. Jev returns the
distribution in one call with a confidence attached. That inverts the economics:
instead of judging a sample of cases with an expensive model, you judge every
case cheaply and escalate only what's genuinely unclear.

Measured on `examples/summarization.py`: 8 cases x 4 rubrics = 32 grades for
**$0.000193** total, at **100% agreement** with hand-labelled ground truth on all
30 unambiguous labels. The 2 labels omitted as genuinely arguable were the 2
grades Jev independently flagged lowest-confidence (0.04 and 0.64).

## The cascade

```python
def llm_escalator(state, rubric, grade):
    # called only for low-confidence or borderline grades
    return {"passed": ask_a_strong_model(state, rubric), "note": "escalated"}

Judge(escalate_below=0.65, escalator=llm_escalator)
```

Escalation fires when confidence is below your threshold **or** the grade is
`borderline` — within the dead band of its own pass threshold, where Jev's
run-to-run jitter (~±0.01, measured) could flip the verdict. In the example run
that was 4 of 32 grades (12%), so an LLM judge costs you 12% of what it would
have on its own.

Pick `escalate_below` from `report.reliability()`, not from taste.

## Rubrics

| constructor | returns | passes when |
|---|---|---|
| `noul(name, q, expect=True)` | probability 0–1 | `p >= pass_at` (or `<=` if `expect=False`) |
| `score(name, q, levels, pass_at=N)` | float on the rubric | `P(level >= pass_at) > 0.5` |
| `choice(name, q, options, expect="x")` | chosen option | choice matches `expect` |

- **Prefer `score` over `noul` whenever you need to rank or discriminate at the
  extremes.** Measured: `noul` returned 0.98 for *both* a production column drop
  and `rm -rf /`; a `score` rubric separated them (3.88 vs 3.99) and stayed
  monotonic across a 6-step ladder. Saturation silently flattens the top of a scale.
- `pass_at` on a score is evaluated as `P(level >= pass_at) > 0.5`, from the
  returned distribution. Comparing the raw score would make the top level
  unreachable, since `score` is an expectation (Σ level×prob) and a rubric 96%
  certain of level 2 returns 1.96.
- `critical=True` makes any failure zero the case score.
- Jev reports `confidence` for `choice` and `score` but **not** for `noul`, so
  `noul` confidence is derived as `|p − 0.5| × 2`. It is not a vendor number.

## Ground truth and reliability

`should_pass={rubric: bool}` is whether that rubric *ought to pass* — deliberately
not the same as `Rubric.expect`, which is the expected *answer*. For
`noul(..., expect=False)` they are opposites: a case that does the bad thing
should FAIL. Supplying `should_pass` turns a run into a measurement of the grader
as well as the system, and enables:

```
RELIABILITY (grader accuracy vs your ground truth)
  overall 100% on 30 labelled grades
  conf 0.80-0.95  n=9    acc 100%
  conf 0.95-1.00  n=16   acc 100%
```

This is the only evidence that justifies a threshold. Vendor calibration on
vendor benchmarks does not transfer to your rubrics automatically — measure it.
Omit a rubric from `should_pass` when the truth is genuinely arguable.

## Regressions

```python
report.save("out/baseline.json")
# ...change the system...
print(suite.run().compare("out/baseline.json"))   # per-case, per-rubric deltas
```

## Notes from measurement

- **Ask semantic questions, not arithmetic ones.** Jev reads dates as text and
  is not a calculator. A "within 14 days?" question on a 15-day gap came back
  0.41 — the right side of the line by a hair. Don't put interval math in a rubric.
- **Concurrency beats pacing.** Bursts on OpenRouter's alpha endpoint incur a
  quantized ~1–2.5s queueing tax; spaced calls return in ~415ms. `run()`
  parallelises so the tax overlaps instead of compounding. Set
  `Client(min_interval=...)` only if per-call latency matters more than throughput.
- **Structured state is hygiene, not an injection defence.** See
  `examples/injection_ab.py` — flat and structured states produced identical
  verdicts under the same payload. What resists injection is genuine evidence,
  and what catches the rest is the borderline/escalation machinery.
- **Large irrelevant state costs money, not accuracy.** 2KB of distractors left
  the verdict at conf 1.00 but multiplied tokens 5x.

## Files

| file | what |
|---|---|
| `client.py` | HTTP, retry on 429/529, usage accounting |
| `rubric.py` | `Rubric` + `noul` / `choice` / `score` constructors |
| `judge.py` | `Grade`, `Judge`, the escalation cascade |
| `suite.py` | `Case`, `Suite`, the parallel runner |
| `report.py` | aggregation, `reliability()`, `compare()` |

Examples: `examples/summarization.py` (full eval with ground truth),
`examples/injection_ab.py` (adversarial A/B).
