"""
START HERE. The smallest eval that works.

We have two replies a support agent might send. We want to check one thing
about each: is it written politely?

Run it:   python3 examples/01_hello.py
"""

# This lets the example find the jevals folder next door. You don't need this
# line in your own code if you've run `pip install -e .`
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from jevals import Suite, noul


# ---------------------------------------------------------------------------
# STEP 1 - say what you want checked.
#
# `noul` is a yes/no question. You give it:
#   a short name   -> "is_polite", which becomes the column name in the results
#   the question   -> asked in plain English, exactly as you'd ask a person
#
# You get back a number between 0 and 1: how likely the answer is "yes".
# By default, a reply PASSES this check when the answer is yes.
# ---------------------------------------------------------------------------
checks = [
    noul("is_polite", "Is this reply written politely?"),
]


# ---------------------------------------------------------------------------
# STEP 2 - say what to check.
#
# A "case" is one piece of work being marked. Give it a name you'll recognise
# in the results, and put the thing being judged in `output`.
# ---------------------------------------------------------------------------
suite = Suite("support replies", checks)

suite.add("friendly", output="Thanks for flagging this! I've refunded the duplicate charge.")
suite.add("rude",     output="You clearly didn't read the docs. Not our problem.")


# ---------------------------------------------------------------------------
# STEP 3 - run it and print the results.
#
# `run()` sends each case off to be marked, then `print()` shows a report card.
# ---------------------------------------------------------------------------
report = suite.run()
report.print()


# ---------------------------------------------------------------------------
# WHAT YOU'LL SEE
#
#   PASS  friendly   score 1.00
#         is_polite    0.98   conf 0.96  PASS
#
#   FAIL  rude       score 0.00
#         is_polite    0.02   conf 0.96  FAIL
#
# Reading a line:
#   0.98        the answer to your question - 98% likely "yes, it's polite"
#   conf 0.96   how SURE it is. This is the useful part: a low number here
#               means the case was genuinely borderline, not that it's impolite.
#   PASS/FAIL   your verdict, worked out from the number above
#
# Next: 02_the_three_checks.py - the other two kinds of question you can ask.
# ---------------------------------------------------------------------------
