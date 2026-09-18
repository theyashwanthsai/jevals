"""Cases and suites."""
import concurrent.futures as cf
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .client import Client
from .judge import Judge
from .report import Report


@dataclass
class Case:
    """One thing to grade.

    `output` is what's under review. `input` is what produced it, `reference`
    is a gold answer if you have one.

    `should_pass` is optional ground truth -- {check_name: bool} saying whether
    that check *ought to pass* for this case. Note this is deliberately NOT the
    same as Check.expect: for a check declared `noul(..., expect=False)` the two
    are opposites, since a case that does the bad thing should FAIL. Supplying
    it turns the run into a measurement of the grader as well as what you're
    testing, and unlocks Report.reliability(). Omit a check here when the truth
    is genuinely arguable -- reliability is only meaningful over unambiguous
    labels.
    """
    id: str
    output: Any = None
    input: Any = None
    reference: Any = None
    should_pass: Dict[str, bool] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)

    def state(self):
        """Always a structured dict, never concatenated text.

        Hygiene, not a security guarantee. It keeps untrusted output in its own
        labelled field so a check can refer to "the output" unambiguously and
        no delimiter has to be trusted.

        Do not mistake it for an injection defence. Measured A/B 2026-09-18
        (examples/injection_ab.py): the same payload sent flat and structured
        produced the same verdicts every time -- structure changed nothing.
        What actually decided the outcome was how much genuine evidence opposed
        the injection. See FINDINGS.md; the short version is that injection
        nudges the distribution rather than issuing an instruction, so it only
        flips a grade that was already close to its boundary.
        """
        s = {}
        if self.input is not None:
            s["input"] = self.input
        s["output_under_review"] = self.output
        if self.reference is not None:
            s["reference_answer"] = self.reference
        if self.meta:
            s["metadata"] = self.meta
        return s


class Suite:
    def __init__(self, name, checks, judge: Optional[Judge] = None, client: Optional[Client] = None):
        if not checks:
            raise ValueError("a suite needs at least one check")
        self.name = name
        self.checks = list(checks)
        self.client = client or (judge.client if judge else Client())
        self.judge = judge or Judge(client=self.client)
        self.cases: List[Case] = []

    def add(self, id, output=None, **kw):
        self.cases.append(Case(id=id, output=output, **kw))
        return self

    def extend(self, cases):
        for c in cases:
            self.cases.append(c if isinstance(c, Case) else Case(**c))
        return self

    def run(self, concurrency: int = 4, progress=True):
        """Grade every case.

        Jevals never calls your model or agent itself -- it grades output you
        already produced. Set `output=` on every case before calling this
        (call your LLM or agent yourself, in your own code, then pass the
        result in). This just grades what's there.

        Concurrency beats pacing for wall clock here: Jev's burst tax is
        queueing, so parallel calls overlap it rather than compounding it.
        """
        if not self.cases:
            raise ValueError("no cases")
        missing = [c.id for c in self.cases if c.output is None]
        if missing:
            raise ValueError(f"these cases have no output=: {missing}")

        report = Report(self.name, self.checks, self.client)
        errors = []

        def work(case):
            return case, *self.judge.grade(case, self.checks)

        with cf.ThreadPoolExecutor(max_workers=max(1, concurrency)) as ex:
            futures = {ex.submit(work, c): c for c in self.cases}
            for i, fut in enumerate(cf.as_completed(futures), 1):
                case = futures[fut]
                try:
                    _, grades, meta = fut.result()
                    report.add(case, grades, meta)
                except Exception as e:
                    errors.append((case.id, repr(e)))
                if progress:
                    print(f"\r  graded {i}/{len(self.cases)}", end="", file=sys.stderr, flush=True)
        if progress:
            print(file=sys.stderr)
        report.errors = errors
        report.finish()
        return report
