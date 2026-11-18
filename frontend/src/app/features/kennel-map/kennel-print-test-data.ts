import { KennelMapLocation, KennelMapSnapshot } from '../../core/api/kennel-map.models';

/** Synthetic frontend test data only; never imported by the application. */
export function printSnapshot(): KennelMapSnapshot {
  const locations: KennelMapLocation[] = [];
  for (const zone of ['A', 'B']) {
    for (const row of ['1', '2']) {
      for (let position = 1; position <= 5; position++) {
        const code = `${zone}${row}-${String(position).padStart(2, '0')}`;
        locations.push({ id: code, code, display_name: `${zone}${row} enclosure ${position}`,
          location_type: 'adult_enclosure', zone, row, position, capacity: 2, is_active: true, residents: [] });
      }
    }
  }
  for (const [index, row] of ['A', 'B'].entries()) {
    const code = `PUPPY-${row}`;
    locations.push({ id: code, code, display_name: `Puppy building ${row}`,
      location_type: 'puppy_area', zone: 'PUPPY', row, position: index + 1,
      capacity: 5, is_active: true, residents: [] });
  }
  let number = 0;
  for (const location of locations) {
    for (let index = 0; index < location.capacity; index++) {
      number++;
      location.residents.push({
        id: `00000000-0000-4000-8000-${String(number).padStart(12, '0')}`,
        name: `Synthetic Dog ${number}`, sex: number % 2 ? 'female' : 'male',
        is_neutered: number % 3 === 0, dog_class: location.location_type === 'puppy_area' ? 'puppy' : 'standard',
        lifecycle: 'active', availability: 'available', housing_code: location.code, litter_code: null, photo_key: null,
      });
    }
  }
  return {
    selected_date: '2026-03-31', reference_date: '2026-03-31', season_start: '2025-12-01', season_end: '2026-03-31',
    locations,
    summary: { resident_dogs: 50, occupied_locations: 22, unavailable_dogs: 0,
      class_counts: { standard: 40, puppy: 10 }, sex_counts: { female: 25, male: 25 },
      neutered_counts: {}, availability_counts: { available: 50 } },
    housing_edit: { editable: true, effective_date: '2026-03-31', revision: 8, precondition: 'test-only-edit-context-must-not-print', reason: null },
  };
}
