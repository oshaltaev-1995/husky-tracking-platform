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
from app.operations.schemas import Check, ClaimReference, Entity, Snapshot, ToolName
from app.operations.tools import READ_TOOLS

# Only identifier candidates accept these explicit dash/minus representations.
# Never normalize prose or names. Invisible/bidi controls are detected, not repaired.
_DASHES = "-\u2010\u2011\u2012\u2013\u2014\u2015\u2212\ufe63\uff0d"
_CONTROLS = (
    "\u00ad\u034f\u061c\u180e\u200b\u200c\u200d\u200e\u200f"
    "\u202a\u202b\u202c\u202d\u202e"
    "\u2060\u2061\u2062\u2063\u2064\u2065\u2066\u2067\u2068"
    "\u2069\u206a\u206b\u206c\u206d\u206e\u206f\ufeff"
)
_DASH = f"[{re.escape(_DASHES)}]"
_CONTROL = f"[{re.escape(_CONTROLS)}]"
_IDENTIFIER_BOUNDARY = rf"[\w{re.escape(_DASHES + _CONTROLS)}]"
_UUID = (
    rf"[0-9a-fA-F]{{8}}(?:{_DASH}[0-9a-fA-F]{{4}}){{3}}"
    rf"{_DASH}[0-9a-fA-F]{{12}}"
)
_UUID_ANYWHERE = re.compile(_UUID)
_TOKEN = re.compile(rf"(?<!{_IDENTIFIER_BOUNDARY}){_UUID}(?!{_IDENTIFIER_BOUNDARY})")
# Near-UUID group lengths catch malformed and embedded candidates too. Count the
# alphanumerics, allowing detection of controls between them, regardless of count.
# A controlled candidate never shares a valid token span, so it fails closed below.
_ID_CHAR = rf"[A-Za-z0-9]{_CONTROL}*"
_UUID_LIKE = re.compile(
    rf"(?:{_ID_CHAR}){{7,9}}(?:{_DASH}{_CONTROL}*(?:{_ID_CHAR}){{3,5}}){{3}}"
    rf"{_DASH}{_CONTROL}*(?:{_ID_CHAR}){{10,14}}"
)
_ID_LIST = re.compile(
    rf"\bIDs?(?:\s*:\s*|\s+)(?P<list>{_UUID}"
    rf"(?:\s*(?:,\s*(?:and\s+)?|\band\s+){_UUID})*)",
    re.I,
)
_CANONICAL_DASHES = str.maketrans(dict.fromkeys(_DASHES, "-"))
_UNRESOLVED = (
    "The AI explanation contains a reference that could not be matched to this "
    "snapshot. The saved-day summary and checked facts remain available."
)
_TOOL_LABELS: dict[str, str] = {
    "get_day_plan": "saved day plan",
    "get_saved_teams": "saved teams",
    "get_dog_states": "dated dog states",
    "get_workload": "actual workload",
    "get_housing": "dated housing",
    "validate_day": "saved-day check",
}
_EVIDENCE_LABELS = {
    "PLAN_PRESENCE": "saved-plan record",
    "ACTIVITY_DISTANCE": "activity distance",
    "PARTICIPANT_ELIGIBILITY": "participant eligibility",
    "SAVED_LINEUP": "saved-team check",
    "ACTUAL_RECORDING": "actual-recording state",
    "PLANNED_DAILY_KM": "planned workload",
    "ACTUAL_DAILY_KM": "recorded workload",
    "DATED_STATE_MISSING": "dated information",
    "DOG_STATE": "dated dog state",
    "WORKLOAD_BEFORE": "previous actual workload",
    "HOUSING_INFORMATION": "dated housing",
    "ACTUAL_LEDGER": "recorded-work totals",
}
_TECHNICAL_TOKEN = re.compile(
    r"(?<![\w-])(?:" + "|".join(READ_TOOLS) + r"|e-\d+)(?![\w-])"
)
_PRESENTATION_TOKEN = re.compile(_TOKEN.pattern + "|" + _TECHNICAL_TOKEN.pattern)
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

    def activity_label(self, identity: str) -> str | None:
        """One frozen label for summary, findings and activity destinations.

        The snapshot deliberately excludes private activity titles/notes and
        time-of-day. Its saved sequence disambiguates even identical activities.
        """
        activity = next(
            (row for row in self.snapshot.activities if str(row.id) == identity),
            None,
        )
        if activity is None:
            return None
        kind = _KIND_LABELS.get(activity.kind, "Planned activity")
        distance = (
            f" · {activity.distance_km} km" if activity.distance_km is not None else ""
        )
        return f"{kind}{distance} — activity {activity.sequence}"

    def _entity_link(self, identity: str) -> ReviewLink | None:
        matches: list[ReviewLink] = []
        dog = self.dog_link(identity)
        if dog is not None:
            matches.append(dog)
        if identity in self._activity_order:
            entity = Entity(kind="activity", id=identity)
            matches.append(
                ReviewLink(
                    entity=entity,
                    label=self.activity_label(identity) or "Planned activity",
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

    def _evidence_label(
        self, identity: str, references: tuple[ClaimReference, ...]
    ) -> str | None:
        # Reference validation remains authoritative. Presentation additionally
        # requires one unambiguous frozen record/check; the number encodes nothing.
        evidence = [row for row in self.snapshot.evidence if row.id == identity]
        checks = [row for row in self.snapshot.checks if identity in row.evidence_ids]
        refs = [row for row in references if row.evidence_id == identity]
        if len(evidence) != 1 or len(checks) != 1 or not refs:
            return None
        record, check = evidence[0], checks[0]
        if (
            record.selected_date != self.snapshot.selected_date
            or check.selected_date != self.snapshot.selected_date
            or any(
                ref.snapshot_id != self.snapshot.id
                or ref.selected_date != self.snapshot.selected_date
                or ref.entity not in record.entities
                for ref in refs
            )
        ):
            return None
        return _EVIDENCE_LABELS.get(check.rule)

    def explanation(
        self,
        text: str,
        *,
        executed_tools: tuple[ToolName, ...] = (),
        references: tuple[ClaimReference, ...] = (),
    ) -> ReviewDisplay:
        def unresolved() -> ReviewDisplay:
            return ReviewDisplay(status="unresolved", segments=(), message=_UNRESOLVED)

        if len(text) > 4000:
            return unresolved()
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
        lists = tuple(_ID_LIST.finditer(text))
        labels: dict[str, ReviewLink] = {}
        for match in matches:
            identity = match.group()
            found = self._entity_link(identity.translate(_CANONICAL_DASHES).lower())
            if found is None:
                return unresolved()
            expected = self._expected_kind(text[: match.start()])
            if expected is None:
                # An explicit typed ID list keeps its kind for every member;
                # commas/"and" must not let an activity masquerade as a dog.
                expected = next(
                    (
                        self._expected_kind(text[: group.start()])
                        for group in lists
                        if group.start("list") <= match.start()
                        and match.end() <= group.end("list")
                    ),
                    None,
                )
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
        plain = ""

        def flush_plain() -> None:
            nonlocal plain
            # Replacement can expand a bounded raw explanation. Keep existing DTO
            # bounds without turning a presentation failure into a lost summary.
            while plain:
                segments.append(ReviewDisplaySegment(text=plain[:4000]))
                plain = plain[4000:]

        for match in _PRESENTATION_TOKEN.finditer(text):
            plain += text[offset : match.start()]
            token = match.group()
            if token in labels:
                flush_plain()
                found = labels[token]
                segments.append(
                    ReviewDisplaySegment(
                        text=found.label, entity=found.entity, path=found.path
                    )
                )
            elif token in self._names:
                # Identity takes priority, including literal names that resemble
                # internal tokens. Resolved dog-name segments are never rescanned.
                plain += token
            elif token in READ_TOOLS:
                if token not in executed_tools:
                    return unresolved()
                plain += _TOOL_LABELS[token]
            else:
                label = self._evidence_label(token, references)
                if label is None:
                    return unresolved()
                plain += label
            offset = match.end()
        plain += text[offset:]
        flush_plain()
        if len(segments) > 256:
            return unresolved()
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
                    label=self.activity_label(str(activity.id)),
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
