import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { HousingMoveBatch, KennelMapSnapshot } from './kennel-map.models';
import { KennelMapService } from './kennel-map.service';

describe('KennelMapService housing batch', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
  });

  afterEach(() => TestBed.inject(HttpTestingController).verify());

  it('posts only the accepted server context and returns the complete committed response', () => {
    const payload: HousingMoveBatch = {
      effective_date: '2026-03-31',
      precondition: 'test-only-server-precondition',
      moves: [{ dog_id: '00000000-0000-4000-8000-000000000001', destination_code: 'PUPPY-A' }],
    };
    let received: KennelMapSnapshot | undefined;
    TestBed.inject(KennelMapService).moveDogs(payload).subscribe((response) => received = response);
    const request = TestBed.inject(HttpTestingController).expectOne('/api/v1/kennel-map/moves');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual(payload);
    expect(Object.keys(request.request.body).sort()).toEqual(['effective_date', 'moves', 'precondition']);
    expect(request.request.params.keys()).toEqual([]);
    const response: KennelMapSnapshot = {
      selected_date: '2026-03-31',
      season_start: '2025-12-01',
      season_end: '2026-03-31',
      reference_date: '2026-03-31',
      summary: {
        resident_dogs: 1, occupied_locations: 1, unavailable_dogs: 0,
        class_counts: { standard: 1 }, sex_counts: { female: 1 },
        neutered_counts: { intact: 1 }, availability_counts: { available: 1 },
      },
      locations: [{
        id: 'fixture-puppy-area', code: 'PUPPY-A', display_name: 'Puppy A',
        location_type: 'puppy_area', zone: 'PUPPY', row: 'A', position: 1,
        capacity: 5, is_active: true,
        residents: [{
          id: payload.moves[0].dog_id, name: 'Server resident', sex: 'female',
          is_neutered: false, dog_class: 'standard', lifecycle: 'active',
          availability: 'available', housing_code: 'PUPPY-A', litter_code: null,
          photo_key: null,
        }],
      }],
      housing_edit: {
        editable: true, effective_date: '2026-03-31', revision: 8,
        precondition: 'next-test-precondition', reason: null,
      },
    };
    request.flush(response);
    expect(received).toEqual(response);
  });

  it('propagates an unknown-result failure without retrying the mutation', () => {
    let failed = false;
    TestBed.inject(KennelMapService).moveDogs({
      effective_date: '2026-03-31',
      precondition: 'test-only-precondition',
      moves: [{ dog_id: '00000000-0000-4000-8000-000000000001', destination_code: 'A1-02' }],
    }).subscribe({ error: () => failed = true });
    const http = TestBed.inject(HttpTestingController);
    http.expectOne('/api/v1/kennel-map/moves').error(new ProgressEvent('error'));
    expect(failed).toBe(true);
    http.expectNone('/api/v1/kennel-map/moves');
    http.expectNone('/api/v1/demo/session');
  });
});
