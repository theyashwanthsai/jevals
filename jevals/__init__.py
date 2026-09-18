"""jevals - evals for AI systems, graded by a calibrated decision model.

    from jevals import Suite, Judge, score, noul, choice

    suite = Suite("summarisation", [
        score("faithful", "Are all claims supported by the input?",
              ["Fabricates", "Minor unsupported detail", "Fully supported"], pass_at=2),
        noul("no_pii", "Does the output leak personal information?", expect=False),
    ])
    suite.add("c1", input=source, output=candidate, expect={"faithful": True})
    suite.run().print()

Why Jev instead of an LLM judge: an LLM judge samples a token that stands for a
verdict, so you recover a distribution only by running it N times. Jev returns
the distribution in one call, with a confidence you can threshold on -- which
turns "judge everything with an expensive model" into "judge everything cheaply,
escalate only what's genuinely unclear".
"""
from .client import Client, JevError
from .judge import Grade, Judge
from .report import Report
from .rubric import DEAD_BAND, Rubric, choice, noul, score
from .suite import Case, Suite

__all__ = ["Suite", "Case", "Judge", "Grade", "Report", "Rubric", "Client",
           "JevError", "score", "noul", "choice", "DEAD_BAND"]
__version__ = "0.1.0"
