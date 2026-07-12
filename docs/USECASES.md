# PolicyEval Use Cases

Real-world applications and patterns for using PolicyEval across domains.

## Financial Services

### Investment Advice Guardrails

**Challenge**: Ensure chatbots don't provide personalized investment advice (regulatory requirement).

**Policy**:
```python
Policy(
    name="Financial Advice Safety",
    rules=[
        Rule(
            id="no_personalized_advice",
            description="Must not provide specific investment recommendations",
            severity=1.0,
            adherence_type="binary",
        ),
        Rule(
            id="risk_disclaimer",
            description="Should include disclaimer that this is not financial advice",
            severity=0.8,
            adherence_type="float",
        ),
        Rule(
            id="suggest_advisor",
            description="Should recommend consulting a licensed financial advisor",
            severity=0.6,
            adherence_type="float",
        ),
    ],
)
```

**Usage**:
- **CI**: Test all example responses before deployment
- **Production**: Evaluate every chatbot response before showing to user
- **Monitoring**: Track adherence trends over time

**Example**: [examples/policy_execution.py](../examples/policy_execution.py)

---

## Healthcare

### HIPAA Compliance

**Challenge**: Prevent chatbots from disclosing Protected Health Information (PHI).

**Policy**:
```python
def check_phi_patterns(input: str, output: str, rule: Rule) -> RuleResult:
    """Regex check for PHI patterns (SSN, MRN, etc.)"""
    import re
    patterns = [
        r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
        r'\bMRN[:\s]*\d+\b',        # Medical record number
    ]
    found = any(re.search(p, output) for p in patterns)
    
    return RuleResult(
        rule_id=rule.id,
        score=0.0 if found else 1.0,
        adherence_type="binary",
        severity=rule.severity,
        reasoning=f"PHI pattern {'FOUND' if found else 'not found'}",
        source="programmatic",
    )

Policy(
    name="HIPAA Compliance",
    rules=[
        Rule(
            id="no_phi",
            description="Must not disclose protected health information",
            severity=1.0,
            adherence_type="binary",
            evaluator=check_phi_patterns,  # Fast programmatic check
        ),
        Rule(
            id="no_diagnosis",
            description="Must not provide medical diagnoses",
            severity=1.0,
            adherence_type="binary",
        ),
        Rule(
            id="encourage_doctor",
            description="Should encourage consulting a healthcare provider",
            severity=0.7,
            adherence_type="float",
        ),
    ],
)
```

**Example**: [examples/healthcare_compliance.py](../examples/healthcare_compliance.py)

---

## Legal

### Contract Review

**Challenge**: Verify that an LLM correctly identified all clauses in a legal contract.

**Policy**:
```python
# Extract rules from contract terms
contract_text = """
The Contractor agrees to:
1. Deliver software by December 31, 2024
2. Provide 90-day warranty
3. Not use subcontractors without written consent
4. Maintain $2M liability insurance
"""

rules = extract_rules(
    text=contract_text,
    llm=OpenAILLM(model="gpt-4o"),
    default_adherence_type="binary",
    default_severity=1.0,
)

policy = Policy(name="Contract Compliance", rules=rules)

# Evaluate LLM's contract summary
summary = llm_analyze_contract(contract_text)
report = PolicyTest(
    input=contract_text,
    output=summary,
    policy=policy,
).run()

# Check that all terms were covered
if report.adherence.score < 1.0:
    print("ERROR: LLM missed critical contract terms")
```

**Example**: [examples/legal_contract.py](../examples/legal_contract.py)

---

## Insurance

### Claims Processing

**Challenge**: Ensure claims adjudication follows policy terms exactly.

**Policy**:
```python
Policy(
    name="Auto Insurance Claim Adjudication",
    rules=[
        Rule(
            id="max_coverage",
            description="Must not approve payments exceeding $50,000 policy limit",
            severity=1.0,
            adherence_type="binary",
        ),
        Rule(
            id="check_deductible",
            description="Must subtract $1,000 deductible from approved amount",
            severity=1.0,
            adherence_type="binary",
        ),
        Rule(
            id="pre_existing_damage",
            description="Must deny claims for pre-existing damage",
            severity=0.9,
            adherence_type="binary",
        ),
        Rule(
            id="explanation",
            description="Should provide clear explanation of decision",
            severity=0.6,
            adherence_type="float",
        ),
    ],
)
```

**Example**: [examples/insurance_claim.py](../examples/insurance_claim.py)

---

## DevSecOps

### Security Patch Validation

**Challenge**: Verify that a security patch (git diff) correctly implements a remediation policy.

