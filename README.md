# Jevals

Jev based LLM/LLM Agent Eval framework. Research preview, not meant for production yet.

Jevals checks model and agent output against rules you write in code. Every
result comes back with a confidence number attached. That number is the whole
point: you can tell a clear answer apart from a guess, trust the clear ones,
and only send the guesses to a human or a bigger model.

Grading runs on [Jev](https://openrouter.ai/typesafe/jev-1.13), a model built
just for this. It doesn't write text back, it answers a typed question with a
number. So there's no judge prompt to write, no text to parse, no retry loop.
32 answers cost about **$0.0002**, cheap enough to check every case, every
time, instead of a random sample.

```bash
pip install -e .
echo 'OPENROUTER_API_KEY=sk-or-v1-...' > .env
```

---

## Grading what your LLM or agent already produced

Jevals never calls your model or agent. You run it yourself, in your own
code, however you already do that. Jevals only grades the result.

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


# define the rubrik: the checks this output has to pass
checks = [
    score("faithful", "Is every factual claim in the output supported by the input?",
          ["Contains unsupported claims",
           "Mostly supported, but overstates a detail",
           "Every claim is directly supported"],
          pass_at=2, critical=True),
    noul("leaks_pii", "Does the output contain personal contact details?", expect=False),
]

suite = Suite("summarisation", checks)

for i, doc in enumerate(DOCS):
    suite.add(f"doc_{i}", input=doc, output=summarise(doc))

suite.run().print()
```

`summarise(doc)` runs before `suite.add()` even sees it. This is really no
different from grading outputs you already saved to disk:

```python
suite.add("doc_0", input=doc, output=saved_summary)
```

Same for an agent. `output` can be any value it returns, not just a string,
so you can grade the whole trace instead of a final line of text:

```python
from jevals import Suite, noul, choice

# Agent traces
trace = coding_agent.run("Fix the failing test in payments/test_refund.py")

# define the rubrik: the checks this trace has to pass
checks = [
    noul("verified_the_fix", "Did the agent re-run the tests after editing?"),
    noul("invented_a_result", "Does the transcript show the agent making up a tool result?",
         expect=False, critical=True),
    choice("outcome", "How did this run end?", {
        "solved":  "Task completed and verified",
        "gave_up": "Agent stopped without completing it",
        "looped":  "Agent repeated an action without making progress",
    }, expect="solved"),
]

suite = Suite("agent behaviour", checks)

suite.add("run_1", output=trace)

suite.run().print()
```

`coding_agent.run(...)` is your own agent call, made before Jevals is
involved at all. Whatever it hands back, plain text, a JSON trace, a list of
tool calls, becomes the `output`, exactly as it came out. Jevals doesn't
reshape it and doesn't run it for you.

---

## Why not LLM-as-judge

An LLM judge picks a word that stands for a verdict, then writes a reason for
the word it already picked. What you get is a label with no honest sense of
how sure it is. The usual fix is to run the judge several times and count the
votes, which just means paying more to rebuild, roughly, a number the model
already had and threw away.

Jev gives you that number directly, in one call. Jevals turns it into a
pass/fail plus a confidence you can set a bar on. So instead of paying an
expensive model to check a sample of your cases, you check every case cheaply
and only send the unclear ones further.

On `examples/04_full_eval.py` that meant 8 cases and 4 checks each, 32 grades,
**$0.000193** total, and every single one of the 30 clear-cut cases matched
our own hand-written answer key. The 2 cases we left off the answer key
because even we weren't sure turned out to be the same 2 cases Jev itself was
least sure about (0.04 and 0.64).

---

## Checks

A check is one question. Your list of checks is the marking scheme. A `Suite`
is that scheme plus the pieces of work you're checking against it.

| constructor | returns | passes when |
|---|---|---|
| `noul(name, q, expect=True)` | probability 0–1 | `p >= pass_at`, or `<=` when `expect=False` |
| `score(name, q, levels, pass_at=N)` | position on your scale | `P(level >= pass_at) > 0.5` |
| `choice(name, q, options, expect="x")` | the chosen option | it matches `expect` |

A few things worth knowing before you write your first check:

- `score` levels are descriptions, worst first. Their place in the list is the
  level number. `pass_at=2` means "reach level 2 or higher."
- `critical=True` fails the whole case if that one check fails. A case can't
  pass on small stuff while failing on something that actually matters.
- Leave `expect` off a `choice` and it can never fail. It just labels things
  instead of judging them.
- Use `score` instead of `noul` when degree matters. We tested `noul` on both
  a dropped production column and `rm -rf /`, and it gave both a 0.98. A
  `score` scale told them apart (3.88 vs 3.99) and stayed in order across all
  6 steps. A yes/no question flattens "bad" and "much worse" into the same
  answer.
- `noul` doesn't come with a built-in confidence number, so Jevals makes one:
  `|p − 0.5| × 2`. That's ours, not the model's, so don't trust it as much.

## Confidence and escalation

```python
def second_opinion(state, check, grade):
    return {"passed": ask_a_stronger_model(state, check), "note": "escalated"}

Suite(..., judge=Judge(escalate_below=0.7, escalator=second_opinion))
```

A grade gets escalated when confidence is low, or when it's "borderline",
meaning it sits close (within 0.02) to its own pass mark. We measured Jev's
answers wobbling by about ±0.01 between identical runs, so a grade sitting
right on the line can flip for no real reason. That's true even at high
confidence, which is why the "borderline" check exists on top of the
confidence check. In our example run, 4 of 32 grades got escalated this way.

## Measuring the grader

The vendor tested confidence on their own questions, not yours. Give Jevals
your own answer key and it'll tell you how much to trust the grader on your
own checks:

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

You want accuracy to go up as confidence goes up. That's what tells you a
threshold is worth picking. If accuracy stays flat no matter how confident the
grade is, the confidence number isn't telling you anything useful.

`should_pass` says whether a check should pass, not whether the answer is
yes. For a check written with `expect=False`, those are opposites. Skip a
check in `should_pass` when you genuinely aren't sure yourself. The accuracy
number only means something if it's measured against answers you'd actually
stand behind.

## Regressions

```python
suite.run().save("baseline.json")
# ...change your prompt, your model, your agent, whatever...
suite.run().compare("baseline.json")   # per-case, per-check deltas
```

---

## Known limits

These are things we tested, not guesses. Full details in
[`FINDINGS.md`](FINDINGS.md).

- Ask questions in plain words, not math. Jev reads dates as text, not as
  numbers you can compare, and it can't count. We asked "was this paid within
  14 days?" on a 15-day gap and got back 0.41, barely on the right side of the
  line. Keep date and number math out of your checks.
- It isn't perfectly consistent. Expect answers to move by about ±0.01
  between runs on the exact same input. That's why the "borderline" check
  exists.
- Trying to trick the grader with fake instructions nudges the answer, it
  doesn't take it over. We planted a fake `GRADER NOTE` telling it to pass a
  clearly wrong answer. Against strong evidence, it moved the grade from 0.00
  to 0.03, barely anything, and on a weaker case it actually backfired. Also,
  it made no difference whether the fake text sat in its own field or was
  mixed into the same string as everything else (see
  `examples/05_injection_experiment.py`). What actually stops an attack is
  having real evidence for the right answer. The "borderline" check catches
  most of what's left.
- Extra unrelated text in the input costs you money, not accuracy. We buried
  a real question in 2KB of unrelated meeting notes and got the same answer,
  same confidence, just 5 times the tokens.
- Slow responses come from waiting in line, not from the model thinking
  longer. Calls sent one at a time, with a gap between them, came back in
  about 415ms. Calls sent back to back on OpenRouter's test endpoint waited
  1 to 2.5 seconds instead. `run()` sends cases at the same time so that
  wait overlaps instead of piling up.

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
| `05_injection_experiment.py` | a test, not a lesson: can fake instructions steer a grade? |

## Layout

| | |
|---|---|
| `jevals/check.py` | `Check` + `noul` / `choice` / `score` |
| `jevals/judge.py` | `Grade`, `Judge`, the escalation cascade |
| `jevals/suite.py` | `Case`, `Suite`, the parallel runner |
| `jevals/report.py` | aggregation, `reliability()`, `compare()` |
| `jevals/client.py` | HTTP, retry on 429/529, usage accounting |
| `research/` | the test scripts Jevals' design is based on |

Defaults to OpenRouter (`~typesafe/jev-latest`). To call TypeSafe directly
instead, set `TYPESAFE_API_KEY` and `JEV_PROVIDER=typesafe`.

## Status

Research preview, and the API will still change. None of this has run in
production yet. The numbers above come from one afternoon of testing on one
account, and the accuracy checks used two small hand-labelled sets, not a
large one. Run `reliability()` on your own data before you trust a threshold.
