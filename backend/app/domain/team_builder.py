from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from statistics import median

SUPPORTED_TEAM_SIZES = (4, 6, 8, 10, 12)
PREFERRED_PAIR_BONUS = 120.0
HOME_PAIR_BONUS = 28.0
TEAM_7D_SPREAD_PENALTY = 0.8
TEAM_14D_SPREAD_PENALTY = 0.2
SOLVER_BEAM_WIDTH = 240


@dataclass(frozen=True)
class Candidate:
    dog_id: str
    name: str
    roles: frozenset[str]
    housing_code: str | None
    km_7d: int
    km_14d: int
    season_km: int
    starts_14d: int
    days_since_work: int | None
    planned_km: int

    def role_capable(self, role: str) -> bool:
        return role in self.roles

    @property
    def workload_score(self) -> float:
        recovery_days = min(
            self.days_since_work if self.days_since_work is not None else 14, 14
        )
        return (
            recovery_days * 1.3
            - self.km_7d * 1.8
            - self.km_14d * 0.55
            - self.season_km * 0.04
            - self.starts_14d * 1.5
            - self.planned_km * 1.5
        )


@dataclass(frozen=True)
class PairRequest:
    team_index: int
    pair_index: int
    role: str


@dataclass(frozen=True)
class Slot:
    team_index: int
    pair_index: int
    role: str
    side: str
    dog_id: str
    explanations: tuple[str, ...]


@dataclass(frozen=True)
class GeneratedLineup:
    team_count: int
    team_size: int
    slots: tuple[Slot, ...]
    unassigned: tuple[tuple[str, str], ...]