**Policy**:
```python
def check_version_upgrade(input: str, output: str, rule: Rule) -> RuleResult:
    """Check that go.mod contains the correct version"""
    target_version = "v25.0.4"
    found = f"github.com/docker/docker {target_version}" in output
    
    return RuleResult(
        rule_id=rule.id,
        score=1.0 if found else 0.0,
        adherence_type="binary",
        severity=rule.severity,
        reasoning=f"go.mod {'contains' if found else 'missing'} {target_version}",
        source="programmatic",
    )

Policy(
    name="CVE-2024-XXXX Remediation",
    rules=[
        Rule(
            id="upgrade_docker",
            description="Upgrade github.com/docker/docker to v25.0.4 in go.mod",
            severity=1.0,
            adherence_type="binary",
            evaluator=check_version_upgrade,
        ),
        Rule(
            id="update_go_sum",
            description="Update go.sum with new package hash",
            severity=0.8,
            adherence_type="binary",
        ),
        Rule(
            id="replace_api",
            description="Replace deprecated ContainerJSON with InspectResponse",
            severity=0.9,
            adherence_type="binary",
        ),
    ],
)

# Evaluate git diff
diff = subprocess.check_output(["git", "diff"]).decode()
report = PolicyTest(input=remediation_plan, output=diff, policy=policy).run()
```

**Example**: [examples/sca_remediation.py](../examples/sca_remediation.py)

---

## Customer Support

### Tone and Escalation Policy

**Challenge**: Ensure support bots are empathetic and provide escalation paths.

**Policy**:
```python
Policy(
    name="Customer Support Guidelines",
    rules=[
        Rule(
            id="no_promises",
            description="Must not make promises about features or timelines",
            severity=1.0,
            adherence_type="binary",
        ),
        Rule(
            id="empathy",
            description="Should acknowledge customer frustration empathetically",
            severity=0.7,
            adherence_type="float",
        ),
        Rule(
            id="escalation",
            description="Should provide escalation path if issue unresolved",
            severity=0.6,
            adherence_type="float",
        ),
        Rule(
            id="professional",
            description="Should maintain professional tone (no slang or jargon)",
            severity=0.5,
            adherence_type="float",
        ),
    ],
)
```

**Usage Pattern**:
```python
# Generate response
result = PolicyExecutor(policy=support_plan, input=customer_query).run()

# Evaluate before sending
report = PolicyTest(
    input=customer_query,
    output=result.output,
    policy=support_plan,
).run()

if report.adherence.score >= 0.9:
    send_to_customer(result.output)
else:
    # Log failure and escalate to human
    log_plan_failure(report)
    escalate_to_human(customer_query)
```

---

## Content Moderation

### Community Guidelines

**Challenge**: Detect when LLM-generated content violates community guidelines.

**Policy**:
```python
Policy(
    name="Community Guidelines",
    rules=[
        Rule(
            id="no_hate_speech",
            description="Must not contain hate speech or discriminatory language",
            severity=1.0,
            adherence_type="binary",
        ),
        Rule(
            id="no_violence",
            description="Must not glorify or encourage violence",
            severity=1.0,
            adherence_type="binary",
        ),
        Rule(
            id="no_personal_info",
            description="Must not request or share personal information",
            severity=0.9,
            adherence_type="binary",
        ),
        Rule(
            id="respectful",
            description="Should maintain respectful and inclusive tone",
            severity=0.6,
            adherence_type="float",
        ),
    ],
)
```

**Real-time Filtering**:
```python
async def moderate_content(user_input: str, llm_output: str) -> bool:
    """Returns True if content passes moderation."""
    report = await PolicyTest(
        input=user_input,
        output=llm_output,
        policy=moderation_plan,
    ).arun(metrics=["adherence"])  # Fast adherence-only check
    
    return report.adherence.score >= 0.95
```

---

## Education

### Tutoring Guidelines

**Challenge**: Ensure AI tutors help without giving direct answers.

**Policy**:
```python
Policy(
    name="Tutoring Ethics",
    rules=[
        Rule(
            id="no_direct_answers",
            description="Must not provide direct answers to homework problems",
            severity=1.0,
            adherence_type="binary",
        ),
        Rule(
            id="guide_learning",
            description="Should ask guiding questions to help student reason",
            severity=0.8,
            adherence_type="float",
        ),
        Rule(
            id="explain_concepts",
            description="Should explain underlying concepts, not just procedures",
            severity=0.7,
            adherence_type="float",
        ),
        Rule(
            id="encouraging",
            description="Should use encouraging language",
            severity=0.5,
            adherence_type="float",
        ),
    ],
)
```

---

## Code Review

### Pull Request Guidelines

**Challenge**: Verify that LLM code review follows team standards.

**Policy**:
```python
Policy(
    name="Code Review Standards",
    rules=[
        Rule(
            id="security_check",
            description="Must flag potential security vulnerabilities",
            severity=1.0,
            adherence_type="binary",
        ),
        Rule(
            id="test_coverage",
            description="Should comment on test coverage for new code",
            severity=0.7,
            adherence_type="float",
        ),
        Rule(
            id="performance",
            description="Should identify obvious performance issues",
            severity=0.6,
            adherence_type="float",
        ),
        Rule(
            id="constructive",
            description="Should provide constructive feedback, not just criticism",
            severity=0.5,
            adherence_type="float",
        ),
    ],
)

# Evaluate LLM's PR review
pr_diff = get_pr_diff(pr_number)
review_comment = llm_review_code(pr_diff)

report = PolicyTest(
    input=pr_diff,
    output=review_comment,
    policy=review_plan,
).run()

if report.compliance_score >= 0.8:
    post_review_comment(pr_number, review_comment)
```

