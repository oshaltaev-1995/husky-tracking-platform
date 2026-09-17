import pytest

from app.domain.team_builder import (
    Candidate,
    TeamBuilderSolveError,
    generate_lineup,
    validate_role_capability,
)


def candidate(
    name: str,
    *,
    roles: tuple[str, ...] = ("lead", "team", "wheel"),
    housing: str | None = None,
    km_7d: int = 0,
    km_14d: int = 0,
    season_km: int = 0,
) -> Candidate:
    return Candidate(
        dog_id=name.lower(),
        name=name,
        roles=frozenset(roles),
        housing_code=housing,
        km_7d=km_7d,
        km_14d=km_14d,
        season_km=season_km,
        starts_14d=0,
        days_since_work=5,
        planned_km=5,
    )


def paired(lineup: object, first: str, second: str) -> bool:
    slots = lineup.slots  # type: ignore[attr-defined]
    by_pair: dict[tuple[int, int], set[str]] = {}
    for slot in slots:
        by_pair.setdefault((slot.team_index, slot.pair_index), set()).add(slot.dog_id)
    return {first, second} in by_pair.values()


def test_preferred_pair_improves_placement() -> None:
    candidates = [candidate(name) for name in ("A", "B", "C", "D")]
    lineup = generate_lineup(
        candidates,
        team_count=1,
        team_size=4,
        preferred_pairs={frozenset(("a", "b"))},
        hard_conflicts=set(),
    )
    assert paired(lineup, "a", "b")
    assert any(
        "Preferred pair" in slot.explanations
        for slot in lineup.slots
        if slot.dog_id in {"a", "b"}
    )


def test_home_pair_is_soft_and_hard_conflict_wins() -> None:
    candidates = [
        candidate("A", housing="A1-01"),
        candidate("B", housing="A1-01"),
        candidate("C", housing="A1-02"),
        candidate("D", housing="A1-03"),
    ]
    lineup = generate_lineup(
        candidates,
        team_count=1,
        team_size=4,
        preferred_pairs=set(),
        hard_conflicts={frozenset(("a", "b"))},
    )
    assert not paired(lineup, "a", "b")


def test_underused_dog_is_preferred_without_overriding_role() -> None:
    candidates = [
        candidate("A", km_7d=60, km_14d=100, season_km=300),
        candidate("B"),
        candidate("C"),
        candidate("D"),
        candidate("E"),
    ]
    lineup = generate_lineup(
        candidates,
        team_count=1,
        team_size=4,
        preferred_pairs=set(),
        hard_conflicts=set(),
    )
    assert {dog_id for dog_id, _ in lineup.unassigned} == {"a"}

    role_bound = [
        candidate("Lead A", roles=("lead",), km_7d=60),
        candidate("Lead B", roles=("lead",), km_7d=60),
        candidate("Wheel A", roles=("wheel",)),
        candidate("Wheel B", roles=("wheel",)),
        candidate("Fresh Team", roles=("team",)),
    ]
    lineup = generate_lineup(
        role_bound,
        team_count=1,
        team_size=4,
        preferred_pairs=set(),
        hard_conflicts=set(),
    )
    assert "fresh team" in {dog_id for dog_id, _ in lineup.unassigned}


@pytest.mark.parametrize("size", [3, 5, 7, 14])
def test_unsupported_team_sizes_are_rejected(size: int) -> None:
    with pytest.raises(TeamBuilderSolveError, match="4, 6, 8, 10, or 12"):
        generate_lineup(
            [candidate(str(index)) for index in range(20)],
            team_count=1,
            team_size=size,
            preferred_pairs=set(),
            hard_conflicts=set(),
        )


@pytest.mark.parametrize(
    ("roles", "role", "valid"),
    [
        (("lead",), "lead", True),
        (("team",), "lead", False),
        (("team",), "team", True),
        (("lead",), "team", False),
        (("wheel",), "wheel", True),
        (("team",), "wheel", False),
        (("lead", "team", "wheel"), "lead", True),
        (("lead", "team", "wheel"), "team", True),
        (("lead", "team", "wheel"), "wheel", True),
    ],
)
def test_slot_role_capability_is_authoritative(
    roles: tuple[str, ...], role: str, valid: bool
) -> None:
    dog = candidate("Role dog", roles=roles)
    if valid:
        validate_role_capability(dog, role)
    else:
        with pytest.raises(TeamBuilderSolveError, match=f"not {role}-capable"):
            validate_role_capability(dog, role)
