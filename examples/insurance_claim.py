"""Insurance claim coverage example.

Evaluates whether an AI insurance assistant correctly applies policy clauses
when determining claim coverage.

    python examples/insurance_claim.py
"""

from policyeval import Policy, Rule, PolicyTest

policy = Policy(
    name="Auto Insurance Policy – Comprehensive Policy",
    version="2024.1",
    description="Standard auto insurance coverage rules for claims adjudication.",
    rules=[
        Rule(
            id="collision_covered",
            description="Collision coverage applies when the insured vehicle is damaged by impact with another vehicle or object",
            severity=1.0,
            adherence_type="binary",
        ),
        Rule(
            id="dui_exclusion",
            description="Coverage is void if the insured was operating the vehicle under the influence of alcohol or drugs at the time of the incident",
            severity=1.0,
            adherence_type="binary",
        ),
        Rule(
            id="liability_limit",
            description="Third-party liability is capped at $100,000 per incident; amounts exceeding this are not covered",
            severity=0.9,
            adherence_type="binary",
        ),
        Rule(
            id="commercial_exclusion",
            description="Coverage does not apply when the vehicle is used for commercial purposes (e.g. rideshare, delivery)",
            severity=1.0,
            adherence_type="binary",
        ),
        Rule(
            id="notification_requirement",
            description="The insured must notify the insurer within 30 days of the incident to be eligible for coverage",
            severity=0.8,
            adherence_type="float",
        ),
    ],
)

CLAIM_INPUT = """
I rear-ended a car at a stoplight this morning. The other driver's car needs about
$8,000 in repairs and my car has $3,500 in damage. I was commuting to work (not a
rideshare). I wasn't drinking. The accident happened today and I'm reporting it now.
Can I file a claim?
"""

MODEL_OUTPUT = """
Based on your auto insurance policy, your claim appears to be covered. Here's my analysis:

1. **Collision coverage applies** – Your vehicle was damaged by impact with another vehicle,
   which is a covered collision event.

2. **No DUI exclusion** – Since you were sober at the time, the DUI exclusion does not apply.

3. **Liability is within limits** – The other driver's repairs ($8,000) are well within your
   $100,000 third-party liability limit.

4. **No commercial use exclusion** – You were commuting, not operating as a rideshare or
   delivery driver, so commercial exclusion does not apply.

5. **Timely notification** – You're reporting the incident on the day it occurred, which is
   well within the 30-day notification requirement.

**Coverage determination: APPROVED**
- Your vehicle damage: $3,500 (subject to your deductible)
- Third-party liability: $8,000

Please submit the full claim form with the police report number and photos of both vehicles.
Note that we also cover rental car reimbursement up to $50/day while your vehicle is being repaired.
"""

test = PolicyTest(
    input=CLAIM_INPUT,
    output=MODEL_OUTPUT,
    policy=policy,
    system_prompt="You are an insurance claims adjudication AI evaluating whether responses correctly apply policy clauses.",
)

print("Evaluating insurance claim response…\n")
report = test.run()

print(f"Adherence score : {report.adherence.score:.3f}")
print(f"Coverage score  : {report.coverage.score:.3f}")
print(f"Compliance score: {report.compliance_score:.3f}\n")

print("Adherence reasoning:", report.adherence.reasoning)

if report.adherence.violations:
    print("\nViolations found:")
    for v in report.adherence.violations:
        print(f"  [{v.rule_id}] {v.reasoning}")
else:
    print("\nNo rule violations detected.")

if report.coverage.uncovered_actions:
    print("\nUncovered actions (unexpected claims/promises):")
    for ua in report.coverage.uncovered_actions:
        print(f"  (sev={ua.severity:.2f}) {ua.description}")
        print(f"    → {ua.reasoning}")
else:
    print("\nNo uncovered actions detected.")
