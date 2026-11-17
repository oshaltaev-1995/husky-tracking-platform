import {
  KennelMapLocation,
  KennelMapResident,
  KennelMapSnapshot,
} from '../../core/api/kennel-map.models';
import {
  affectedHousing,
  HousingMoveDraft,
  pendingMoves,
  previewHousing,
  stageMove,
} from './housing-move-draft';

function resident(name: string, housing: string, availability: KennelMapResident['availability'] = 'available'): KennelMapResident {
  return {
    id: `${name.toLowerCase().replaceAll(' ', '-')}-uuid`, name,
    sex: 'female', is_neutered: false, dog_class: housing.startsWith('PUPPY') ? 'puppy' : 'standard',
    lifecycle: 'active', availability, housing_code: housing, litter_code: null, photo_key: null,
  };
}

function enclosure(code: string, residents: KennelMapResident[] = []): KennelMapLocation {
  const puppy = code.startsWith('PUPPY');
  return {
    id: code, code, display_name: code, location_type: puppy ? 'puppy_area' : 'adult_enclosure',
    zone: puppy ? 'PUPPY' : code[0], row: puppy ? 'A' : code[1], position: 1,
    capacity: puppy ? 5 : 2, is_active: true, residents,
  };
}

function snapshot(): KennelMapSnapshot {
  return {
    selected_date: '2026-03-31', season_start: '2025-12-01', season_end: '2026-03-31', reference_date: '2026-03-31',
    housing_edit: { editable: true, effective_date: '2026-03-31', revision: 0, precondition: 'test-only-precondition', reason: null },
    summary: { resident_dogs: 9, occupied_locations: 3, unavailable_dogs: 4, class_counts: { standard: 4, puppy: 5 }, sex_counts: { female: 9 }, neutered_counts: { intact: 9, neutered: 0 }, availability_counts: { available: 5, injured: 1, rest: 1, restricted: 1, retired: 1 } },
    locations: [
      enclosure('A1-01', [resident('Atlas', 'A1-01', 'rest'), resident('Aurora', 'A1-01', 'injured')]),
      enclosure('A1-02', [resident('Cedar', 'A1-02', 'restricted'), resident('Orion', 'A1-02', 'retired')]),
      enclosure('B2-05'),
      enclosure('PUPPY-A', ['Taro', 'Tessa', 'Theo', 'Tindra', 'Toast'].map((name) => resident(name, 'PUPPY-A'))),
      { ...enclosure('PUPPY-B'), is_active: false },
    ],
  };
}

function freeze<T>(value: T): T {
  if (value && typeof value === 'object') {
    Object.values(value).forEach(freeze);
    Object.freeze(value);
  }
  return value;
}

function ids(value: KennelMapSnapshot): string[] {
  return value.locations.flatMap((location) => location.residents.map((dog) => dog.id)).sort();
}

