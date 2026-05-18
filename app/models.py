from pydantic import BaseModel, field_validator
from typing import List, Optional
from enum import Enum
from datetime import datetime


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class ComponentInput(BaseModel):
    id: str
    name: str
    dependencies: List[str] = []

    @field_validator("id", "name")
    @classmethod
    def validate_non_empty(cls, v: str):
        if not v.strip():
            raise ValueError("Value cannot be empty")
        return v.strip()


class SystemRegisteredResponse(BaseModel):
    message: str
    component_count: int
    evaluation_levels: int


class SystemInput(BaseModel):
    components: List[ComponentInput]

    @field_validator("components")
    @classmethod
    def no_duplicates(cls, components: List[ComponentInput]) -> List[ComponentInput]:
        ids = [c.id for c in components]
        duplicate_ids = set([id for id in ids if ids.count(id) > 1])
        if duplicate_ids:
            raise ValueError(
                f"Duplicate component IDs found: {', '.join(duplicate_ids)}"
            )
        return components


class HealthEvent(BaseModel):
    component_id: str
    status: HealthStatus
    details: Optional[str] = None


class ComponentHealth(BaseModel):
    id: str
    name: str
    status: HealthStatus
    dependencies: List[str] = []
    alert: bool = False


class SystemHealthStatusResponse(BaseModel):
    overall_status: HealthStatus
    componenets: List[ComponentHealth]
    evaluatedatetime: datetime
    unhealthy_count: int = 0
    degraded_count: int = 0
    healthy_count: int = 0