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
# STEP 1 - Define the rubrik.
#
# `noul` is a yes/no question. You give it:
#   Key: a short name -> "is_polite", which becomes the column name in the results
#   Value: the question -> asked in plain English, exactly as you'd ask a person
#
# You get back a number between 0 and 1: how likely the answer is "yes".
# By default, a reply PASSES this check when the answer is yes.
# ---------------------------------------------------------------------------
checks = [
    noul("is_polite", "Is this reply written politely?"),
]

# ---------------------------------------------------------------------------
# STEP 2 - Create a suite and add test cases. 
#
# ---------------------------------------------------------------------------
suite = Suite("support replies", checks)

suite.add("test_case_1", output="Thanks for flagging this! I've refunded the duplicate charge.")
suite.add("test_case_2",     output="You clearly didn't read the docs. Not our problem.")


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
#   PASS  test_case_1   score 1.00
#         is_polite              0.96         conf 0.92  PASS
#
#   FAIL  test_case_2   score 0.00
#         is_polite              0.02         conf 0.96  FAIL
#
#
# THE CASE NAME IS YOURS TO CHOOSE
#
# "test_case_1" is not a keyword and means nothing to the library. It is just a
# label you pick when you call suite.add(), and the only thing it ever does is
# come back to you here so you can tell the rows apart.
#
# Name them whatever makes the report easiest to read: "test_case_1", or
# "refund-request", or the ID of a real support ticket. The one rule is that
# they must be unique within a suite, so two rows can never be confused.
#
# The same is true of "is_polite" in step 1, and of "support replies" in
# step 2 - all three are your own labels, not instructions to anything.
#
#
# READING A LINE
#
#   test_case_1   your name for this piece of work   (you chose it in step 2)
#   score 1.00    the fraction of checks this case passed - 1.00 means all of
#                 them, 0.00 means none. With one check it can only be 1 or 0.
#   is_polite     your name for the check            (you chose it in step 1)
#   0.96          the answer to your question - 96% likely "yes, it's polite"
#   conf 0.92     how SURE it is. This is the useful part: a low number here
#                 means the case was genuinely borderline, not that it failed.
#   PASS/FAIL     the verdict, worked out from the answer above
#
# The exact numbers shift slightly from run to run - 0.96 one time, 0.95 the
# next. That is why anything landing right on a pass mark gets flagged for a
# second look instead of being quietly decided one way or the other.
#
# Next: 02_the_three_checks.py - the other two kinds of question you can ask.
# ---------------------------------------------------------------------------