class TeamBuilderSolveError(ValueError):
    def __init__(
        self, code: str, message: str, details: dict[str, int] | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def recommended_configuration(pool_size: int) -> tuple[int, int]:
    if pool_size < 4:
        return (1, 4)
    if pool_size in SUPPORTED_TEAM_SIZES:
        return (1, pool_size)
    exact = [
        (count, size)
        for size in SUPPORTED_TEAM_SIZES
        for count in range(2, 7)
        if count * size == pool_size
    ]
    if exact:
        return min(exact, key=lambda item: (abs(item[1] - 8), item[0], item[1]))
    configurations = [
        (count, size)
        for size in SUPPORTED_TEAM_SIZES
        for count in range(1, 7)
        if count * size <= pool_size
    ]
    return max(
        configurations,
        key=lambda item: (item[0] * item[1], -abs(item[1] - 8), -item[0]),
    )


def harness_pairs(team_count: int, team_size: int) -> tuple[PairRequest, ...]:
    pair_count = team_size // 2
    requests: list[PairRequest] = []
    for role, pair_indexes in (
        ("lead", (0,)),
        ("wheel", (pair_count - 1,)),
        ("team", tuple(range(1, pair_count - 1))),
    ):
        for pair_index in pair_indexes:
            for team_index in range(team_count):
                requests.append(PairRequest(team_index, pair_index, role))
    return tuple(requests)


def validate_role_capability(candidate: Candidate, role: str) -> None:
    if not candidate.role_capable(role):
        raise TeamBuilderSolveError(
            "role_mismatch", f"{candidate.name} is not {role}-capable."
        )


@dataclass(frozen=True)
class _State:
    pairs: tuple[tuple[PairRequest, Candidate, Candidate, tuple[str, ...]], ...]
    used: frozenset[str]
    team_km_7d: tuple[int, ...]
    team_km_14d: tuple[int, ...]
    score: float


def generate_lineup(
    candidates: list[Candidate],
    *,
    team_count: int,
    team_size: int,
    preferred_pairs: set[frozenset[str]],
    hard_conflicts: set[frozenset[str]],
) -> GeneratedLineup:
    _validate_configuration(candidates, team_count, team_size)
    requests = harness_pairs(team_count, team_size)
    required_leads = team_count * 2
    required_wheels = team_count * 2
    lead_count = sum(candidate.role_capable("lead") for candidate in candidates)
    wheel_count = sum(candidate.role_capable("wheel") for candidate in candidates)
    if lead_count < required_leads:
        raise TeamBuilderSolveError(
            "lead_shortage",
            f"Need {required_leads} lead-capable dogs; selected pool has {lead_count}.",
            {"required": required_leads, "available": lead_count},
        )
    if wheel_count < required_wheels:
        raise TeamBuilderSolveError(
            "wheel_shortage",
            f"Need {required_wheels} wheel-capable dogs; "
            f"selected pool has {wheel_count}.",
            {"required": required_wheels, "available": wheel_count},
        )

    states = [
        _State(
            pairs=(),
            used=frozenset(),
            team_km_7d=(0,) * team_count,
            team_km_14d=(0,) * team_count,
            score=0,
        )
    ]
    for request in requests:
        expanded: list[_State] = []
        for state in states:
            available = [
                candidate
                for candidate in candidates
                if candidate.dog_id not in state.used
                and candidate.role_capable(request.role)
            ]
            for first, second in combinations(available, 2):
                pair_key = frozenset((first.dog_id, second.dog_id))
                if pair_key in hard_conflicts:
                    continue
                left, right = sorted((first, second), key=_candidate_key)
                explanations = _pair_explanations(
                    left, right, pair_key, preferred_pairs
                )
                km_7d = list(state.team_km_7d)
                km_14d = list(state.team_km_14d)
                km_7d[request.team_index] += left.km_7d + right.km_7d
                km_14d[request.team_index] += left.km_14d + right.km_14d
                pair_score = left.workload_score + right.workload_score
                if pair_key in preferred_pairs:
                    pair_score += PREFERRED_PAIR_BONUS
                if left.housing_code and left.housing_code == right.housing_code:
                    pair_score += HOME_PAIR_BONUS
                score = (
                    state.score
                    + pair_score
                    - _spread(km_7d) * TEAM_7D_SPREAD_PENALTY
                    - _spread(km_14d) * TEAM_14D_SPREAD_PENALTY
                )
                expanded.append(
                    _State(
                        pairs=state.pairs + ((request, left, right, explanations),),
                        used=state.used | {left.dog_id, right.dog_id},
                        team_km_7d=tuple(km_7d),
                        team_km_14d=tuple(km_14d),
                        score=score,
                    )
                )
        if not expanded:
            raise TeamBuilderSolveError(
                "constraints_unsatisfied",
                "Role overlap and hard pair conflicts prevent a complete arrangement.",
            )
        expanded.sort(key=_state_key)
        states = expanded[:SOLVER_BEAM_WIDTH]

    best = states[0]
    slots: list[Slot] = []
    for request, left, right, pair_explanations in best.pairs:
        for side, candidate in (("left", left), ("right", right)):
            slot_reasons = [f"{request.role.title()} capable", *pair_explanations]
            if candidate.km_7d <= median(item.km_7d for item in candidates):
                slot_reasons.append("Lower recent workload")
            if candidate.days_since_work is not None and candidate.days_since_work >= 3:
                slot_reasons.append(f"{candidate.days_since_work} days since last work")
            slots.append(
                Slot(
                    team_index=request.team_index,
                    pair_index=request.pair_index,
                    role=request.role,
                    side=side,
                    dog_id=candidate.dog_id,
                    explanations=tuple(dict.fromkeys(slot_reasons)),
                )
            )

    used = {slot.dog_id for slot in slots}
    assigned = [candidate for candidate in candidates if candidate.dog_id in used]
    assigned_median = (
        median([candidate.km_7d for candidate in assigned]) if assigned else 0
    )
    unassigned = []
    for candidate in sorted(candidates, key=_candidate_key):
        if candidate.dog_id in used:
            continue
        reason = (
            "Higher recent workload"
            if candidate.km_7d > assigned_median
            else "Not needed for requested team count"
        )
        unassigned.append((candidate.dog_id, reason))
    slots.sort(key=lambda slot: (slot.team_index, slot.pair_index, slot.side))
    return GeneratedLineup(team_count, team_size, tuple(slots), tuple(unassigned))


def _validate_configuration(
    candidates: list[Candidate], team_count: int, team_size: int
) -> None:
    if team_size not in SUPPORTED_TEAM_SIZES:
        raise TeamBuilderSolveError(
            "invalid_team_size", "Team size must be 4, 6, 8, 10, or 12."
        )
    if team_count < 1 or team_count > 6:
        raise TeamBuilderSolveError(
            "invalid_team_count", "Team count must be between 1 and 6."
        )
    requested = team_count * team_size
    if requested > len(candidates):
        raise TeamBuilderSolveError(
            "insufficient_pool",
            f"Only {len(candidates)} eligible selected dogs remain for "
            f"{team_count} × {team_size} ({requested} slots).",
            {"required": requested, "available": len(candidates)},
        )


def _candidate_key(candidate: Candidate) -> tuple[str, str]:
    return (candidate.name.casefold(), candidate.dog_id)


def _state_key(state: _State) -> tuple[float, tuple[str, ...]]:
    signature = tuple(dog.dog_id for pair in state.pairs for dog in (pair[1], pair[2]))
    return (-round(state.score, 6), signature)


def _spread(values: list[int]) -> int:
    assigned = [value for value in values if value > 0]
    return max(assigned) - min(assigned) if len(assigned) > 1 else 0


def _pair_explanations(
    first: Candidate,
    second: Candidate,
    pair_key: frozenset[str],
    preferred_pairs: set[frozenset[str]],
) -> tuple[str, ...]:
    reasons: list[str] = []
    if pair_key in preferred_pairs:
        reasons.append("Preferred pair")
    if first.housing_code and first.housing_code == second.housing_code:
        reasons.append("Home pair")
    return tuple(reasons)
