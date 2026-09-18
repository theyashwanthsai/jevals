# jev-test

Minimal harness for testing TypeSafe Jev (System One decision model) via OpenRouter.
Zero dependencies — stdlib only.

## Setup

    echo 'OPENROUTER_API_KEY=sk-or-v1-...' > .env

To hit TypeSafe directly instead: put `TYPESAFE_API_KEY=...` in `.env` and
`export JEV_PROVIDER=typesafe`.

## Run

    python3 run.py                     # all 13 cases, 36 calls
    python3 run.py --group claims      # only the advertised use cases
    python3 run.py --group stress      # only the failure-mode probes
    python3 run.py calibration wild    # named cases
    python3 run.py --raw counting      # include raw JSON

## Files

| file | what |
|---|---|
| `jev.py` | client — `decide(state, questions) -> (json, latency_ms)` |
| `cases.py` | the test cases; add yours to `CASES` |
| `run.py` | runner, formatter, and auto-checks |

## What each case probes

**`--group claims`** — the things TypeSafe advertises:

- **calibration** — does `confidence` track real ambiguity? Includes a genuinely
  50/50 ticket and a none-of-the-above ticket. This is the load-bearing claim;
  if confidence is flat at ~1.0 you can't threshold on it.
- **human-gate** — the trust-layer case. Escalating ladder from `cat file` to
  `rm -rf /`. Auto-checks that approval-needed rises monotonically.
- **agent-next-step** — "choose the next step for an agent", with an object
  state (agent trajectory), not a string. Ground truth: `run_tests`.
- **urgency-ladder** — is the score rubric actually ordinal? Auto-checked.
- **many-questions** — 12 questions, one state, one call. The cost/latency lever.

**`--group stress`** — targets failure modes [TypeSafe documents itself](https://docs.typesafe.ai/model-jaggedness/jev-1.13):

- **injection** (their weakness #7) — can text in the *state* override the
  criteria? Ground truth is `sales` for all four variants; one is a polite note,
  one a fake SYSTEM OVERRIDE block, one fake pre-labelled JSON metadata.
- **complement** (#9) — they warn `P(x)` and `1-P(not x)` may disagree. We ask
  both and check the sum.
- **counting** (#2, "Jev is not a calculator") — 7 transactions, 4 failed.
- **dates** (#4, "reads dates as text") — mixed formats, 16-day gap.
- **distractor** (#6) — same decision clean vs buried in ~2KB of meeting notes.
- **code-review** — out of distribution: a diff that removes a mutex and
  introduces a real race.
- **determinism** — same input 5x. Encoder should be bit-identical.
- **wild** — no ground truth at all: haiku quality, an absurd startup, the
  trolley problem. Does it still emit confident numbers?

## Reading the output

    department    billing    conf 0.87  [billing:0.87 technical:0.12 sales:0.01]
    is_urgent     0.940
    urgency       3.42       conf 0.61  [0:0.00 1:0.02 2:0.10 3:0.34 4:0.54]

`noul` is P(yes). `score` is a float = Σ(level × probability), 0-indexed.
`confidence` is derived from how spread the distribution is (noul has none).

The summary block at the end measures the two headline claims: 70–500ms latency
and $0.042/M input tokens, priced per decision.
