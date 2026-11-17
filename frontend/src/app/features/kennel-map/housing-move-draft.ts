import {
  KennelMapLocation,
  KennelMapResident,
  KennelMapSnapshot,
} from '../../core/api/kennel-map.models';

/** Final destinations only; committed housing and the action history stay separate. */
export type HousingMoveDraft = ReadonlyMap<string, string>;

export interface PendingHousingMove {
  dog_id: string;
  dog_name: string;
  source_code: string;
  destination_code: string;
}

interface CommittedResident {
  dog: KennelMapResident;
  source: KennelMapLocation;
}

function committedResidents(snapshot: KennelMapSnapshot): Map<string, CommittedResident> {
  const residents = new Map<string, CommittedResident>();
  for (const source of snapshot.locations) {
    for (const dog of source.residents) residents.set(dog.id, { dog, source });
  }
  return residents;
}

/** Return the same draft for a no-op, so callers record only real Undo actions. */
export function stageMove(
  committed: KennelMapSnapshot,
  draft: HousingMoveDraft,
  dogId: string,
  destination: string,
): HousingMoveDraft {
  const resident = committedResidents(committed).get(dogId);
  const target = committed.locations.find((location) => location.code === destination && location.is_active);
  if (!resident || !target) return draft;
  const current = draft.get(dogId) ?? resident.source.code;
  if (current === destination) return draft;
  const next = new Map(draft);
  if (resident.source.code === destination) next.delete(dogId);
  else next.set(dogId, destination);
  return next;
}

/** Use committed sources and snapshot order, independently of action order. */
export function pendingMoves(
  committed: KennelMapSnapshot,
  draft: HousingMoveDraft,
): PendingHousingMove[] {
  const destinations = new Set(committed.locations.filter((location) => location.is_active).map((location) => location.code));
  const result: PendingHousingMove[] = [];
  for (const [dogId, { dog, source }] of committedResidents(committed)) {
    const destination = draft.get(dogId);
    if (!destination || !destinations.has(destination) || destination === source.code) continue;
    result.push({ dog_id: dogId, dog_name: dog.name, source_code: source.code, destination_code: destination });
  }
  return result;
}

/** Preview is presentation only; the token and all non-housing state remain committed. */
export function previewHousing(
  committed: KennelMapSnapshot,
  draft: HousingMoveDraft,
): KennelMapSnapshot {
  const changes = pendingMoves(committed, draft);
  if (!changes.length) return committed;
  const destinations = new Map(changes.map((move) => [move.dog_id, move.destination_code]));
  const locations = committed.locations.map((location) => ({ ...location, residents: [] as KennelMapResident[] }));
  const byCode = new Map(locations.map((location) => [location.code, location]));
  for (const source of committed.locations) {
    for (const dog of source.residents) {
      const destination = destinations.get(dog.id) ?? source.code;
      byCode.get(destination)?.residents.push({ ...dog, housing_code: destination });
    }
  }
  for (const location of locations) {
    location.residents.sort((a, b) => a.name.localeCompare(b.name, 'en') || a.id.localeCompare(b.id, 'en'));
  }
  return {
    ...committed,
    summary: {
      ...committed.summary,
      occupied_locations: locations.filter((location) => location.residents.length).length,
    },
    locations,
  };
}

/** Include emptied sources and complete destinations in the original topology order. */
export function affectedHousing(
  preview: KennelMapSnapshot,
  changes: readonly PendingHousingMove[],
): KennelMapLocation[] {
  const codes = new Set(changes.flatMap((move) => [move.source_code, move.destination_code]));
  return preview.locations.filter((location) => codes.has(location.code));
}
