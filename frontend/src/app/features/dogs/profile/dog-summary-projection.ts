import { DogProfileBundle, LocationView } from '../../../core/api/dogs.models';
import { workingRoleLabel } from '../../../shared/working-role-label';

/** Bounded summary detail; full notes and every dated event stay in the profile. */
export const DOG_SUMMARY_NOTES_LIMIT = 260;
export const DOG_SUMMARY_HISTORY_LIMIT = 3;

export interface DogSummaryHousing {
  readonly label: 'Current housing' | 'Last known housing';
  readonly code: string;
  readonly displayName: string;
}

export interface DogSummaryProjection {
  readonly name: string;
  readonly snapshotDate: string;
  readonly photoKey: string | null;
  readonly birthDate: string;
  readonly ageLabel: string;
  readonly sex: string;
  readonly neuterLabel: 'Neutered / spayed' | 'Intact';
  readonly neuteredOn: string | null;
  readonly litterCode: string | null;
  readonly litterBirthDate: string | null;
  readonly lifecycle: string;
  readonly operationalClass: string | null;
  readonly classIsHistorical: boolean;
  readonly availability: string | null;
  readonly capabilities: readonly string[];
  readonly housing: DogSummaryHousing | null;
  readonly archive: { readonly date: string; readonly reason: string } | null;
  readonly pedigree: {
    readonly mother: string | null;
    readonly father: string | null;
    readonly maternalGrandmother: string | null;
    readonly maternalGrandfather: string | null;
    readonly paternalGrandmother: string | null;
    readonly paternalGrandfather: string | null;
    readonly littermates: number;
    readonly offspring: number;
  };
  readonly work: {
    readonly seasonStart: string;
    readonly seasonEnd: string;
    readonly totalKm: number;
    readonly starts: number;
    readonly starts5km: number;
    readonly starts10km: number;
    readonly averageKmPerStart: number | null;
    readonly lastWorkDate: string | null;
  };
  readonly history: readonly {
    readonly date: string;
    readonly kind: 'Availability' | 'Class' | 'Lifecycle' | 'Housing';
    readonly value: string;
  }[];
  readonly workspaceHousing: {
    readonly date: string;
    readonly code: string;
    readonly displayName: string;
  } | null;
  readonly notes: { readonly text: string; readonly shortened: boolean } | null;
}

function label(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function calendarDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}

function housing(location: LocationView | null, current: boolean): DogSummaryHousing | null {
  return location ? Object.freeze({
    label: current ? 'Current housing' : 'Last known housing',
    code: location.code,
    displayName: location.display_name,
  }) : null;
}

function notesExcerpt(value: string | null): DogSummaryProjection['notes'] {
  const text = value?.trim().replace(/\s+/g, ' ');
  if (!text) return null;
  if (text.length <= DOG_SUMMARY_NOTES_LIMIT) return Object.freeze({ text, shortened: false });
  const prefix = text.slice(0, DOG_SUMMARY_NOTES_LIMIT - 1);
  const boundary = prefix.search(/\s+\S*$/);
  const excerpt = (boundary > 0 ? prefix.slice(0, boundary) : prefix).trimEnd();
  return Object.freeze({ text: `${excerpt}…`, shortened: true });
}

/**
 * A detached display projection from one completed four-GET profile bundle.
 * This is a consistency check, not a promise of a transactional API snapshot.
 * Nothing here resolves domain state or recalculates actual-work totals.
 */
