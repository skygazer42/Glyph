"""Evaluate rule drafts without loading services or persisting rule files."""

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
import yaml

from app.agents.dsl_generator.rule_engine import PolicyEngine
from app.api.schemas import PreviewDSLRequest, TestDSLResponse


class DraftInput(BaseModel):
    model_config = ConfigDict(strict=True, extra="allow")

    name: str = Field(min_length=1, max_length=256, pattern=r"\S")
    type: Literal["string", "float", "number", "int", "integer", "bool", "boolean"] = "string"
    required: bool = True


class DraftOutput(BaseModel):
    model_config = ConfigDict(strict=True, extra="allow")

    status: str
    final_result: str
    trace_template: str = ""


class DraftRule(BaseModel):
    model_config = ConfigDict(strict=True, extra="allow")

    rule_id: str = Field(min_length=1, max_length=256, pattern=r"\S")
    inputs: list[DraftInput] = Field(default_factory=list)
    calc: dict[str, Any] = Field(default_factory=dict)
    output: DraftOutput
    policy_source: dict[str, Any] = Field(default_factory=dict)
    valid_period: dict[str, str | None] = Field(default_factory=dict)

    @model_validator(mode="after")
    def unique_input_names(self) -> "DraftRule":
        names = [item.name for item in self.inputs]
        if len(names) != len(set(names)):
            raise ValueError("inputs 中的参数名称不能重复")
        return self


router = APIRouter()


@router.post("/preview", response_model=TestDSLResponse)
def preview_dsl(request: PreviewDSLRequest) -> TestDSLResponse:
    """Parse and evaluate the supplied version without changing saved rules."""
    try:
        rule = yaml.safe_load(request.yaml_content)
        DraftRule.model_validate(rule)
    except (yaml.YAMLError, ValidationError, RecursionError) as error:
        raise HTTPException(status_code=400, detail=f"规则格式无效：{error}") from error

    result = PolicyEngine(rule_dir=None).execute_rule(rule, request.inputs)
    return TestDSLResponse(success=True, result=result)
