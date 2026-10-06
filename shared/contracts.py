"""Inference results distinguish observations, heuristics and unavailable evidence."""
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator

DamageLabel = Literal['dent', 'scratch', 'crack', 'glass_shatter', 'lamp_broken', 'tire_flat']
CheckStatus = Literal['passed', 'flagged', 'inconclusive', 'unavailable', 'not_applicable']


class CheckResult(BaseModel):
    id: str
    status: CheckStatus
    detail: str
    method: str


class Detection(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, protected_namespaces=())
    label: DamageLabel
    confidence: float = Field(ge=0, le=1)
    bbox: list[float] = Field(min_length=4, max_length=4)

    @model_validator(mode='after')
    def normalized_box(self):
        if any(not 0 <= value <= 1 for value in self.bbox):
            raise ValueError('Bounding boxes must be normalized')
        return self


class AnalysisResult(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, protected_namespaces=())
    schema_version: Literal['2'] = '2'
    outcome: Literal['damage_detected', 'no_visible_damage', 'insufficient_evidence']
    damage_detected: bool
    detections: list[Detection]
    severity: Literal['minor', 'moderate', 'severe'] | None
    severity_score: float | None = Field(default=None, ge=0, le=1)
    detector_confidence: float | None = Field(default=None, ge=0, le=1)
    primary_damage_type: DamageLabel | None
    cost_estimate_min: float | None = Field(default=None, ge=0)
    cost_estimate_max: float | None = Field(default=None, ge=0)
    cost_breakdown: dict = Field(default_factory=dict)
    severity_reasoning: dict = Field(default_factory=dict)
    fraud_score: float = Field(ge=0, le=1)
    manipulation_score: float | None = Field(default=None, ge=0, le=1)
    fraud_flags: list[str] = Field(default_factory=list)
    checks: list[CheckResult]
    model_provenance: dict
    annotated_image_base64: str | None = None

    @model_validator(mode='after')
    def consistent_result(self):
        if self.damage_detected != bool(self.detections):
            raise ValueError('Damage flag and detections disagree')
        if self.outcome == 'damage_detected':
            if not self.detections or self.primary_damage_type is None or self.severity is None:
                raise ValueError('Detected damage needs a label and severity')
        elif self.detections or self.primary_damage_type is not None or self.severity is not None:
            raise ValueError('Abstention/empty results must not invent damage')
        if not self.detections and any(v is not None for v in (self.cost_estimate_min, self.cost_estimate_max)):
            raise ValueError('No repair estimate without detected damage')
        if (self.cost_estimate_min is None) != (self.cost_estimate_max is None):
            raise ValueError('Both estimate bounds must be present or absent')
        if self.cost_estimate_min is not None and self.cost_estimate_min > self.cost_estimate_max:
            raise ValueError('Estimate bounds are reversed')
        return self
