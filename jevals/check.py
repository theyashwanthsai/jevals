"""Checks: declarative grading dimensions.

A check is data, not a prompt. It compiles to a Jev question and knows how to
turn an answer into (value, confidence, passed).
"""
from dataclasses import dataclass, field
from typing import Any, Optional

# Jev's jitter measured at +/-0.01 run-to-run on noul. Grades landing this close
# to their threshold are reported borderline rather than silently flipping.
DEAD_BAND = 0.02


@dataclass
class Check:
    name: str
    type: str                       # "noul" | "choice" | "score"
    instructions: str
    criteria: Any = None
    expect: Any = None              # noul: True/False. choice: option or [options]
    pass_at: Optional[float] = None # score: minimum passing level
    weight: float = 1.0
    critical: bool = False          # a failure here fails the whole case

    def __post_init__(self):
        if self.type not in ("noul", "choice", "score"):
            raise ValueError(f"{self.name}: bad type {self.type!r}")
        if self.type == "score":
            if not self.criteria or len(self.criteria) < 2:
                raise ValueError(f"{self.name}: score needs >=2 levels")
            if len(self.criteria) > 10:
                raise ValueError(f"{self.name}: score allows at most 10 levels")
            if self.pass_at is None:
                self.pass_at = len(self.criteria) - 1
        if self.type == "choice":
            if not self.criteria or len(self.criteria) < 2:
                raise ValueError(f"{self.name}: choice needs >=2 options")
            if self.expect is not None:
                opts = [self.expect] if isinstance(self.expect, str) else list(self.expect)
                unknown = [o for o in opts if o not in self.criteria]
                if unknown:
                    raise ValueError(f"{self.name}: expect {unknown} not in criteria")
        if self.type == "noul":
            if self.expect is None:
                self.expect = True
            if self.pass_at is None:
                self.pass_at = 0.5

    def to_question(self):
        q = {"type": self.type, "instructions": self.instructions}
        if self.criteria:
            q["criteria"] = self.criteria
        return q

    def read(self, answer):
        """-> (value, confidence, passed, borderline)

        confidence is normalised to 0..1 across all three types. Jev reports it
        for choice and score; noul has no confidence field, so we derive it as
        |p - 0.5| * 2 -- i.e. how far the probability sits from a coin flip.
        """
        if self.type == "noul":
            p = float(answer["noul"])
            conf = abs(p - 0.5) * 2
            margin = p - self.pass_at if self.expect else (1 - self.pass_at) - p
            passed = (p >= self.pass_at) if self.expect else (p <= 1 - self.pass_at)
            return p, conf, passed, abs(margin) < DEAD_BAND

        if self.type == "score":
            v = float(answer["score"])
            conf = float(answer.get("confidence", 0.0))
            probs = answer.get("probabilities") or {}
            if not probs:
                return v, conf, v >= self.pass_at - 0.5, abs(v - self.pass_at) < DEAD_BAND
            # `score` is an expectation, sum(level * p(level)), so it almost never
            # lands exactly on a level -- comparing it to pass_at directly makes the
            # top level unreachable (a check 96% certain of level 2 returns 1.96).
            # Ask the distribution the question the author actually meant:
            # "is this at least level `pass_at`?" -> P(level >= pass_at) > 0.5.
            mass = sum(p for k, p in probs.items() if int(k) >= self.pass_at)
            return v, conf, mass > 0.5, abs(mass - 0.5) < 0.05

        v = answer["choice"]
        conf = float(answer.get("confidence", 0.0))
        if self.expect is None:
            return v, conf, True, False
        ok = v == self.expect if isinstance(self.expect, str) else v in self.expect
        probs = answer.get("probabilities") or {}
        top2 = sorted(probs.values(), reverse=True)[:2]
        return v, conf, ok, len(top2) == 2 and (top2[0] - top2[1]) < DEAD_BAND


# ------------------------------------------------------------- constructors
def noul(name, instructions, expect=True, *, true=None, false=None,
         pass_at=0.5, weight=1.0, critical=False):
    """Yes/no. `expect=False` means a passing case should answer 'no'.

    Prefer `score` when you need to rank or discriminate at the extremes --
    measured 2026-09-18, noul saturated at 0.98 for both a production column
    drop and `rm -rf /`, while a score check separated them cleanly.
    """
    criteria = None
    if true or false:
        criteria = {k: v for k, v in (("true", true), ("false", false)) if v}
    return Check(name, "noul", instructions, criteria, expect=expect,
                  pass_at=pass_at, weight=weight, critical=critical)


def choice(name, instructions, options, expect=None, *, weight=1.0, critical=False):
    """Pick one of `options` (dict of option -> description)."""
    return Check(name, "choice", instructions, options, expect=expect,
                  weight=weight, critical=critical)


def score(name, instructions, levels, pass_at=None, *, weight=1.0, critical=False):
    """Ordered check. `levels` is a list of descriptions, 0-indexed.

    `pass_at` is the minimum level counted as a pass; defaults to the top level.
    A case passes when P(level >= pass_at) > 0.5, computed from the returned
    distribution -- not by comparing the expectation to the threshold, which
    would make the top level unreachable.
    """
    return Check(name, "score", instructions, list(levels), pass_at=pass_at,
                  weight=weight, critical=critical)
