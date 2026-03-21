from __future__ import annotations

from dataclasses import dataclass

from .planner import ExecutionPlan


SAFE_PREFIX = "bespoke.safe."
ADMIN_PREFIX = "bespoke.admin."


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    requires_confirmation: bool
    reason: str


class PolicyEngine:
    def __init__(self, mode: str, consent_required_for_risky: bool = True) -> None:
        self.mode = mode
        self.consent_required_for_risky = consent_required_for_risky

    def provider_allowed(self, provider: str) -> bool:
        if self.mode == "local-only":
            return provider in {"ollama", "llama_cpp", "mock"}
        if self.mode == "cloud-ok-no-train":
            return provider in {"mock", "openai", "anthropic", "gemini", "ollama", "llama_cpp"}
        if self.mode == "opt-in":
            return True
        return provider == "mock"

    def plan_decision(self, plan: ExecutionPlan) -> PolicyDecision:
        has_admin = any(step.tool.startswith(ADMIN_PREFIX) for step in plan.steps)
        if has_admin:
            return PolicyDecision(
                allowed=True,
                requires_confirmation=True,
                reason="admin tools require explicit confirmation",
            )
        requires_confirmation = self.consent_required_for_risky and any(
            step.tool.startswith(SAFE_PREFIX) and "snapshot" in step.tool for step in plan.steps
        )
        return PolicyDecision(
            allowed=True,
            requires_confirmation=requires_confirmation or plan.requires_user_confirmation,
            reason="safe plan" if not requires_confirmation else "sensitive safe tool requires confirmation",
        )

