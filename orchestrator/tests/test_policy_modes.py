from __future__ import annotations

from orchestrator.planner import ExecutionPlan
from orchestrator.policies import PolicyEngine


def test_local_only_allows_local_providers() -> None:
    policy = PolicyEngine("local-only")
    assert policy.provider_allowed("ollama") is True
    assert policy.provider_allowed("openai") is False


def test_admin_plan_requires_confirmation() -> None:
    policy = PolicyEngine("opt-in")
    plan = ExecutionPlan.model_validate(
        {
            "goal": "danger",
            "requires_user_confirmation": False,
            "steps": [{"tool": "bespoke.admin.raw_command", "arguments": {}}],
            "rollback": [],
        }
    )
    decision = policy.plan_decision(plan)
    assert decision.requires_confirmation is True

