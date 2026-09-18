"""
The three kinds of question you can ask, and how pass/fail is decided.

Same support replies as 01, but now we check four things about each.

Run it:   python3 examples/02_the_three_checks.py
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from jevals import Suite, noul, score, choice


checks = [

    # ---------------------------------------------------------------- YES/NO
    # `noul` asks a yes/no question and gives back a number from 0 to 1:
    # how likely the answer is "yes".
    #
    # By default, passing means the answer is YES.
    noul("is_polite", "Is this reply written politely?"),

    # Sometimes a "yes" is the BAD outcome. Add expect=False and the rule
    # flips: now a reply passes when the answer is NO.
    #
    # This is the single easiest thing to get muddled, so say it plainly:
    #   expect=True  -> "I want the answer to be yes"
    #   expect=False -> "I want the answer to be no"
    noul("blames_customer", "Does this reply blame the customer?", expect=False),


    # ------------------------------------------------------------ MARKS OUT OF N
    # `score` is for when yes/no is too blunt and you want a scale.
    #
    # You write out what each level MEANS, worst first. The list below is
    # three levels: 0, 1, 2. You are writing a marking scheme in words -
    # there are no hidden numbers, the descriptions do all the work.
    #
    # pass_at=2 means "must reach level 2 or better to pass".
    score("helpfulness", "How helpful is this reply to the customer?",
          ["Doesn't address the problem at all",
           "Acknowledges the problem but doesn't solve it",
           "Solves the customer's problem"],
          pass_at=2),


    # ----------------------------------------------------------------- PICK ONE
    # `choice` picks exactly one option from a set you define. You write each
    # option as name -> what it means.
    #
    # Leave `expect` off and it never fails - it just reports which one it
    # picked, which is useful for labelling and sorting. Add expect="warm"
    # if you want it to be a pass/fail check with a right answer.
    choice("tone", "What is the overall tone of this reply?",
           {"warm":    "Friendly and personal",
            "neutral": "Plain and factual",
            "cold":    "Curt or dismissive"}),
]


suite = Suite("support replies", checks)

# polite, and actually solves the problem
suite.add("test_case_1",
          output="Thanks for flagging this! I've refunded the duplicate charge, "
                 "and you should see it back within three working days.")

# polite, but never solves anything
suite.add("test_case_2",
          output="I'm so sorry to hear about this, that sounds really frustrating. "
                 "Someone will be in touch at some point.")

# rude, blames the customer, solves nothing
suite.add("test_case_3",
          output="You clearly didn't read the docs. Not our problem.")

suite.run().print()


# ---------------------------------------------------------------------------
# THINGS WORTH NOTICING IN THE OUTPUT
#
# 1. `test_case_2` - the sympathetic but useless one - is polite and doesn't
#    blame anyone, so it passes
#    those two - but it scores low on helpfulness. That separation is the point
#    of having several checks instead of one "is this good?" question.
#
# 2. `tone` never says FAIL, because we didn't give it an expected answer.
#    It's there to label, not to judge.
#
# 3. Prefer `score` over yes/no whenever you care about DEGREE. A yes/no
#    question tends to pin to 0.98 for anything bad, so it can't tell you
#    "bad" from "catastrophically bad". A score scale keeps them apart.
#
# Next: 03_answer_key.py - how to tell whether the marker itself is any good.
# ---------------------------------------------------------------------------
