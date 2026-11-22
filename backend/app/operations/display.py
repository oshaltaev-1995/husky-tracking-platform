"""Deterministic client presentation of one accepted, detached review snapshot.

Entity identity and evidence are never repaired here. Provider text is untrusted
plain text; only exact snapshot entities receive local labels/links. Unknown or
malformed identity text suppresses that explanation, not the frozen facts.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable

from app.operations.api_schemas import (
    ReviewActivitySummary,
    ReviewActualSummary,
    ReviewDisplay,
    ReviewDisplaySegment,
    ReviewFindingGroup,
    ReviewLink,
    ReviewOperationalSummary,
    ReviewStatusCounts,
)
from app.operations.schemas import Check, Entity, Snapshot

# Boundaries matter: replacing a substring of an unknown identifier is guessing.
_UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
_UUID_ANYWHERE = re.compile(_UUID)
_TOKEN = re.compile(rf"(?<![\w-]){_UUID}(?![\w-])")
_UUID_LIKE = re.compile(
    r"(?<![\w-])[A-Za-z0-9]{7,9}(?:-[A-Za-z0-9]{3,5}){3}"
    r"-[A-Za-z0-9]{10,14}(?![\w-])"
)
_ID_LIST = re.compile(
    rf"\bIDs?(?:\s*:\s*|\s+)(?P<list>{_UUID}(?:\s*(?:,|and)\s*{_UUID})*)",
    re.I,
)
_UNRESOLVED = (
    "The AI explanation contains a reference that could not be matched to this "
    "snapshot. The saved-day summary and checked facts remain available."
)
_KIND_LABELS = {
    "training": "Training",
    "open_space_walk": "Open-space walk",
    "individual_exercise": "Individual exercise",
    "rest": "Rest",
}


def status_counts(checks: tuple[Check, ...]) -> ReviewStatusCounts:
    counts = Counter(check.status for check in checks)
    return ReviewStatusCounts(
        passed=counts["pass"],
        violations=counts["violation"],
        attention=counts["attention"],
        unverified=counts["unverified"],
    )


class FrozenDisplay:
    """Labels, summary and grouping use only this review's frozen snapshot."""

    def __init__(self, snapshot: Snapshot, link: Callable[[Entity], str]) -> None:
        self.snapshot = snapshot
        self._link = link
        self._dogs = {str(dog.id): dog for dog in snapshot.dogs}
        self._names = Counter(dog.name for dog in snapshot.dogs)
        self._activity_order = {
            str(activity.id): activity.sequence for activity in snapshot.activities
        }
        self._actual_ids = {str(row.id) for row in snapshot.actual}

    def dog_link(self, identity: str) -> ReviewLink | None:
        dog = self._dogs.get(identity)
        if dog is None:
            return None
        label = dog.name
        if self._names[dog.name] > 1:
            # Keep the real name. Housing/class are genuine frozen context, not a
            # fabricated Dog1/Dog2 identity; links stay separate even if both match.
            context = [value for value in (dog.housing_code, dog.dog_class) if value]
            if context:
                label += " · " + " · ".join(context)
        entity = Entity(kind="dog", id=identity)
        return ReviewLink(entity=entity, label=label, path=self._link(entity))

    def _entity_link(self, identity: str) -> ReviewLink | None:
        matches: list[ReviewLink] = []
        dog = self.dog_link(identity)
        if dog is not None:
            matches.append(dog)
        if identity in self._activity_order:
            activity = next(
                row for row in self.snapshot.activities if str(row.id) == identity
            )
            kind = _KIND_LABELS.get(activity.kind, "Planned activity")
            entity = Entity(kind="activity", id=identity)
            matches.append(
                ReviewLink(
                    entity=entity,
                    label=f"{kind} · activity {self._activity_order[identity]}",
                    path=self._link(entity),
                )
            )
        if identity in self._actual_ids:
            entity = Entity(kind="actual", id=identity)
            matches.append(
                ReviewLink(
                    entity=entity, label="Recorded work", path=self._link(entity)
                )
            )
        # An identity appearing under two entity kinds must not be guessed.
        return matches[0] if len(matches) == 1 else None

    @staticmethod
    def _expected_kind(before: str) -> str | None:
        patterns = {
            "dog": r"\b(?:dog|participant)s?(?:\s+IDs?)?\s*[:#]?\s*$",
            "activity": r"\bactivit(?:y|ies)(?:\s+IDs?)?\s*[:#]?\s*$",
            "actual": r"\b(?:actual|session)s?(?:\s+IDs?)?\s*[:#]?\s*$",
        }
        return next(
            (
                kind
                for kind, pattern in patterns.items()
                if re.search(pattern, before, re.I)
            ),
            None,
        )

    def explanation(self, text: str) -> ReviewDisplay:
        def unresolved() -> ReviewDisplay:
            return ReviewDisplay(status="unresolved", segments=(), message=_UNRESOLVED)

        if not text.strip():
            return ReviewDisplay(
                status="unresolved",
                segments=(),
                message="The AI explanation was empty. The saved-day summary "
                "and checked facts remain available.",
            )

        # Reject malformed/embedded tokens before replacing any identity. A plain
        # number/date is never a candidate, and an unknown token never becomes a name.
        matches = tuple(_TOKEN.finditer(text))
        spans = {match.span() for match in matches}
        if any(match.span() not in spans for match in _UUID_ANYWHERE.finditer(text)):
            return unresolved()
        if any(match.span() not in spans for match in _UUID_LIKE.finditer(text)):
            return unresolved()
        labels: dict[str, ReviewLink] = {}
        for match in matches:
            identity = match.group()
            found = self._entity_link(identity.lower())
            if found is None:
                return unresolved()
            expected = self._expected_kind(text[: match.start()])
            if expected is not None and found.entity.kind != expected:
                return unresolved()
            labels[identity] = found

        # A narrowly recognised list marker is presentation, not a factual claim.
        # Only verified lists lose "IDs"; all surrounding assertions stay verbatim.
        def list_names(match: re.Match[str]) -> str:
            identities = _TOKEN.findall(match.group("list"))
            return (
                match.group("list")
                if identities and all(identity in labels for identity in identities)
                else match.group()
            )

        text = _ID_LIST.sub(list_names, text)
        segments: list[ReviewDisplaySegment] = []
        offset = 0
        for match in _TOKEN.finditer(text):
            if offset < match.start():
                segments.append(ReviewDisplaySegment(text=text[offset : match.start()]))
            found = labels[match.group()]
            segments.append(
                ReviewDisplaySegment(
                    text=found.label, entity=found.entity, path=found.path
                )
            )
            offset = match.end()
        if offset < len(text) or not segments:
            segments.append(ReviewDisplaySegment(text=text[offset:]))
        return ReviewDisplay(status="ready", segments=tuple(segments), message=None)

    def summary(self) -> ReviewOperationalSummary:
        activities: list[ReviewActivitySummary] = []
        for activity in self.snapshot.activities:
            selected = tuple(
                found
                for identity in activity.participants
                if (found := self.dog_link(str(identity))) is not None
            )
            activities.append(
                ReviewActivitySummary(
                    entity=Entity(kind="activity", id=str(activity.id)),
                    kind=activity.kind,
                    distance_km=activity.distance_km,
                    selected_pool_count=len(activity.participants),
                    selected_dogs=selected,
                    omitted_selected_dogs=len(activity.participants) - len(selected),
                    saved_teams=len(activity.teams)
                    if activity.kind == "training"
                    else None,
                    actual_status=activity.actual_status,
                )
            )
        return ReviewOperationalSummary(
            plan_exists=self.snapshot.plan_exists,
            activity_count=len(self.snapshot.activities),
            selected_unique_dogs=len(
                {
                    dog
                    for activity in self.snapshot.activities
                    for dog in activity.participants
                }
            ),
            selected_participations=sum(
                len(activity.participants) for activity in self.snapshot.activities
            ),
            activities=tuple(activities),
            omitted_activities=0,
            actual=ReviewActualSummary(
                sessions=len(self.snapshot.actual),
                dogs_worked=len(
                    {dog for row in self.snapshot.actual for dog in row.participants}
                ),
                dog_starts=sum(len(row.participants) for row in self.snapshot.actual),
                dog_km=sum(
                    row.distance_km * len(row.participants)
                    for row in self.snapshot.actual
                ),
            ),
        )

    def finding_groups(self) -> tuple[ReviewFindingGroup, ...]:
        selected = {
            str(identity)
            for activity in self.snapshot.activities
            for identity in activity.participants
        }
        primary: list[Check] = []
        other: list[Check] = []
        for check in self.snapshot.checks:
            if check.status == "pass":
                continue
            dogs = {entity.id for entity in check.entities if entity.kind == "dog"}
            # Activity/actual/day/housing checks and any selected dog stay primary.
            unrelated = (
                bool(dogs)
                and dogs.isdisjoint(selected)
                and all(entity.kind == "dog" for entity in check.entities)
            )
            (other if unrelated else primary).append(check)
        result: list[ReviewFindingGroup] = []
        remaining = 32
        for scope, all_checks in (("plan", primary), ("other_dogs", other)):
            included = tuple(all_checks[:remaining])
            remaining -= len(included)
            linked_ids = dict.fromkeys(
                entity.id
                for check in included
                for entity in check.entities
                if entity.kind == "dog"
            )
            links = tuple(
                found
                for identity in linked_ids
                if (found := self.dog_link(identity)) is not None
            )
            result.append(
                ReviewFindingGroup(
                    scope="plan" if scope == "plan" else "other_dogs",
                    findings=included,
                    status_counts=status_counts(tuple(all_checks)),
                    omitted_findings=len(all_checks) - len(included),
                    links=links,
                )
            )
        return tuple(result)
