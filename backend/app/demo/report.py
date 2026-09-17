from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.core.demo_clock import DemoClock
from app.demo.validation import DemoValidationReport, validate_demo_world


def render_report(report: DemoValidationReport) -> str:
    workload = report.working_dog_workload_km
    ordered_workload = sorted(workload.items(), key=lambda item: (item[1], item[0]))
    return "\n".join(
        [
            f"Dataset: {report.dataset_version}",
            f"Checksum: {report.checksum}",
            f"Dogs: {report.dog_count} total / {report.active_count} active / "
            f"{report.archived_count} archived",
            f"Cohorts: {json.dumps(report.cohort_counts, sort_keys=True)}",
            f"Classes: {json.dumps(report.class_counts, sort_keys=True)}",
            "Archive reasons: "
            f"{json.dumps(report.archive_reason_counts, sort_keys=True)}",
            "Current statuses: "
            f"{json.dumps(report.current_status_counts, sort_keys=True)}",
            f"Housing: {report.adult_enclosure_count} adult enclosures, "
            f"{report.puppy_area_count} puppy areas, "
            f"{report.historical_move_count} dogs with housing moves/history",
            "Litters:",
            *(
                f"  {row['code']} {row['birth_date']}: "
                f"mother={row['mother'] or 'external'}, "
                f"father={row['father'] or 'external'}; "
                f"members={', '.join(row['members'])}"
                for row in report.litter_rows
            ),
            f"Work: {report.session_count} sessions / "
            f"{report.participation_count} starts; distance sessions="
            f"{json.dumps(report.distance_session_counts, sort_keys=True)}",
            f"Eligible-dog workload km: min={report.workload_min_km}, "
            f"median={report.workload_median_km:g}, max={report.workload_max_km}",
            "Workload by dog: "
            + ", ".join(f"{name}={distance}" for name, distance in ordered_workload),
            "Puppy/junior workload: 0 km (validated)",
        ]
    )


def build_report(session: Session, clock: DemoClock) -> str:
    return render_report(validate_demo_world(session, clock))