export function projectDogSummary(bundle: DogProfileBundle): DogSummaryProjection | null {
  const { profile, pedigree, work, history } = bundle;
  const reference = profile.state.reference_date;
  const placement = history.workspace_housing;
  if (!profile.id || [pedigree.dog_id, work.dog_id, history.dog_id].some((id) => id !== profile.id) ||
    !calendarDate(reference) || history.reference_date !== reference ||
    !calendarDate(profile.birth_date) || !calendarDate(work.season_start) || !calendarDate(work.season_end) ||
    work.season_start > work.season_end ||
    (placement && (placement.effective_date !== reference ||
      profile.state.housing?.code !== placement.location.code))) return null;

  const currentHousing = profile.state.lifecycle === 'active' && profile.state.housing !== null;
  const selectedHousing = currentHousing ? profile.state.housing : profile.last_known_housing;
  const kinds = ['Availability', 'Class', 'Lifecycle', 'Housing'] as const;
  const events = [
    ...history.availability.map((item) => ({ date: item.valid_from, kind: kinds[0], value: label(item.value) })),
    ...history.classes.map((item) => ({ date: item.valid_from, kind: kinds[1], value: label(item.value) })),
    ...history.lifecycle.map((item) => ({ date: item.valid_from, kind: kinds[2], value: label(item.value) })),
    ...history.housing.map((item) => ({ date: item.valid_from, kind: kinds[3], value: item.location.code })),
  ].filter((item) => calendarDate(item.date) && item.date <= reference)
    // Same-date events use the documented kind order, then the full value.
    .sort((a, b) => b.date.localeCompare(a.date, 'en') ||
      kinds.indexOf(a.kind) - kinds.indexOf(b.kind) || a.value.localeCompare(b.value, 'en'))
    .slice(0, DOG_SUMMARY_HISTORY_LIMIT)
    .map((item) => Object.freeze(item));
  const archive = profile.state.lifecycle === 'archived' && profile.archive ? Object.freeze({
    date: profile.archive.archive_date,
    reason: ({ euthanized: 'Euthanized', deceased: 'Died naturally', rehomed_to_guide: 'Rehomed to guide' })[profile.archive.reason],
  }) : null;

  return Object.freeze({
    name: profile.name,
    snapshotDate: reference,
    photoKey: profile.photo_key,
    birthDate: profile.birth_date,
    ageLabel: profile.age_label,
    sex: label(profile.sex),
    neuterLabel: profile.is_neutered ? 'Neutered / spayed' : 'Intact',
    neuteredOn: profile.neutered_on,
    litterCode: profile.litter_code,
    litterBirthDate: profile.litter_birth_date,
    lifecycle: label(profile.state.lifecycle),
    operationalClass: profile.state.dog_class ? label(profile.state.dog_class) : null,
    classIsHistorical: profile.state.class_is_historical,
    availability: profile.state.availability ? label(profile.state.availability) : null,
    capabilities: Object.freeze(profile.capabilities.map(workingRoleLabel)),
    housing: housing(selectedHousing, currentHousing),
    archive,
    pedigree: Object.freeze({
      mother: pedigree.mother?.name ?? null,
      father: pedigree.father?.name ?? null,
      maternalGrandmother: pedigree.maternal_grandparents.mother?.name ?? null,
      maternalGrandfather: pedigree.maternal_grandparents.father?.name ?? null,
      paternalGrandmother: pedigree.paternal_grandparents.mother?.name ?? null,
      paternalGrandfather: pedigree.paternal_grandparents.father?.name ?? null,
      littermates: pedigree.litter?.siblings.length ?? 0,
      offspring: pedigree.offspring.reduce((total, litter) => total + litter.children.length, 0),
    }),
    work: Object.freeze({
      seasonStart: work.season_start,
      seasonEnd: work.season_end,
      totalKm: work.summary.total_km,
      starts: work.summary.starts,
      starts5km: work.summary.starts_5km,
      starts10km: work.summary.starts_10km,
      averageKmPerStart: work.summary.average_km_per_start,
      lastWorkDate: work.summary.last_work_date,
    }),
    history: Object.freeze(events),
    workspaceHousing: placement ? Object.freeze({
      date: placement.effective_date,
      code: placement.location.code,
      displayName: placement.location.display_name,
    }) : null,
    notes: notesExcerpt(profile.notes),
  });
}