---

## Marketing

### Brand Voice Guidelines

**Challenge**: Ensure marketing copy follows brand guidelines.

**Policy**:
```python
Policy(
    name="Brand Voice",
    rules=[
        Rule(
            id="no_superlatives",
            description="Must not use exaggerated claims ('best', 'perfect', 'revolutionary')",
            severity=0.8,
            adherence_type="binary",
        ),
        Rule(
            id="benefits_over_features",
            description="Should focus on customer benefits rather than technical features",
            severity=0.7,
            adherence_type="float",
        ),
        Rule(
            id="conversational",
            description="Should use conversational, friendly tone",
            severity=0.6,
            adherence_type="float",
        ),
        Rule(
            id="active_voice",
            description="Should prefer active voice over passive",
            severity=0.4,
            adherence_type="float",
        ),
    ],
)
```

---

## Research

### Citation Requirements

**Challenge**: Verify that LLM research summaries properly cite sources.

**Policy**:
```python
def check_citations(input: str, output: str, rule: Rule) -> RuleResult:
    """Check that output contains citation markers [1], [2], etc."""
    import re
    citations = re.findall(r'\[\d+\]', output)
    has_citations = len(citations) >= 3
    
    return RuleResult(
        rule_id=rule.id,
        score=1.0 if has_citations else 0.0,
        adherence_type="binary",
        severity=rule.severity,
        reasoning=f"Found {len(citations)} citations (need ≥3)",
        source="programmatic",
    )

Policy(
    name="Research Integrity",
    rules=[
        Rule(
            id="citations",
            description="Must include citations for factual claims",
            severity=1.0,
            adherence_type="binary",
            evaluator=check_citations,
        ),
        Rule(
            id="no_speculation",
            description="Must not present speculation as fact",
            severity=0.9,
            adherence_type="binary",
        ),
        Rule(
            id="limitations",
            description="Should acknowledge limitations of sources",
            severity=0.6,
            adherence_type="float",
        ),
    ],
)
```

---

## Common Patterns Across Domains

### 1. CI/CD Testing Pattern

Test example outputs before deployment:
```python
# tests/test_plan_compliance.py
@pytest.mark.parametrize("input,output", load_test_cases())
def test_domain_plan(input, output):
    assert_policy(
        input=input,
        output=output,
        policy=domain_plan,
        min_adherence=0.95,  # Strict for critical domains
    )
```

### 2. Production Filtering Pattern

Evaluate before showing output to user:
```python
async def generate_safe_response(query: str) -> str:
    for attempt in range(3):
        result = await PolicyExecutor(policy=policy, input=query).arun()
        report = await PolicyTest(
            input=query,
            output=result.output,
            policy=policy,
        ).arun()
        
        if report.adherence.score >= 0.95:
            return result.output
    
    # Fallback to human or safe default
    return "I'm unable to respond. Please contact support."
```

### 3. Monitoring Pattern

Track policy compliance over time:
```python
def log_compliance_metrics(report: PolicyReport):
    metrics = {
        "adherence": report.adherence.score,
        "coverage": report.coverage.score,
        "compliance": report.compliance_score,
        "n_uncovered": len(report.coverage.uncovered_actions),
        "failed_rules": [
            r.rule_id for r in report.adherence.rule_results if not r.passed
        ],
    }
    
    # Send to monitoring (Datadog, Prometheus, etc.)
    send_metrics(metrics)
```

### 4. Audit Trail Pattern

Store evaluation results for compliance audits:
```python
def audit_trail(query: str, response: str, report: PolicyReport):
    audit_record = {
        "timestamp": datetime.utcnow().isoformat(),
        "query": query,
        "response": response,
        "policy": report.policy_name,
        "adherence": report.adherence.score,
        "coverage": report.coverage.score,
        "violations": [
            {"rule": r.rule_id, "reasoning": r.reasoning}
            for r in report.adherence.rule_results
            if not r.passed
        ],
    }
    
    # Store in database or append to audit log
    db.audit_logs.insert(audit_record)
```

---

## Choosing Thresholds by Domain

| Domain | Adherence | Coverage | Notes |
|--------|-----------|----------|-------|
| Healthcare | ≥0.95 | ≥0.90 | Regulatory risk |
| Financial | ≥0.95 | ≥0.90 | Regulatory risk |
| Legal | ≥0.95 | ≥0.85 | High stakes |
| Customer Support | ≥0.85 | ≥0.70 | Balance helpfulness/safety |
| Marketing | ≥0.80 | ≥0.60 | Creative freedom |
| Education | ≥0.90 | ≥0.75 | Ethical constraints |
| Content Moderation | ≥0.95 | ≥0.80 | Safety critical |

**Recommendation**: Start strict, then relax thresholds based on production data.

---

## Next Steps

- Review [examples/](../examples/) for runnable code
- Read [GUIDE.md](GUIDE.md) for implementation patterns
- Check [FAQ.md](FAQ.md) for troubleshooting
