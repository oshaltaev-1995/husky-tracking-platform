import pytest

from app.domain.workload import (
    MAX_DAILY_DOG_DISTANCE_KM,
    WorkloadRuleViolation,
    validate_daily_dog_distances,
)


@pytest.mark.parametrize(
    ("distances", "expected_total"),
    [
        ([5], 5),
        ([10, 10, 10], 30),
        ([10, 10, 5, 5], 30),
        ([10, 5, 5, 5, 5], 30),
    ],
)
def test_valid_daily_sled_distance_combinations(
    distances: list[int], expected_total: int
) -> None:
    assert validate_daily_dog_distances(distances) == expected_total


def test_daily_sled_distance_above_limit_is_invalid() -> None:
    with pytest.raises(WorkloadRuleViolation, match="35 km exceeds 30 km"):
        validate_daily_dog_distances([10, 10, 10, 5])


def test_limit_is_a_shared_canonical_domain_constant() -> None:
    assert MAX_DAILY_DOG_DISTANCE_KM == 30
