import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';

import {
  KennelMapLocation,
  KennelMapResident,
  KennelMapSnapshot,
} from '../../core/api/kennel-map.models';
import { KennelMapPageComponent } from './kennel-map-page.component';

const maple: KennelMapResident = {
  id: 'maple-id',
  name: 'Maple',
  sex: 'female',
  is_neutered: false,
  dog_class: 'standard',
  lifecycle: 'active',
  availability: 'injured',
  housing_code: 'A1-01',
  litter_code: 'M',
  photo_key: null,
};

const fjord: KennelMapResident = {
  id: 'fjord-id',
  name: 'Fjord',
  sex: 'male',
  is_neutered: true,
  dog_class: 'standard',
  lifecycle: 'active',
  availability: 'retired',
  housing_code: 'A1-01',
  litter_code: null,
  photo_key: null,
};

const taro: KennelMapResident = {
  id: 'taro-id',
  name: 'Taro',
  sex: 'male',
  is_neutered: false,
  dog_class: 'puppy',
  lifecycle: 'active',
  availability: 'available',
  housing_code: 'PUPPY-A',
  litter_code: 'T',
  photo_key: null,
};

function location(
  code: string,
  type: 'adult_enclosure' | 'puppy_area',
  residents: KennelMapResident[] = [],
): KennelMapLocation {
  const adult = type === 'adult_enclosure';
  return {
    id: code,
    code,
    display_name: adult ? `${code} enclosure` : `Puppy building ${code.slice(-1)}`,
    location_type: type,
    zone: adult ? code[0] : 'PUPPY',
    row: adult ? code[1] : code.slice(-1),
    position: adult ? Number(code.slice(-2)) : code.endsWith('A') ? 1 : 2,
    capacity: adult ? 2 : 5,
    is_active: true,
    residents,
  };
}

const adultLocations = [
  ...Array.from({ length: 5 }, (_, index) => `A1-${String(index + 1).padStart(2, '0')}`),
  ...Array.from({ length: 5 }, (_, index) => `A2-${String(index + 1).padStart(2, '0')}`),
  ...Array.from({ length: 5 }, (_, index) => `B1-${String(index + 1).padStart(2, '0')}`),
  ...Array.from({ length: 5 }, (_, index) => `B2-${String(index + 1).padStart(2, '0')}`),
].map((code) => location(code, 'adult_enclosure', code === 'A1-01' ? [maple, fjord] : []));

const snapshot: KennelMapSnapshot = {
  selected_date: '2026-03-31',
  season_start: '2025-12-01',
  season_end: '2026-03-31',
  reference_date: '2026-03-31',
  summary: {
    resident_dogs: 50,
    occupied_locations: 22,
    unavailable_dogs: 4,
    class_counts: { puppy: 10, junior: 6, training: 8, standard: 26 },
    sex_counts: { female: 22, male: 28 },
    neutered_counts: { intact: 28, neutered: 22 },
    availability_counts: { available: 46, injured: 1, rest: 1, restricted: 1, retired: 1 },
  },
  locations: [
    ...adultLocations,
    location('PUPPY-A', 'puppy_area', [taro]),
    location('PUPPY-B', 'puppy_area'),
  ],
};

async function setup(url = '/kennel') {
  await TestBed.configureTestingModule({
    imports: [KennelMapPageComponent],
    providers: [
      provideHttpClient(),
      provideHttpClientTesting(),
      provideRouter([{ path: 'kennel', component: KennelMapPageComponent }]),
    ],
  }).compileComponents();
  const router = TestBed.inject(Router);
  await router.navigateByUrl(url);
  const fixture = TestBed.createComponent(KennelMapPageComponent);
  fixture.detectChanges();
  return { fixture, router, http: TestBed.inject(HttpTestingController) };
}

