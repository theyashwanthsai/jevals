# jevals

A way to check the quality of AI output, automatically, cheaply, and often.

You write down what you want checked. It marks every piece of work against
that list, gives you a report card, and flags anything it wasn't sure about so
a person only has to look at those.

The marking is done by Jev, a model that answers typed questions with a number
and a confidence instead of writing prose. That confidence is what makes this
different from asking another AI "is this good?" - you can tell the difference
between a clear-cut verdict and a coin flip, so you know which results to
trust and which to double-check.

## Setup

```bash
echo 'OPENROUTER_API_KEY=sk-or-v1-...' > .env
pip install -e .            # optional; the examples run without it
```

## Learn it in order

Five files, smallest first. Each one runs, and each teaches exactly one thing.
Read them in order and you'll have the whole library in about ten minutes.

| file | what it teaches | lines of actual code |
|---|---|---|
| `examples/01_hello.py` | the smallest working eval: one check, two cases | ~8 |
| `examples/02_the_three_checks.py` | the three kinds of question, and how pass/fail is decided | ~30 |
| `examples/03_answer_key.py` | how to tell whether the *marker* is any good, and what to do with unsure cases | ~40 |
| `examples/04_full_eval.py` | a real task end to end, including a case that tries to cheat the marker | ~90 |
| `examples/05_injection_experiment.py` | an experiment, not a tutorial: can adversarial text steer a grade? | ~90 |

```bash
python3 examples/01_hello.py
```

## The whole thing in ten lines

```python
from jevals import Suite, noul, score

suite = Suite("support replies", [
    noul("is_polite", "Is this reply written politely?"),
    noul("blames_customer", "Does this reply blame the customer?", expect=False),
    score("helpfulness", "How helpful is this reply?",
          ["Doesn't address it", "Acknowledges it", "Solves it"], pass_at=2),
])

suite.add("case-1", output="Thanks for flagging this! I've refunded the charge.")
suite.add("case-2", output="You clearly didn't read the docs.")

suite.run().print()
```

Three things to know and you can read any eval written with this:

- **`expect=False`** flips a check, for questions where "yes" is the bad answer.
- **`pass_at=2`** on a score means "must reach level 2 or better". Levels are
  written worst-first and are described in words, not numbers.
- **`conf`** in the output is how sure it was. Low confidence means the case was
  genuinely borderline - not that it failed.

## How the pieces fit

```
Check           one question you want answered
[Check, ...]    your marking scheme — just a list, no class needed
Case            one piece of work being marked
Suite           the marking scheme + the pile of work + the runner
```

A `Suite` is not the same thing as a marking scheme: the scheme is reusable
across projects, while the Suite is one specific batch of work being marked
against it. That's why the name comes from testing ("test suite") rather than
from marking — what defines it is that it holds cases.

```python
checks = [...]                           # the scheme — reuse this anywhere
suite  = Suite("March backlog", checks)  # the scheme applied to one batch
suite.add("ticket-1", output=...)        # only a Suite has these
```

## Why not just ask an LLM to judge it

An LLM judge samples a token that stands for a verdict, so you recover a
distribution only by running it N times and counting. Jev returns the
distribution in one call with a confidence attached. That inverts the economics:
instead of judging a sample of cases with an expensive model, you judge every
case cheaply and escalate only what's genuinely unclear.

Measured on `examples/04_full_eval.py`: 8 cases x 4 checks = 32 grades for
**$0.000193** total, at **100% agreement** with hand-labelled ground truth on all
30 unambiguous labels. The 2 labels omitted as genuinely arguable were the 2
grades Jev independently flagged lowest-confidence (0.04 and 0.64).

## The cascade

```python
def llm_escalator(state, check, grade):
    # called only for low-confidence or borderline grades
    return {"passed": ask_a_strong_model(state, check), "note": "escalated"}

Judge(escalate_below=0.65, escalator=llm_escalator)
```

Escalation fires when confidence is below your threshold **or** the grade is
`borderline` — within the dead band of its own pass threshold, where Jev's
run-to-run jitter (~±0.01, measured) could flip the verdict. In the example run
that was 4 of 32 grades (12%), so an LLM judge costs you 12% of what it would
have on its own.

Pick `escalate_below` from `report.reliability()`, not from taste.

## Checks

| constructor | returns | passes when |
|---|---|---|
| `noul(name, q, expect=True)` | probability 0–1 | `p >= pass_at` (or `<=` if `expect=False`) |
| `score(name, q, levels, pass_at=N)` | position on your scale | `P(level >= pass_at) > 0.5` |
| `choice(name, q, options, expect="x")` | chosen option | choice matches `expect` |

- **Prefer `score` over `noul` whenever you need to rank or discriminate at the
  extremes.** Measured: `noul` returned 0.98 for *both* a production column drop
  and `rm -rf /`; a `score` scale separated them (3.88 vs 3.99) and stayed
  monotonic across a 6-step ladder. Saturation silently flattens the top of a scale.
- `pass_at` on a score is evaluated as `P(level >= pass_at) > 0.5`, from the
  returned distribution. Comparing the raw score would make the top level
  unreachable, since `score` is an expectation (Σ level×prob) and a check that is 96%
  certain of level 2 returns 1.96.
- `critical=True` makes any failure zero the case score.
- Jev reports `confidence` for `choice` and `score` but **not** for `noul`, so
  `noul` confidence is derived as `|p − 0.5| × 2`. It is not a vendor number.

## Ground truth and reliability

`should_pass={check: bool}` is whether that check *ought to pass* — deliberately
not the same as `Check.expect`, which is the expected *answer*. For
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
vendor benchmarks does not transfer to your checks automatically — measure it.
Omit a check from `should_pass` when the truth is genuinely arguable.

## Regressions

```python
report.save("out/baseline.json")
# ...change the system...
print(suite.run().compare("out/baseline.json"))   # per-case, per-check deltas
```

## Notes from measurement

- **Ask semantic questions, not arithmetic ones.** Jev reads dates as text and
  is not a calculator. A "within 14 days?" question on a 15-day gap came back
  0.41 — the right side of the line by a hair. Don't put interval math in a check.
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
| `check.py` | `Check` + `noul` / `choice` / `score` constructors |
| `judge.py` | `Grade`, `Judge`, the escalation cascade |
| `suite.py` | `Case`, `Suite`, the parallel runner |
| `report.py` | aggregation, `reliability()`, `compare()` |

Examples: `examples/summarization.py` (full eval with ground truth),
`examples/injection_ab.py` (adversarial A/B).
