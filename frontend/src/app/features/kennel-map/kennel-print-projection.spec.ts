import { KennelMapLayer, KennelMapResident, KennelMapSnapshot } from '../../core/api/kennel-map.models';
import { projectKennelPrint } from './kennel-print-projection';
import { printSnapshot } from './kennel-print-test-data';

function allLocations(snapshot: KennelMapSnapshot, layer: KennelMapLayer = 'default') {
  const projected = projectKennelPrint(snapshot, layer);
  return [...projected.groups.flatMap((group) => group.rows.flatMap((row) => row.locations)), ...projected.puppyBuildings];
}

describe('Committed kennel print projection', () => {
  it('preserves all enclosure identities, empty locations and each resident exactly once', () => {
    const snapshot = printSnapshot();
    const original = structuredClone(snapshot);
    const projected = projectKennelPrint(snapshot, 'default');
    const locations = allLocations(snapshot);
    expect(locations.map((location) => location.code)).toEqual(snapshot.locations.map((location) => location.code));
    expect(projected.groups.map((group) => group.rows.map((row) => row.code))).toEqual([['A1', 'A2'], ['B1', 'B2']]);
    expect(projected.residentCount).toBe(50);
    expect(projected.locationCount).toBe(22);
    expect(locations.flatMap((location) => location.residents.map((dog) => dog.id)).sort()).toEqual(
      snapshot.locations.flatMap((location) => location.residents.map((dog) => dog.id)).sort(),
    );
    expect(snapshot).toEqual(original);
    snapshot.locations.forEach((location) => location.residents = []);
    const empty = projectKennelPrint(snapshot, 'default');
    expect(empty.residentCount).toBe(0);
    expect(empty.locationCount).toBe(22);
    expect(empty.groups.flatMap((group) => group.rows).every((row) => row.lines.length === 1)).toBe(true);
    expect(empty.puppyLines).toEqual([0]);
  });

  it('uses the selected committed date and housing without retaining any editing context', () => {
    const snapshot = printSnapshot();
    snapshot.selected_date = '2026-01-01';
    snapshot.housing_edit = { editable: false, effective_date: '2026-03-31', revision: null, precondition: null, reason: 'historical_date' };
    const dog = snapshot.locations[0].residents.pop()!;
    dog.housing_code = 'PUPPY-A';
    snapshot.locations[20].residents.push(dog);
    const projection = projectKennelPrint(snapshot, 'class');
    expect(projection.snapshotDate).toBe('2026-01-01');
    expect(projection.puppyBuildings[0].residents.some((resident) => resident.id === dog.id)).toBe(true);
    const serialized = JSON.stringify(projection);
    expect(serialized).not.toContain('housing_edit');
    expect(serialized).not.toContain('precondition');
    expect(serialized).not.toContain('revision');
    expect(serialized).not.toContain('photo_key');
  });

  it('freezes a detached projection that cannot drift when the live source changes', () => {
    const snapshot = printSnapshot();
    const projection = projectKennelPrint(snapshot, 'gender');
    const first = projection.groups[0].rows[0].locations[0];
    expect(Object.isFrozen(projection)).toBe(true);
    expect(Object.isFrozen(projection.groups[0].rows[0].lines)).toBe(true);
    expect(Object.isFrozen(first.residents[0])).toBe(true);
    expect(Object.isFrozen(first.residents)).toBe(true);
    expect(() => Object.defineProperty(first.residents[0], 'name', { value: 'Changed' })).toThrow();
    snapshot.locations[0].residents[0].name = 'A different live name';
    snapshot.locations[0].residents.splice(1);
    snapshot.selected_date = '2026-02-01';
    expect(first.residents.map((dog) => dog.name)).toEqual(['Synthetic Dog 1', 'Synthetic Dog 2']);
    expect(projection.snapshotDate).toBe('2026-03-31');
    expect(projection.residentCount).toBe(50);
  });

  it('retains over-capacity adult/puppy rosters and full long names with no hidden overflow group', () => {
    const snapshot = printSnapshot();
    const allDogs = snapshot.locations.flatMap((location) => location.residents);
    snapshot.locations.forEach((location) => location.residents = []);
    snapshot.locations[0].residents = allDogs.slice(0, 4);
    snapshot.locations[20].residents = allDogs.slice(4, 17);
    snapshot.locations[21].residents = allDogs.slice(17);
    snapshot.locations[20].residents[0].name = 'A long synthetic resident name that must remain complete when printed';
    const projection = projectKennelPrint(snapshot, 'default');
    expect(projection.groups[0].rows[0].locations[0].occupancy).toBe(4);
    expect(projection.groups[0].rows[0].locations[0].nominalCapacity).toBe(2);
    expect(projection.puppyBuildings[0].occupancy).toBe(13);
    expect(projection.puppyBuildings[0].nominalCapacity).toBe(5);
    expect(projection.puppyBuildings[0].residents[0].name).toBe(snapshot.locations[20].residents[0].name);
    expect(projection.residentCount).toBe(50);
    expect(projection.groups[0].rows[0].lines.length).toBe(4);
    expect(projection.puppyLines.length).toBe(33);
  });

  it('has no fixed resident or page limit for an extreme concentrated roster', () => {
    const snapshot = printSnapshot();
    const allDogs = snapshot.locations.flatMap((location) => location.residents);
    snapshot.locations.forEach((location) => location.residents = []);
    snapshot.locations[0].residents = allDogs;
    const projection = projectKennelPrint(snapshot, 'default');
    expect(projection.groups[0].rows[0].lines.length).toBe(50);
    expect(allLocations(snapshot).flatMap((location) => location.residents).length).toBe(50);
    expect(allLocations(snapshot).filter((location) => !location.residents.length).length).toBe(21);
  });

  const layerCases: { layer: KennelMapLayer; marker: string; label: string; legend: string[] }[] = [
    { layer: 'default', marker: '', label: 'Standard · Female', legend: ['Class and sex · unavailable status marked'] },
    { layer: 'gender', marker: 'F', label: 'Female', legend: ['Female', 'Male'] },
    { layer: 'neutered', marker: 'N', label: 'Spayed', legend: ['Intact', 'Neutered / spayed'] },
    { layer: 'class', marker: 'S', label: 'Standard', legend: ['Puppy', 'Junior', 'Training', 'Standard'] },
    { layer: 'unavailable', marker: 'A', label: 'Available', legend: ['Available', 'Injured', 'Rest', 'Restricted', 'Retired'] },
  ];
  for (const example of layerCases) {
    it(`keeps the established ${example.layer} layer text and legend`, () => {
      const snapshot = printSnapshot();
      snapshot.locations[0].residents[0].is_neutered = true;
      const projection = projectKennelPrint(snapshot, example.layer);
      const dog = projection.groups[0].rows[0].locations[0].residents[0];
      expect(dog.marker).toBe(example.marker);
      expect(dog.label).toBe(example.label);
      expect(projection.legend.map((item) => item.label)).toEqual(example.legend);
    });
  }

  it('keeps every unavailable status distinct in text, including without printed color', () => {
    const snapshot = printSnapshot();
    const first = snapshot.locations[0].residents[0];
    const statuses: [KennelMapResident['availability'], string, string][] = [
      ['injured', 'I', 'Injured'], ['rest', 'R', 'Rest'], ['restricted', 'X', 'Restricted'], ['retired', 'T', 'Retired'], [null, '?', 'Status not recorded'],
    ];
    for (const [status, marker, label] of statuses) {
      first.availability = status;
      const dog = allLocations(snapshot, 'unavailable')[0].residents[0];
      expect(dog.marker).toBe(marker);
      expect(dog.label).toBe(label);
      expect(allLocations(snapshot, 'default')[0].residents[0].label).toBe(label);
    }
  });
});
