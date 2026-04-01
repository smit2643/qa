from models import (
    Organization, User, Membership, Role,
    Project, TestSuite, TestCase, TestStep,
    TestRun, RunStatus, TriggerType,
    TestResult, ResultStatus,
    VisualDiff, HealingSuggestion, HealingStatus,
    AuditLog,
)

def test_organization_fields():
    org = Organization(name="Acme Corp", slug="acme-corp")
    assert org.slug == "acme-corp"
    assert org.plan == "free"

def test_project_generates_unique_api_keys():
    p1 = Project(organization_id="org1", name="App1", target_url="https://app1.com")
    p2 = Project(organization_id="org1", name="App2", target_url="https://app2.com")
    assert p1.api_key != p2.api_key
    assert len(p1.api_key) == 64

def test_test_run_defaults():
    run = TestRun(suite_id="suite1")
    assert run.status == RunStatus.queued
    assert run.browser == "chromium"

def test_test_result_defaults():
    result = TestResult(run_id="run1")
    assert result.status == ResultStatus.pending

def test_healing_suggestion_defaults():
    h = HealingSuggestion(
        result_id="r1", test_id="t1",
        broken_selector="div.old", suggested_selector="role=button"
    )
    assert h.status == HealingStatus.pending

def test_all_models_imported():
    # Ensure __init__.py exports everything
    models = [
        Organization, User, Membership, Project, TestSuite,
        TestCase, TestStep, TestRun, TestResult,
        VisualDiff, HealingSuggestion, AuditLog,
    ]
    for model in models:
        assert hasattr(model, "__tablename__")
