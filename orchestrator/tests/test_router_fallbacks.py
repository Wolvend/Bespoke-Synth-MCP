from __future__ import annotations

from orchestrator.config import Settings
from orchestrator.model_router import ModelRouter


async def test_mock_provider_returns_plan_json() -> None:
    router = ModelRouter(Settings())
    response = await router.generate("mock", "system", "set cutoff")
    assert "steps" in response.text

