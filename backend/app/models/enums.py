from enum import StrEnum


class DogSex(StrEnum):
    FEMALE = "female"
    MALE = "male"


class DogClass(StrEnum):
    PUPPY = "puppy"
    JUNIOR = "junior"
    TRAINING = "training"
    STANDARD = "standard"


class LifecycleState(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class AvailabilityState(StrEnum):
    AVAILABLE = "available"
    INJURED = "injured"
    REST = "rest"
    RESTRICTED = "restricted"
    RETIRED = "retired"


class ArchiveReason(StrEnum):
    EUTHANIZED = "euthanized"
    DECEASED = "deceased"
    REHOMED_TO_GUIDE = "rehomed_to_guide"


class WorkingRole(StrEnum):
    LEAD = "lead"
    TEAM = "team"
    WHEEL = "wheel"


class RelationshipKind(StrEnum):
    PREFERRED_PAIR = "preferred_pair"
    HARD_CONFLICT = "hard_conflict"


class LocationType(StrEnum):
    ADULT_ENCLOSURE = "adult_enclosure"
    PUPPY_AREA = "puppy_area"


class ActivityType(StrEnum):
    SLED_TRAINING = "sled_training"


class PlannedActivityType(StrEnum):
    TRAINING = "training"
    OPEN_SPACE_WALK = "open_space_walk"
    INDIVIDUAL_EXERCISE = "individual_exercise"
    REST = "rest"


class TeamSide(StrEnum):
    LEFT = "left"
    RIGHT = "right"
