from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class TeamBuilderActivityRead(BaseModel):
    id: UUID
    date: date
    title: str
    distance_km: int
    participant_count: int
    plan_revision: int


class WorkloadMetricsRead(BaseModel):
    km_7d: int
    km_14d: int
    season_km: int
    starts_14d: int
    days_since_last_work: int | None
    planned_km_today: int


class TeamBuilderCandidateRead(BaseModel):
    id: UUID
    name: str
    housing_code: str | None
    dog_class: str | None
    availability: str | None
    capabilities: list[str]
    eligible: bool
    reasons: list[str]
    workload: WorkloadMetricsRead


class TeamRelationshipRead(BaseModel):
    dog_a_id: UUID
    dog_b_id: UUID
    kind: str


class TeamSlotRead(BaseModel):
    dog_id: UUID
    dog_name: str
    pair_index: int
    pair_label: str
    side: str
    harness_role: str
    position_order: int
    explanations: list[str]


class PlannedTeamRead(BaseModel):
    id: UUID | None = None
    sequence: int
    display_label: str
    team_size: int
    slots: list[TeamSlotRead]


class UnassignedDogRead(BaseModel):
    dog_id: UUID
    dog_name: str
    reason: str


class CapabilitySummaryRead(BaseModel):
    lead: int
    team: int
    wheel: int


class TeamBuilderContextRead(BaseModel):
    activity: TeamBuilderActivityRead
    recommended_team_count: int
    recommended_team_size: int
    supported_team_sizes: list[int]
    capability_summary: CapabilitySummaryRead
    candidates: list[TeamBuilderCandidateRead]
    relationships: list[TeamRelationshipRead]
    saved_teams: list[PlannedTeamRead]


class GenerateTeamsRequest(BaseModel):
    team_count: int = Field(ge=1, le=6)
    team_size: int


class GeneratedTeamsRead(BaseModel):
    activity: TeamBuilderActivityRead
    persisted: bool = False
    teams: list[PlannedTeamRead]
    unassigned: list[UnassignedDogRead]


class TeamSlotWrite(BaseModel):
    dog_id: UUID
    pair_index: int = Field(ge=0)
    side: str
    harness_role: str
    position_order: int = Field(ge=1)


class PlannedTeamWrite(BaseModel):
    sequence: int = Field(ge=1)
    display_label: str | None = Field(default=None, max_length=80)
    team_size: int
    slots: list[TeamSlotWrite]

    @model_validator(mode="after")
    def validate_slots(self) -> PlannedTeamWrite:
        if len(self.slots) != self.team_size:
            raise ValueError("each saved team must contain exactly its configured size")
        positions = [(slot.pair_index, slot.side) for slot in self.slots]
        if len(positions) != len(set(positions)):
            raise ValueError("a harness position cannot appear twice")
        return self


class SaveTeamsRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    replace_existing: bool = False
    teams: list[PlannedTeamWrite] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def validate_unique_dogs(self) -> SaveTeamsRequest:
        dog_ids = [slot.dog_id for team in self.teams for slot in team.slots]
        if len(dog_ids) != len(set(dog_ids)):
            raise ValueError("a dog may occupy only one slot in a Training activity")
        sequences = [team.sequence for team in self.teams]
        if sequences != list(range(1, len(sequences) + 1)):
            raise ValueError("team sequences must be contiguous starting at one")
        return self
