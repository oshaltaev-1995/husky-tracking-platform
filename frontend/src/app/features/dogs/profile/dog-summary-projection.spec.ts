import { DogProfileBundle, RelatedDog } from '../../../core/api/dogs.models';
import { DOG_SUMMARY_NOTES_LIMIT, projectDogSummary } from './dog-summary-projection';

function bundle(): DogProfileBundle {
  const location = { code: 'A1-01', display_name: 'A1 enclosure 1', location_type: 'adult_enclosure' as const, zone: 'A', row: '1' };
  const relation = (name: string): RelatedDog => ({ id: name, name, birth_date: '2016-02-01', lifecycle: 'active', dog_class: 'standard' });
  return {
    profile: {
      id: 'summary-dog', name: 'Synthetic Working Dog', birth_date: '2020-05-12',
      age_years: 5, age_months: 10, age_label: '5 years, 10 months', sex: 'female',
      is_neutered: true, neutered_on: '2023-01-02', photo_key: '9422673b-331b-5e72-a700-5fff0574a209.webp',
      notes: 'A calm, fictional working dog.', litter_code: 'C', litter_birth_date: '2020-05-12',
      capabilities: ['lead', 'team', 'wheel'],
      state: { reference_date: '2026-03-31', lifecycle: 'active', dog_class: 'standard', class_is_historical: false, availability: 'available', housing: location },
      archive: null, last_known_housing: location,
    },
    pedigree: {
      dog_id: 'summary-dog', mother: relation('Synthetic Mother'), father: relation('Synthetic Father'),
      maternal_grandparents: { mother: relation('Maternal Grandmother'), father: relation('Maternal Grandfather') },
      paternal_grandparents: { mother: relation('Paternal Grandmother'), father: relation('Paternal Grandfather') },
      litter: { code: 'C', birth_date: '2020-05-12', siblings: [relation('Sibling')] },
      offspring: [{ code: 'T', birth_date: '2026-02-01', children: [relation('Child One'), relation('Child Two')] }],
    },
    work: {
      dog_id: 'summary-dog', season_start: '2025-12-01', season_end: '2026-03-31',
      summary: { total_km: 35, starts: 4, starts_5km: 1, starts_10km: 3, average_km_per_start: 8.75, last_work_date: '2026-03-30' },
      weekly: [], entries: [],
    },
    history: {
      dog_id: 'summary-dog', reference_date: '2026-03-31', archive: null,
      availability: [{ value: 'available', valid_from: '2026-03-01', valid_to: null, is_current: true, note: 'A private detail omitted from the summary.' }],
      classes: [{ value: 'standard', valid_from: '2026-02-01', valid_to: null, is_current: true, note: null }],
      lifecycle: [{ value: 'active', valid_from: '2020-05-12', valid_to: null, is_current: true, note: null }],
      housing: [{ location, valid_from: '2025-12-01', valid_to: null, is_current: true, note: null }],
    },
  };
}