describe('KennelMapPageComponent', () => {
  afterEach(() => TestBed.inject(HttpTestingController).verify());

  it('renders the canonical row topology, puppy areas, and profile links', async () => {
    const { fixture, http } = await setup();
    expect(fixture.nativeElement.textContent).toContain('Loading the dated kennel snapshot');
    http.expectOne('/api/v1/kennel-map?date=2026-03-31').flush(snapshot);
    await fixture.whenStable();
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent;
    expect(text).toContain('A1-01');
    expect(text).toContain('B2-05');
    expect(text).toContain('PUPPY-A');
    expect(fixture.nativeElement.querySelectorAll('ht-kennel-location-card').length).toBe(22);
    const zoneA = fixture.nativeElement.querySelector('[data-zone="A"]');
    expect(zoneA.querySelectorAll('.paired-row-block [data-row]').length).toBe(2);
    expect(zoneA.querySelector('.kennel-aisle')).not.toBeNull();
    expect(
      Array.from(
        zoneA.querySelectorAll('[data-row="A1"] [data-location-code]') as NodeListOf<HTMLElement>,
      ).map((cell) => cell.dataset['locationCode']),
    ).toEqual(['A1-01', 'A1-02', 'A1-03', 'A1-04', 'A1-05']);
    const dogLink = fixture.nativeElement.querySelector(
      'a[href="/dogs/maple-id"]',
    ) as HTMLAnchorElement;
    expect(dogLink).not.toBeNull();
  });

  it('switches layers, changes the legend, and preserves layer URL state', async () => {
    const { fixture, router, http } = await setup();
    http.expectOne('/api/v1/kennel-map?date=2026-03-31').flush(snapshot);
    await fixture.whenStable();
    fixture.detectChanges();

    const geometryBefore = Array.from(
      fixture.nativeElement.querySelectorAll('[data-location-code]') as NodeListOf<HTMLElement>,
    ).map((cell) => cell.dataset['locationCode']);

    const classButton = Array.from(
      fixture.nativeElement.querySelectorAll('.layer-control button') as NodeListOf<HTMLButtonElement>,
    ).find((button) => button.textContent.trim() === 'Class') as HTMLButtonElement;
    classButton.click();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(classButton.getAttribute('aria-pressed')).toBe('true');
    expect(fixture.nativeElement.querySelector('.map-legend').textContent).toContain('Puppy');
    expect(router.url).toContain('layer=class');
    expect(fixture.nativeElement.querySelector('[data-tone="standard"]')).not.toBeNull();
    expect(
      Array.from(
        fixture.nativeElement.querySelectorAll('[data-location-code]') as NodeListOf<HTMLElement>,
      ).map((cell) => cell.dataset['locationCode']),
    ).toEqual(geometryBefore);
  });

  it('keeps fixed resident slots visible in partial and empty historical enclosures', async () => {
    const { fixture, http } = await setup();
    const partialDog: KennelMapResident = {
      ...maple,
      id: 'cedar-id',
      name: 'Cedar',
      availability: 'available',
      housing_code: 'A1-02',
    };
    const historicalSnapshot: KennelMapSnapshot = {
      ...snapshot,
      locations: snapshot.locations.map((item) =>
        item.code === 'A1-02' ? { ...item, residents: [partialDog] } : item,
      ),
    };
    http.expectOne('/api/v1/kennel-map?date=2026-03-31').flush(historicalSnapshot);
    await fixture.whenStable();
    fixture.detectChanges();

    const partial = fixture.nativeElement.querySelector('[data-location-code="A1-02"]');
    const empty = fixture.nativeElement.querySelector('[data-location-code="A1-03"]');
    expect(partial.querySelectorAll('.resident-dog').length).toBe(1);
    expect(partial.querySelectorAll('.empty-resident-slot').length).toBe(1);
    expect(empty.querySelectorAll('.empty-resident-slot').length).toBe(2);
    expect(empty.textContent).toContain('0 / 2');
  });

  it('reloads a dated snapshot and keeps the selected date in the URL', async () => {
    const { fixture, router, http } = await setup();
    http.expectOne('/api/v1/kennel-map?date=2026-03-31').flush(snapshot);
    await fixture.whenStable();
    fixture.detectChanges();

    const dateInput = fixture.nativeElement.querySelector('input[type="date"]') as HTMLInputElement;
    dateInput.value = '2026-01-14';
    dateInput.dispatchEvent(new Event('input'));
    await new Promise((resolve) => setTimeout(resolve, 0));
    fixture.detectChanges();
    http.expectOne('/api/v1/kennel-map?date=2026-01-14').flush({
      ...snapshot,
      selected_date: '2026-01-14',
    });
    await fixture.whenStable();
    fixture.detectChanges();

    expect(router.url).toContain('date=2026-01-14');
    expect(fixture.nativeElement.textContent).toContain('January 14, 2026');
  });

  it('finds and highlights a dog with a keyboard-reachable profile link', async () => {
    const { fixture, http } = await setup();
    http.expectOne('/api/v1/kennel-map?date=2026-03-31').flush(snapshot);
    await fixture.whenStable();
    fixture.detectChanges();

    const search = fixture.nativeElement.querySelector('input[type="search"]') as HTMLInputElement;
    search.value = 'map';
    search.dispatchEvent(new Event('input'));
    (fixture.nativeElement.querySelector('.dog-finder') as HTMLFormElement).dispatchEvent(
      new Event('submit'),
    );
    await new Promise((resolve) => setTimeout(resolve, 0));
    fixture.detectChanges();

    const highlighted = fixture.nativeElement.querySelector('.resident-dog.highlighted');
    expect(highlighted.textContent).toContain('Maple');
    expect(fixture.nativeElement.querySelector('.search-announcement').textContent).toContain(
      'A1-01',
    );
  });

  it('shows unavailable states with text and handles an API error', async () => {
    const ready = await setup('/kennel?layer=unavailable');
    ready.http.expectOne('/api/v1/kennel-map?date=2026-03-31').flush(snapshot);
    await ready.fixture.whenStable();
    ready.fixture.detectChanges();
    expect(ready.fixture.nativeElement.querySelector('.map-legend').textContent).toContain(
      'Injured',
    );
    expect(
      ready.fixture.nativeElement.querySelector('.resident-dog[data-tone="injured"]').textContent,
    ).toContain('Maple');

    TestBed.resetTestingModule();
    const failed = await setup();
    failed.http.expectOne('/api/v1/kennel-map?date=2026-03-31').flush('offline', {
      status: 503,
      statusText: 'Unavailable',
    });
    await failed.fixture.whenStable();
    failed.fixture.detectChanges();
    expect(failed.fixture.nativeElement.querySelector('[role="alert"]')).not.toBeNull();
  });

  it('normalizes unknown URL state to the canonical defaults', async () => {
    const { fixture, router, http } = await setup('/kennel?date=2030-01-01&layer=heatmap');
    http.expectOne('/api/v1/kennel-map?date=2026-03-31').flush(snapshot);
    await fixture.whenStable();
    fixture.detectChanges();

    expect(router.url).toContain('date=2026-03-31');
    expect(router.url).toContain('layer=default');
    expect(
      (fixture.nativeElement.querySelector('.layer-control button.active') as HTMLButtonElement)
        .textContent,
    ).toContain('Default');
  });
});