describe('housing move draft', () => {
  it('normalizes A→B→C to one final move and removes a return to committed housing', () => {
    const committed = snapshot();
    const original = new Map<string, string>();
    const b = stageMove(committed, original, 'atlas-uuid', 'A1-02');
    const c = stageMove(committed, b, 'atlas-uuid', 'PUPPY-A');
    expect(pendingMoves(committed, c)).toEqual([{ dog_id: 'atlas-uuid', dog_name: 'Atlas', source_code: 'A1-01', destination_code: 'PUPPY-A' }]);
    const returned = stageMove(committed, c, 'atlas-uuid', 'A1-01');
    expect(returned.size).toBe(0);
    expect(previewHousing(committed, returned)).toBe(committed);
    expect(original.size).toBe(0);
    expect(b.get('atlas-uuid')).toBe('A1-02');
    expect(c.get('atlas-uuid')).toBe('PUPPY-A');
  });

  it('retains the same draft for committed and preview-target no-ops', () => {
    const committed = snapshot();
    const empty = new Map<string, string>();
    expect(stageMove(committed, empty, 'atlas-uuid', 'A1-01')).toBe(empty);
    const draft = stageMove(committed, empty, 'atlas-uuid', 'A1-02');
    expect(stageMove(committed, draft, 'atlas-uuid', 'A1-02')).toBe(draft);
    expect(pendingMoves(committed, draft).length).toBe(1);
  });

  it('preserves prior draft values so Undo restores the previous intention for a repeated dog', () => {
    const committed = snapshot();
    let current: HousingMoveDraft = new Map();
    const history: HousingMoveDraft[] = [];
    for (const destination of ['A1-02', 'PUPPY-A', 'A1-01']) {
      history.push(current);
      current = stageMove(committed, current, 'atlas-uuid', destination);
    }
    expect(current.size).toBe(0);
    expect(pendingMoves(committed, history.pop()!)[0].destination_code).toBe('PUPPY-A');
    expect(pendingMoves(committed, history.pop()!)[0].destination_code).toBe('A1-02');
    expect(history.pop()!.size).toBe(0);
  });

  it('allows four adult residents and preserves prior occupants, names, IDs and other state', () => {
    const committed = freeze(snapshot());
    const before = JSON.stringify(committed);
    let draft: HousingMoveDraft = new Map();
    for (const id of ['atlas-uuid', 'aurora-uuid']) draft = stageMove(committed, draft, id, 'A1-02');
    const preview = previewHousing(committed, draft);
    expect(preview.locations[1].residents.map((dog) => dog.name)).toEqual(['Atlas', 'Aurora', 'Cedar', 'Orion']);
    expect(preview.locations[1].capacity).toBe(2);
    expect(preview.locations[0].residents).toEqual([]);
    expect(preview.summary.occupied_locations).toBe(2);
    expect(preview.summary.resident_dogs).toBe(9);
    expect(ids(preview)).toEqual(ids(committed));
    expect(new Set(ids(preview)).size).toBe(9);
    expect(JSON.stringify(committed)).toBe(before);
    expect(preview.housing_edit).toBe(committed.housing_edit);
    expect(preview.locations[1].residents.every((dog) => dog.housing_code === 'A1-02')).toBe(true);
    expect(preview.locations.map((location) => location.code)).toEqual(committed.locations.map((location) => location.code));
  });

  it('accepts unavailable adults into a puppy building with eight residents and retains all puppy names', () => {
    const committed = snapshot();
    let draft: HousingMoveDraft = new Map();
    for (const id of ['atlas-uuid', 'aurora-uuid', 'cedar-uuid']) draft = stageMove(committed, draft, id, 'PUPPY-A');
    const puppy = previewHousing(committed, draft).locations.find((location) => location.code === 'PUPPY-A')!;
    expect(puppy.residents.length).toBe(8);
    expect(puppy.capacity).toBe(5);
    expect(puppy.residents.map((dog) => dog.name)).toEqual(['Atlas', 'Aurora', 'Cedar', 'Taro', 'Tessa', 'Theo', 'Tindra', 'Toast']);
    expect(puppy.residents.find((dog) => dog.id === 'aurora-uuid')?.availability).toBe('injured');
    expect(pendingMoves(committed, draft).length).toBe(3);
  });

  it('supports empty destinations and puppies in adult enclosures without a type rule', () => {
    const committed = snapshot();
    const draft = stageMove(committed, new Map(), 'taro-uuid', 'B2-05');
    const preview = previewHousing(committed, draft);
    expect(preview.locations[2].residents.map((dog) => dog.id)).toEqual(['taro-uuid']);
    expect(preview.summary.occupied_locations).toBe(4);
    expect(preview.locations[3].residents.some((dog) => dog.id === 'taro-uuid')).toBe(false);
  });

  it('reports all affected sources and destinations in topology order, including an emptied source', () => {
    const committed = snapshot();
    let draft: HousingMoveDraft = new Map();
    for (const id of ['orion-uuid', 'cedar-uuid']) draft = stageMove(committed, draft, id, 'A1-01');
    const changes = pendingMoves(committed, draft);
    expect(changes.map((move) => move.dog_name)).toEqual(['Cedar', 'Orion']);
    const affected = affectedHousing(previewHousing(committed, draft), changes);
    expect(affected.map((location) => location.code)).toEqual(['A1-01', 'A1-02']);
    expect(affected[0].residents.length).toBe(4);
    expect(affected[1].residents).toEqual([]);
    expect(affectedHousing(committed, [])).toEqual([]);
  });

  it('does not stage unknown dogs or unknown/inactive destinations or project invalid draft entries', () => {
    const committed = snapshot();
    const empty = new Map<string, string>();
    expect(stageMove(committed, empty, 'missing-uuid', 'A1-02')).toBe(empty);
    expect(stageMove(committed, empty, 'atlas-uuid', 'not-a-location')).toBe(empty);
    expect(stageMove(committed, empty, 'atlas-uuid', 'PUPPY-B')).toBe(empty);
    const invalid = new Map([['missing-uuid', 'A1-02'], ['atlas-uuid', 'PUPPY-B'], ['taro-uuid', 'PUPPY-A']]);
    expect(pendingMoves(committed, invalid)).toEqual([]);
    expect(previewHousing(committed, invalid)).toBe(committed);
  });

  it('keeps long names intact when concentrating the whole population in one enclosure', () => {
    const committed = snapshot();
    committed.locations[0].residents[0].name = 'Atlas with an intentionally long synthetic display name';
    let draft: HousingMoveDraft = new Map();
    for (const id of ids(committed)) draft = stageMove(committed, draft, id, 'B2-05');
    const preview = previewHousing(committed, draft);
    expect(preview.locations[2].residents.length).toBe(9);
    expect(preview.locations[2].residents.some((dog) => dog.name === committed.locations[0].residents[0].name)).toBe(true);
    expect(preview.summary.occupied_locations).toBe(1);
    expect(ids(preview)).toEqual(ids(committed));
    expect(preview.locations.filter((location) => location.code !== 'B2-05').every((location) => location.residents.length === 0)).toBe(true);
  });
});
