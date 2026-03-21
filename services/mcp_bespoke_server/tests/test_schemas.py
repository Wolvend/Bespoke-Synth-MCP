from __future__ import annotations

import pytest
from pydantic import ValidationError

from mcp_bespoke_server.schemas import BatchSetIn, GetParamIn, SetParamIn


def test_set_param_schema_accepts_valid_payload() -> None:
    payload = SetParamIn(path="filter~cutoff", value=0.25)
    assert payload.path == "filter~cutoff"


def test_get_param_rejects_empty_path() -> None:
    with pytest.raises(ValidationError):
        GetParamIn(path="")


def test_batch_set_rejects_too_many_items() -> None:
    with pytest.raises(ValidationError):
        BatchSetIn(ops=[{"path": "x", "value": 1}] * 501)

