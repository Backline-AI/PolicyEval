"""SCA remediation policy evaluation example.

Evaluates whether a git diff correctly implements a CVE remediation policy.
The version-bump rule is checked programmatically (a plain string match –
no LLM call needed, deterministic); the remaining rules, which require
judgment about *how* the code changed, are evaluated by the LLM judge.

    python examples/sca_remediation.py

Appendix
--------
After the main evaluation output, the script prints a structured appendix
containing per-rule scores in a compact table, a severity-weighted breakdown,
and the full serialised report as JSON – useful for CI artefacts or audit logs.
"""

from policyeval import Policy, Rule, RuleResult, PolicyTest

# ── Programmatic evaluator ───────────────────────────────────────────────────
# A version bump is a plain string match – there's no judgment call for an
# LLM to make, so we skip the LLM call entirely for this one rule.

TARGET_VERSION = "v25.0.4"


def check_docker_version(input: str, output: str, rule: Rule) -> RuleResult:
    found = TARGET_VERSION in output
    return RuleResult(
        rule_id=rule.id,
        score=1.0 if found else 0.0,
        adherence_type=rule.adherence_type,
        severity=rule.severity,
        reasoning=f"{TARGET_VERSION} {'found' if found else 'not found'} in diff",
        source="programmatic",
    )


# ── Policy definition ────────────────────────────────────────────────────────

policy = Policy(
    name="SCA Remediation Policy – Docker Security Fix",
    version="2024-Q1",
    description="Remediation policy for CVE-2024-XXXX in github.com/docker/docker.",
    rules=[
        Rule(
            id="upgrade_docker_version",
            description="Upgrade github.com/docker/docker to v25.0.4 in go.mod",
            severity=1.0,
            adherence_type="binary",
            evaluator=check_docker_version,
        ),
        Rule(
            id="update_go_sum",
            description="Update go.sum to reflect the new docker package hash",
            severity=0.8,
            adherence_type="binary",
        ),
        Rule(
            id="replace_container_json",
            description="Replace deprecated ContainerJSON type with InspectResponse in all usages",
            severity=0.9,
            adherence_type="binary",
        ),
        Rule(
            id="add_auth_error_handling",
            description="Add error handling for the new AuthenticationError type introduced in v25",
            severity=0.7,
            adherence_type="float",
        ),
    ],
)

REMEDIATION_PLAN = """
CVE-2024-XXXX Remediation Policy:
1. Upgrade github.com/docker/docker from v24.0.0 to v25.0.4
2. Update go.sum with new hashes
3. Replace all usages of deprecated ContainerJSON with InspectResponse
4. Add error handling for the new AuthenticationError type
"""

GIT_DIFF = """
diff --git a/go.mod b/go.mod
--- a/go.mod
+++ b/go.mod
-\tgithub.com/docker/docker v24.0.0
+\tgithub.com/docker/docker v25.0.4

diff --git a/go.sum b/go.sum
--- a/go.sum
+++ b/go.sum
-github.com/docker/docker v24.0.0 h1:abc123...
+github.com/docker/docker v25.0.4 h1:def456...

diff --git a/internal/docker/client.go b/internal/docker/client.go
--- a/internal/docker/client.go
+++ b/internal/docker/client.go
-\tvar info docker.ContainerJSON
+\tvar info docker.InspectResponse

diff --git a/internal/docker/auth.go b/internal/docker/auth.go
--- a/internal/docker/auth.go
+++ b/internal/docker/auth.go
+\tif err != nil {
+\t\tif errors.As(err, &docker.AuthenticationError{}) {
+\t\t\treturn fmt.Errorf("docker auth failed: %w", err)
+\t\t}
+\t}

diff --git a/internal/metrics/prometheus.go b/internal/metrics/prometheus.go
--- a/internal/metrics/prometheus.go
+++ b/internal/metrics/prometheus.go
+\tdockerVersion.Set(25.0)
"""

test = PolicyTest(
    output=GIT_DIFF,
    policy=policy,
    system_prompt=(
        "You are an expert code analyst specialising in dependency security remediation. "
        "Evaluate whether the git diff correctly and completely implements the remediation policy."
    ),
    eval_mode="batch",
)

print("Evaluating SCA remediation diff…\n")
report = test.run()

print(f"Adherence score : {report.adherence.score:.3f}")
print(f"Coverage score  : {report.coverage.score:.3f}")
print(f"Compliance score: {report.compliance_score:.3f}\n")

print("Rule-by-rule results:")
for r in report.adherence.rule_results:
    status = "PASS" if r.passed else "FAIL"
    source_tag = f"[{r.source}]"
    print(f"  [{status}] {source_tag} {r.rule_id} (score={r.score:.2f}): {r.reasoning}")

if report.coverage.uncovered_actions:
    print("\nUnexpected changes (not in remediation policy):")
    for ua in report.coverage.uncovered_actions:
        print(f"  (sev={ua.severity:.2f}) {ua.description}")
        print(f"    → {ua.reasoning}")
else:
    print("\nNo unexpected changes detected.")

# ── Appendix ─────────────────────────────────────────────────────────────────

print("\n" + "=" * 72)
print("APPENDIX")
print("=" * 72)

# A. Policy metadata
print("\nA. Policy metadata")
print(f"   Name    : {policy.name}")
print(f"   Version : {policy.version}")
print(f"   Rules   : {len(policy.rules)}")

# B. Per-rule score table
print("\nB. Per-rule score breakdown")
col = "{:<30} {:>6} {:>8} {:>10}"
print("   " + col.format("Rule ID", "Sev", "Score", "Weighted"))
print("   " + "-" * 57)
total_weight = sum(r.severity for r in policy.rules)
for rr in report.adherence.rule_results:
    rule = next(r for r in policy.rules if r.id == rr.rule_id)
    weighted = rr.score * rule.severity
    print(
        "   "
        + col.format(
            rr.rule_id, f"{rule.severity:.2f}", f"{rr.score:.2f}", f"{weighted:.2f}"
        )
    )
print("   " + "-" * 57)
weighted_sum = sum(
    rr.score * next(r for r in policy.rules if r.id == rr.rule_id).severity
    for rr in report.adherence.rule_results
)
print(
    "   "
    + col.format(
        "TOTAL (normalised)",
        f"{total_weight:.2f}",
        "",
        f"{weighted_sum / total_weight:.2f}",
    )
)

# C. Severity-weighted pass / fail summary
passed_rules = [rr for rr in report.adherence.rule_results if rr.passed]
failed_rules = [rr for rr in report.adherence.rule_results if not rr.passed]
print("\nC. Pass / fail summary")
print(f"   Passed : {len(passed_rules)} / {len(policy.rules)} rules")
print(f"   Failed : {len(failed_rules)} / {len(policy.rules)} rules")
if failed_rules:
    print("   Failing rules:")
    for rr in failed_rules:
        print(f"     • {rr.rule_id} (score={rr.score:.2f})")

# D. Evaluation timestamp and metadata
print("\nD. Evaluation details")
print(f"   Evaluated at : {report.evaluated_at.isoformat()}")
if report.metadata:
    for k, v in report.metadata.items():
        print(f"   {k:<14}: {v}")

# E. Full report as JSON (for CI artefacts / audit logs)
print("\nE. Full report (JSON)")
print(report.model_dump_json(indent=2))