describe('Dog Summary projection', () => {
  it('keeps backend identity, effective state, six pedigree names and per-dog actual totals', () => {
    const source = bundle();
    // The existing work summary is authoritative, even without exporting its full ledger.
    source.work.entries = [{ date: '2026-03-30', distance_km: 5, activity_type: 'training', label: null, role: null }];
    const projected = projectDogSummary(source)!;
    expect(projected.name).toBe(source.profile.name);
    expect(projected.snapshotDate).toBe('2026-03-31');
    expect(projected.ageLabel).toBe(source.profile.age_label);
    expect(projected.birthDate).toBe('2020-05-12');
    expect(projected.neuterLabel).toBe('Neutered / spayed');
    expect(projected.neuteredOn).toBe('2023-01-02');
    expect(projected.lifecycle).toBe('Active');
    expect(projected.operationalClass).toBe('Standard');
    expect(projected.availability).toBe('Available');
    expect(projected.capabilities).toEqual(['Lead', 'Team', 'Wheel']);
    expect(projected.housing).toEqual({ label: 'Current housing', code: 'A1-01', displayName: 'A1 enclosure 1' });
    expect(projected.pedigree).toEqual({
      mother: 'Synthetic Mother', father: 'Synthetic Father', maternalGrandmother: 'Maternal Grandmother',
      maternalGrandfather: 'Maternal Grandfather', paternalGrandmother: 'Paternal Grandmother',
      paternalGrandfather: 'Paternal Grandfather', littermates: 1, offspring: 2,
    });
    expect(projected.work).toEqual({
      seasonStart: '2025-12-01', seasonEnd: '2026-03-31', totalKm: 35, starts: 4,
      starts5km: 1, starts10km: 3, averageKmPerStart: 8.75, lastWorkDate: '2026-03-30',
    });
  });

  it('does not conflate retired availability with archive or current housing with last known housing', () => {
    const source = bundle();
    source.profile.state.availability = 'retired';
    const retired = projectDogSummary(source)!;
    expect(retired.lifecycle).toBe('Active');
    expect(retired.availability).toBe('Retired');
    expect(retired.archive).toBeNull();
    expect(retired.housing?.label).toBe('Current housing');

    source.profile.state.lifecycle = 'archived';
    source.profile.state.class_is_historical = true;
    source.profile.state.availability = null;
    source.profile.archive = { archive_date: '2026-03-20', reason: 'rehomed_to_guide', note: 'Excluded archive prose' };
    const archived = projectDogSummary(source)!;
    expect(archived.classIsHistorical).toBe(true);
    expect(archived.availability).toBeNull();
    expect(archived.archive).toEqual({ date: '2026-03-20', reason: 'Rehomed to guide' });
    expect(archived.housing?.label).toBe('Last known housing');

    source.profile.last_known_housing = null;
    expect(projectDogSummary(source)!.housing).toBeNull();
  });

  it('preserves zero work and absent averages, relations, photo and notes without inventing facts', () => {
    const source = bundle();
    source.profile.state.dog_class = 'puppy';
    source.profile.state.housing = null;
    source.profile.last_known_housing = null;
    source.profile.capabilities = [];
    source.profile.photo_key = null;
    source.profile.notes = null;
    source.profile.is_neutered = false;
    source.profile.neutered_on = null;
    source.profile.litter_code = null;
    source.profile.litter_birth_date = null;
    source.pedigree = {
      dog_id: source.profile.id, mother: null, father: null,
      maternal_grandparents: { mother: null, father: null }, paternal_grandparents: { mother: null, father: null },
      litter: null, offspring: [],
    };
    source.work.summary = { total_km: 0, starts: 0, starts_5km: 0, starts_10km: 0, average_km_per_start: null, last_work_date: null };
    const projected = projectDogSummary(source)!;
    expect(projected.neuterLabel).toBe('Intact');
    expect(projected.work).toEqual({
      seasonStart: '2025-12-01', seasonEnd: '2026-03-31', totalKm: 0, starts: 0,
      starts5km: 0, starts10km: 0, averageKmPerStart: null, lastWorkDate: null,
    });
    expect(projected.capabilities).toEqual([]);
    expect(projected.housing).toBeNull();
    expect(projected.notes).toBeNull();
    expect(projected.photoKey).toBeNull();
    expect(projected.litterCode).toBeNull();
    expect(projected.pedigree.mother).toBeNull();
    expect(projected.pedigree.paternalGrandfather).toBeNull();
  });

  it('keeps the latest three canonical events through the reference date in stable same-date order', () => {
    const source = bundle();
    source.history.classes[0].valid_from = '2026-03-01';
    source.history.lifecycle[0].valid_from = '2026-03-01';
    source.history.housing[0].valid_from = '2026-03-01';
    source.history.availability.push({ value: 'injured', valid_from: '2026-04-01', valid_to: null, is_current: false, note: null });
    expect(projectDogSummary(source)!.history).toEqual([
      { date: '2026-03-01', kind: 'Availability', value: 'Available' },
      { date: '2026-03-01', kind: 'Class', value: 'Standard' },
      { date: '2026-03-01', kind: 'Lifecycle', value: 'Active' },
    ]);
    source.history.housing[0].valid_from = '2026-03-31';
    expect(projectDogSummary(source)!.history[0]).toEqual({ date: '2026-03-31', kind: 'Housing', value: 'A1-01' });
  });

  it('keeps temporary workspace housing separate from canonical history and uses resolved profile housing', () => {
    const source = bundle();
    const original = source.history.housing[0].location;
    const moved = { ...original, code: 'B2-05', display_name: 'B2 enclosure 5', zone: 'B', row: '2' };
    source.profile.state.housing = moved;
    source.history.workspace_housing = { effective_date: '2026-03-31', location: moved };
    const projected = projectDogSummary(source)!;
    expect(projected.housing?.code).toBe('B2-05');
    expect(projected.workspaceHousing).toEqual({ date: '2026-03-31', code: 'B2-05', displayName: 'B2 enclosure 5' });
    expect(projected.history.find((event) => event.kind === 'Housing')?.value).toBe('A1-01');
    expect(projected.history.some((event) => event.value === 'B2-05')).toBe(false);
  });

  it('rejects mixed-dog, inconsistent-reference and mixed-placement responses instead of printing stale context', () => {
    for (const part of ['pedigree', 'work', 'history'] as const) {
      const source = bundle();
      source[part].dog_id = 'different-dog';
      expect(projectDogSummary(source)).toBeNull();
    }
    const source = bundle();
    source.history.reference_date = '2026-03-30';
    expect(projectDogSummary(source)).toBeNull();
    source.history.reference_date = '2026-03-31';
    source.profile.state.reference_date = '2026-02-30';
    expect(projectDogSummary(source)).toBeNull();
    source.profile.state.reference_date = '2026-03-31';
    source.history.workspace_housing = { effective_date: '2026-03-30', location: source.profile.state.housing! };
    expect(projectDogSummary(source)).toBeNull();
    source.history.workspace_housing.effective_date = '2026-03-31';
    source.history.workspace_housing.location = { ...source.profile.state.housing!, code: 'B1-01' };
    expect(projectDogSummary(source)).toBeNull();
  });

  it('bounds only the notes excerpt at a word boundary, marks shortening, and retains full core names', () => {
    const source = bundle();
    source.profile.notes = 'A quiet synthetic dog with a reliable response to the familiar kennel routine. '.repeat(8);
    source.profile.name = 'A Long Synthetic Dog Name That Must Remain Complete';
    source.pedigree.mother!.name = 'A Long Maternal Name That Also Must Remain Complete';
    const projected = projectDogSummary(source)!;
    expect(projected.notes?.text.length).toBeLessThanOrEqual(DOG_SUMMARY_NOTES_LIMIT);
    expect(projected.notes?.shortened).toBe(true);
    expect(projected.notes?.text.endsWith('…')).toBe(true);
    expect(source.profile.notes.startsWith(projected.notes!.text.slice(0, -1))).toBe(true);
    expect(source.profile.notes[projected.notes!.text.length - 1]).toMatch(/\s/);
    expect(projected.name).toBe(source.profile.name);
    expect(projected.pedigree.mother).toBe(source.pedigree.mother!.name);
    source.profile.notes = '  Short plain text <b>not trusted HTML</b>.  ';
    expect(projectDogSummary(source)!.notes).toEqual({ text: 'Short plain text <b>not trusted HTML</b>.', shortened: false });
  });

  it('detaches and deeply freezes display facts without retaining ledger entries, IDs or history notes', () => {
    const source = bundle();
    const original = structuredClone(source);
    const projected = projectDogSummary(source)!;
    expect(source).toEqual(original);
    for (const value of [projected, projected.capabilities, projected.housing, projected.pedigree, projected.work,
      projected.history, ...projected.history, projected.notes]) expect(Object.isFrozen(value)).toBe(true);
    expect(() => Object.defineProperty(projected.work, 'totalKm', { value: 999 })).toThrow();
    source.profile.name = 'Changed source';
    source.profile.state.housing!.code = 'B1-02';
    source.pedigree.mother!.name = 'Changed mother';
    source.work.summary.total_km = 999;
    source.history.availability[0].value = 'injured';
    expect(projected.name).toBe(original.profile.name);
    expect(projected.housing?.code).toBe('A1-01');
    expect(projected.pedigree.mother).toBe('Synthetic Mother');
    expect(projected.work.totalKm).toBe(35);
    expect(projected.history[0].value).toBe('Available');
    const serialized = JSON.stringify(projected);
    expect(serialized).not.toContain('summary-dog');
    expect(serialized).not.toContain('private detail');
    expect(serialized).not.toContain('entries');
    expect(serialized).not.toContain('valid_to');
  });

  it('does not depend on the machine date or profile tab state', () => {
    const source = bundle();
    const before = projectDogSummary(source);
    const originalNow = Date.now;
    Date.now = () => new Date('2040-09-12T10:00:00Z').getTime();
    try {
      expect(projectDogSummary(source)).toEqual(before);
      expect(projectDogSummary(source)!.ageLabel).toBe('5 years, 10 months');
    } finally {
      Date.now = originalNow;
    }
  });
});
