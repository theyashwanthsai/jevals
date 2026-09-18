"""
How do you know the MARKER is any good?

You mark a handful of cases yourself first, then compare. This file shows
that, plus what to do with the cases the marker isn't sure about.

Run it:   python3 examples/03_answer_key.py
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from jevals import Suite, Judge, Client, noul, score


checks = [
    noul("is_polite", "Is this reply written politely?"),
    noul("blames_customer", "Does this reply blame the customer?", expect=False),
    score("helpfulness", "How helpful is this reply to the customer?",
          ["Doesn't address the problem at all",
           "Acknowledges the problem but doesn't solve it",
           "Solves the customer's problem"],
          pass_at=2),
]


# ===========================================================================
# THE ANSWER KEY
#
# `should_pass` is YOUR opinion of whether each check should pass. Written as
#   {"check_name": True}   -> this check ought to pass for this case
#   {"check_name": False}  -> this check ought to fail for this case
#
# READ THIS BIT TWICE, it's the one genuinely confusing part:
#
#   `blames_customer` was declared with expect=False, meaning "I want the
#   answer to be no". So for a reply that DOES blame the customer, the check
#   should FAIL - you write should_pass=False, even though the answer to the
#   question is "yes, it blames them".
#
#   should_pass is about the CHECK passing, not about the ANSWER being yes.
#
# I got this backwards the first time I wrote it and it made the marker look
# wrong on half the cases when the mistake was entirely mine.
#
# You don't have to fill in every check. Leave one out when the honest answer
# is "I'm not sure myself" - see `test_case_5` below. Guessing here just pollutes
# the measurement with your own coin flips.
# ===========================================================================

cases = [
    # polite, and solves the problem
    ("test_case_1",
     "Thanks for flagging this! I've refunded the duplicate charge, and you "
     "should see it back within three working days.",
     {"is_polite": True, "blames_customer": True, "helpfulness": True}),

    # rude, and blames the customer
    ("test_case_2",
     "You clearly didn't read the docs. Not our problem.",
     # It blames the customer, so that check should FAIL -> False
     {"is_polite": False, "blames_customer": False, "helpfulness": False}),

    # polite, but solves nothing
    ("test_case_3",
     "I'm so sorry to hear about this, that sounds really frustrating. "
     "Someone will be in touch at some point.",
     {"is_polite": True, "blames_customer": True, "helpfulness": False}),

    # answers the question, but snippily
    ("test_case_4",
     "As I have already explained twice, the setting is in Preferences.",
     {"is_polite": False, "blames_customer": False, "helpfulness": True}),

    # factual and helpful - but is "on your account" blaming?
    ("test_case_5",
     "This was caused by an expired API key on your account. I've reset it.",
     # Deliberately incomplete: it solves the problem and isn't rude, but
     # whether "on your account" counts as blaming is genuinely arguable.
     # So we state the two we're sure about and leave the third blank.
     {"is_polite": True, "helpfulness": True}),
]


# ===========================================================================
# THE HANDOFF
#
# When the marker isn't sure, you probably want a second opinion rather than
# a coin flip. `escalate_below=0.7` means: any answer it's less than 70% sure
# about gets passed to the function below instead of being trusted outright.
#
# In real use this function is one call to a big expensive model, or a message
# to a person. You only pay for it on the few cases that need it.
#
# Returning None means "I looked, keep the original verdict".
# ===========================================================================

def second_opinion(state, check, grade):
    print(f"      [handoff] '{grade.case}' / {check.name} - only {grade.confidence:.0%} "
          f"sure, would ask a bigger model here")
    return None


suite = Suite("support replies", checks,
              judge=Judge(client=Client(), escalate_below=0.7, escalator=second_opinion))

for name, text, answer_key in cases:
    suite.add(name, output=text, should_pass=answer_key)

suite.run().print()


# ---------------------------------------------------------------------------
# HOW TO READ THE RELIABILITY BLOCK
#
# This is the actual output from this file:
#
#   RELIABILITY (grader accuracy vs your ground truth)
#     overall 93% on 14 labelled grades
#     conf 0.00-0.40  n=3    acc   67%
#     conf 0.60-0.80  n=1    acc  100%
#     conf 0.80-0.95  n=5    acc  100%
#     conf 0.95-1.00  n=5    acc  100%
#
# "overall 93%" is how often the marker agreed with you. That's the number
# that tells you whether to trust it on YOUR work - not the vendor's
# benchmarks, which were measured on somebody else's questions.
#
# The rows underneath matter more. They group answers by how sure the marker
# was, and show how often it was actually right in each group. Look at what
# happened here: it was right 100% of the time in all three confident bands,
# and only went wrong in the least-confident one.
#
# That shape is the whole ballgame. It means "I'm sure" and "I'm not sure"
# are honest statements, so you can safely say "trust anything above 0.7,
# send the rest for a second opinion" - and now you know that rule catches
# your mistakes rather than throwing away good answers.
#
# If accuracy were FLAT across the rows - right 80% of the time whether it
# claimed 30% or 99% sure - the confidence number would be decoration, and
# you should not build a threshold on it.
#
# That's the whole reason to bother writing an answer key: it's how you pick
# `escalate_below` from evidence instead of from taste.
#
# Next: 04_full_eval.py - the same ideas on a real task, with a case that
# tries to cheat the marker.
# ---------------------------------------------------------------------------
