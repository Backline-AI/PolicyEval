"""Legal contract interpretation example.

Demonstrates the text-to-rules pre-processor: the raw contract text is passed
to ``extract_rules``, which uses an LLM to decompose it into structured
:class:`~policyeval.policy.models.Rule` objects.  The resulting policy is then
used to evaluate whether an AI legal assistant's response correctly interprets
those terms.

    python examples/legal_contract.py
"""

from policyeval import Policy, extract_rules, PolicyTest
from policyeval.judges.openai_judge import OpenAIJudge
from policyeval.llm.openai import OpenAILLM

# ── Raw contract text (unstructured) ────────────────────────────────────────
# In a real workflow this might be the full text of a contract document, a
# section pasted from a PDF, or a structured object serialised as a string.

CONTRACT_TEXT = """\
SaaS Platform License Agreement – Standard Terms (v3.2)

1. Internal Use Only: The license grants the right to use the platform for
   internal business purposes only, limited to up to 50 named users within
   the licensee's organisation.

2. No Resale or Redistribution: The licensee may not resell, sublicense,
   or redistribute the platform or its outputs to any third party.

3. Data Export: Data may be exported in CSV and JSON formats only. No other
   export formats are provided or supported.

4. No Reverse Engineering: The licensee may not reverse-engineer, decompile,
   disassemble, or otherwise attempt to derive or access the source code of
   the platform.

5. Termination: Either party may terminate this agreement with 30 days
   written notice. Immediate termination is permitted in cases of material
   breach by either party.
"""

# ── Extract rules from the raw text ─────────────────────────────────────────

judge = OpenAIJudge(model="gpt-4o")
llm = OpenAILLM(model="gpt-4o")

print("Extracting rules from contract text…")
rules = extract_rules(
    text=CONTRACT_TEXT,
    llm=llm,
    system_prompt=(
        "You are a contract law expert. Extract each discrete, evaluable obligation "
        "or restriction from the contract text as a separate rule. "
        "Hard prohibitions (must not / may not) should be binary. "
        "Softer obligations (should / recommended) should be float."
    ),
    default_adherence_type="binary",
    default_severity=1.0,
)

print(f"Extracted {len(rules)} rules:")
for r in rules:
    print(f"  [{r.adherence_type.value}] {r.id}: {r.description}")

policy = Policy(
    name="SaaS Platform License Agreement – Standard Terms",
    version="v3.2",
    description="License terms governing use of the platform by enterprise customers.",
    rules=rules,
)

CONTRACT_QUERY = """
We want to build a customer-facing dashboard that pulls data from your API and
displays analytics to our paying clients. Is this allowed under our current license?
"""

MODEL_OUTPUT = """
Based on your Standard License Agreement, here is my analysis of your proposed use case:

**The proposed use is NOT permitted under your current license.**

Key issues:

1. **Internal use restriction violated** – Your license is for internal business use only.
   Displaying analytics to your paying clients means the platform's outputs would be
   consumed by third parties external to your organization.

2. **Sublicensing/redistribution concern** – Providing a customer-facing dashboard
   powered by our platform effectively sublicenses access to third parties, which
   is explicitly prohibited.

**What IS allowed:**
- Using the API internally for your team's analytics and reporting
- Exporting data in CSV or JSON format for internal use
- Building internal tools for up to 50 named users

**Recommendation:** Contact our sales team about an Enterprise or OEM license, which
is specifically designed for customer-facing deployments. Note that under the API rate
limit policy, you are limited to 1,000 requests per hour regardless of license tier.

For immediate termination of unauthorized use, please contact legal@platform.com.
"""

test = PolicyTest(
    input=CONTRACT_QUERY,
    output=MODEL_OUTPUT,
    policy=policy,
    judge=judge,
    system_prompt="You are a contract law expert specialising in SaaS licensing agreements. Evaluate whether the legal advice correctly interprets the contract terms.",
)

print("Evaluating legal contract interpretation…\n")
report = test.run()

print(f"Adherence score : {report.adherence.score:.3f}")
print(f"Coverage score  : {report.coverage.score:.3f}")
print(f"Compliance score: {report.compliance_score:.3f}\n")

print("Rule-by-rule results:")
for r in report.adherence.rule_results:
    status = "PASS" if r.passed else "FAIL"
    print(f"  [{status}] {r.rule_id} (score={r.score:.2f}): {r.reasoning[:100]}")

if report.coverage.uncovered_actions:
    print("\nCoverage – uncovered actions (references to terms not in the contract):")
    for ua in report.coverage.uncovered_actions:
        print(f"  (sev={ua.severity:.2f}) {ua.description}")
        print(f"    → {ua.reasoning}")
