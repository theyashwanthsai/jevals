"""Grading with confidence-gated escalation.

The cascade: Jev grades everything cheaply; only cases where it is unsure get
handed to an expensive judge. Jev's confidence is what makes this possible --
measured 2026-09-18 it dropped to 0.34 on a deliberately unclassifiable input
and 0.40 on subjective ones, while sitting at 1.00 on clear cases.
"""
from dataclasses import dataclass
from typing import Any, Callable, Optional

from .client import Client


@dataclass
class Grade:
    case: str
    check: str
    type: str
    value: Any
    confidence: float
    passed: bool
    borderline: bool = False
    escalated: bool = False
    note: str = ""
    probabilities: Optional[dict] = None
    weight: float = 1.0
    critical: bool = False

    @property
    def trusted(self):
        """Did this grade stand on its own, without needing escalation?"""
        return not (self.borderline or self.escalated)

    def __str__(self):
        v = f"{self.value:.2f}" if isinstance(self.value, float) else str(self.value)
        flag = "PASS" if self.passed else "FAIL"
        marks = "".join(["!" if self.borderline else "", "^" if self.escalated else ""])
        return f"{self.check:<22} {v:<12} conf {self.confidence:.2f}  {flag}{marks}"


class Judge:
    """Grades a case against checks in a single Jev call.

    escalate_below: confidence under this triggers the escalator.
    escalator: callable(state, check, grade) -> dict | None
        Return {"passed": bool, "value": Any (optional), "note": str (optional)}
        to override Jev's grade, or None to keep it. This is where you plug in
        an LLM judge, a human queue, or a deterministic check.

    Escalation also fires on `borderline` grades -- those within the dead band
    of their own threshold, where Jev's run-to-run jitter could flip the verdict.
    """

    def __init__(self, client: Optional[Client] = None, escalate_below: float = 0.0,
                 escalator: Optional[Callable] = None):
        self.client = client or Client()
        self.escalate_below = escalate_below
        self.escalator = escalator

    def grade(self, case, checks):
        """-> (list[Grade], meta)"""
        by_name = {r.name: r for r in checks}
        if len(by_name) != len(checks):
            raise ValueError("duplicate check names")
        state = case.state()
        questions = {r.name: r.to_question() for r in checks}
        answers, meta = self.client.decide(state, questions)

        grades = []
        for name, check in by_name.items():
            if name not in answers:
                raise RuntimeError(f"Jev returned no answer for check {name!r}")
            a = answers[name]
            value, conf, passed, borderline = check.read(a)
            g = Grade(case=case.id, check=name, type=check.type, value=value,
                      confidence=conf, passed=passed, borderline=borderline,
                      probabilities=a.get("probabilities"),
                      weight=check.weight, critical=check.critical)

            if self.escalator and (conf < self.escalate_below or borderline):
                why = "borderline" if borderline else f"confidence {conf:.2f} < {self.escalate_below}"
                verdict = self.escalator(state, check, g)
                g.escalated = True
                if verdict:
                    g.passed = verdict.get("passed", g.passed)
                    if "value" in verdict:
                        g.value = verdict["value"]
                    g.note = verdict.get("note", "") or why
                else:
                    g.note = why + " (escalator kept Jev's grade)"
            grades.append(g)
        return grades, meta
