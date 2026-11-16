import { Location } from '@angular/common';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { NavigationEnd, provideRouter, Router } from '@angular/router';
import { filter, firstValueFrom } from 'rxjs';

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

const nova: KennelMapResident = {
  ...maple,
  id: 'nova-id',
  name: 'Nova',
  availability: 'available',
  housing_code: 'B1-05',
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

@Component({ template: '' })
class TestProfileComponent {}

async function setup(url = '/demo/kennel') {
  await TestBed.configureTestingModule({
    imports: [KennelMapPageComponent],
    providers: [
      provideHttpClient(),
      provideHttpClientTesting(),
      provideRouter([
        { path: 'demo/kennel', component: KennelMapPageComponent },
        { path: 'demo/dogs/:id', component: TestProfileComponent },
      ]),
    ],
  }).compileComponents();
  const router = TestBed.inject(Router);
  router.setUpLocationChangeListener();
  await router.navigateByUrl(url);
  const fixture = TestBed.createComponent(KennelMapPageComponent);
  fixture.detectChanges();
  return {
    fixture,
    root: fixture.nativeElement as HTMLElement,
    router,
    http: TestBed.inject(HttpTestingController),
  };
}

async function render(fixture: ComponentFixture<KennelMapPageComponent>) {
  await fixture.whenStable();
  fixture.detectChanges();
}

function button(root: HTMLElement, groupName: string, name: string): HTMLButtonElement {
  const control = Array.from(root.querySelectorAll<HTMLButtonElement>(
    `[role="group"][aria-label="${groupName}"] button`,
  )).find((candidate) => candidate.textContent.trim() === name);
  if (!control) throw new Error(`Missing ${name} button in ${groupName}`);
  return control;
}

function locationCodes(root: HTMLElement): string[] {
  return Array.from(root.querySelectorAll<HTMLElement>('[data-location-code]'), (cell) =>
    cell.getAttribute('data-location-code')!,
  );
}

describe('KennelMapPageComponent', () => {
  afterEach(() => TestBed.inject(HttpTestingController).verify());

  it('renders the canonical row topology, puppy areas, and profile links', async () => {
    const { fixture, root, http } = await setup();
    expect(fixture.nativeElement.textContent).toContain('Loading the dated kennel snapshot');
    http.expectOne('/api/v1/kennel-map?date=2026-03-31').flush(snapshot);
    await fixture.whenStable();
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent;
    expect(text).toContain('A1-01');
    expect(text).toContain('B2-05');
    expect(text).toContain('PUPPY-A');
    expect(button(root, 'Map view', 'Overview').getAttribute('aria-pressed')).toBe('true');
    expect(root.querySelector('.kennel-canvas')).not.toBeNull();
    expect(root.querySelector('ht-ground-map')).toBeNull();
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
      'a[href="/demo/dogs/maple-id"]',
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

  it('waits for Find before showing a negative result and invalidates stale results on input', async () => {
    const { fixture, http } = await setup('/demo/kennel?date=2026-01-01');
    http.expectOne('/api/v1/kennel-map?date=2026-01-01').flush({
      ...snapshot,
      selected_date: '2026-01-01',
      locations: snapshot.locations.map((item) =>
        item.code === 'B1-05' ? { ...item, residents: [nova] } : item,
      ),
    });
    await fixture.whenStable();
    fixture.detectChanges();
    const search = fixture.nativeElement.querySelector('input[type="search"]') as HTMLInputElement;
    const form = fixture.nativeElement.querySelector('.dog-finder') as HTMLFormElement;
    const type = (value: string) => {
      search.value = value;
      search.dispatchEvent(new Event('input'));
      fixture.detectChanges();
    };
    const find = async () => {
      form.dispatchEvent(new Event('submit'));
      await new Promise((resolve) => setTimeout(resolve, 0));
      fixture.detectChanges();
    };

    type('Nov');
    expect(fixture.nativeElement.querySelector('.search-announcement')).toBeNull();
    await find();
    expect(fixture.nativeElement.querySelector('.search-announcement').textContent).toContain('Nova is in B1-05');
    await find();
    expect(fixture.nativeElement.querySelector('.resident-dog.highlighted').textContent).toContain('Nova');

    type('Unknown');
    expect(fixture.nativeElement.querySelector('.search-announcement')).toBeNull();
    await find();
    expect(fixture.nativeElement.querySelector('.search-announcement.not-found').textContent)
      .toContain('Unknown');
    type('Nova');
    expect(fixture.nativeElement.querySelector('.search-announcement')).toBeNull();
    await find();
    expect(fixture.nativeElement.querySelector('.search-announcement').textContent).toContain('B1-05');
    type('');
    await find();
    expect(fixture.nativeElement.querySelector('.search-announcement')).toBeNull();
  });

  it('invalidates search on date change and resolves only the new effective residents', async () => {
    const { fixture, http } = await setup('/demo/kennel?date=2026-01-01');
    http.expectOne('/api/v1/kennel-map?date=2026-01-01').flush({
      ...snapshot,
      selected_date: '2026-01-01',
      locations: snapshot.locations.map((item) =>
        item.code === 'B1-05' ? { ...item, residents: [nova] } : item,
      ),
    });
    await fixture.whenStable();
    fixture.detectChanges();

    const search = fixture.nativeElement.querySelector('input[type="search"]') as HTMLInputElement;
    search.value = 'Nova';
    search.dispatchEvent(new Event('input'));
    (fixture.nativeElement.querySelector('.dog-finder') as HTMLFormElement).dispatchEvent(new Event('submit'));
    await new Promise((resolve) => setTimeout(resolve, 0));
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.search-announcement').textContent).toContain('B1-05');

    const date = fixture.nativeElement.querySelector('input[type="date"]') as HTMLInputElement;
    date.value = '2026-03-31';
    date.dispatchEvent(new Event('input'));
    await new Promise((resolve) => setTimeout(resolve, 0));
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.search-announcement')).toBeNull();
    http.expectOne('/api/v1/kennel-map?date=2026-03-31').flush({
      ...snapshot,
      locations: snapshot.locations.map((item) =>
        item.code === 'B2-01' ? { ...item, residents: [{ ...nova, housing_code: 'B2-01' }] } : item,
      ),
    });
    await fixture.whenStable();
    fixture.detectChanges();
    (fixture.nativeElement.querySelector('.dog-finder') as HTMLFormElement).dispatchEvent(new Event('submit'));
    await new Promise((resolve) => setTimeout(resolve, 0));
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.search-announcement').textContent).toContain('B2-01');

    date.value = '2026-02-01';
    date.dispatchEvent(new Event('input'));
    await new Promise((resolve) => setTimeout(resolve, 0));
    fixture.detectChanges();
    http.expectOne('/api/v1/kennel-map?date=2026-02-01').flush({
      ...snapshot,
      selected_date: '2026-02-01',
    });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.search-announcement')).toBeNull();
    (fixture.nativeElement.querySelector('.dog-finder') as HTMLFormElement).dispatchEvent(new Event('submit'));
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.search-announcement.not-found').textContent)
      .toContain('Nova');
  });

  it('shows unavailable states with text and handles an API error', async () => {
    const ready = await setup('/demo/kennel?layer=unavailable');
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
    const { fixture, root, router, http } = await setup(
      '/demo/kennel?date=2030-01-01&layer=heatmap&view=table',
    );
    http.expectOne('/api/v1/kennel-map?date=2026-03-31').flush(snapshot);
    await fixture.whenStable();
    fixture.detectChanges();

    expect(router.url).toContain('date=2026-03-31');
    expect(router.url).toContain('layer=default');
    expect(router.parseUrl(router.url).queryParamMap.has('view')).toBe(false);
    expect(button(root, 'Map view', 'Overview').getAttribute('aria-pressed')).toBe('true');
    expect(root.querySelector('ht-ground-map')).toBeNull();
    expect(
      (fixture.nativeElement.querySelector('.layer-control button.active') as HTMLButtonElement)
        .textContent,
    ).toContain('Default');
  });

  it('switches active projections without stale DOM or requesting the same snapshot again', async () => {
    const { fixture, root, router, http } = await setup(
      '/demo/kennel?view=overview&date=2026-01-14&layer=class',
    );
    http.expectOne('/api/v1/kennel-map?date=2026-01-14').flush({
      ...snapshot,
      selected_date: '2026-01-14',
    });
    await render(fixture);
    const overviewOrder = locationCodes(root);
    expect(overviewOrder.length).toBe(22);
    expect(router.parseUrl(router.url).queryParams).toEqual({
      view: 'overview', date: '2026-01-14', layer: 'class',
    });

    button(root, 'Map view', 'Ground').click();
    await render(fixture);
    expect(router.parseUrl(router.url).queryParams).toEqual({
      view: 'ground', date: '2026-01-14', layer: 'class',
    });
    expect(button(root, 'Map view', 'Ground').getAttribute('aria-pressed')).toBe('true');
    expect(root.querySelector('.kennel-canvas')).toBeNull();
    const ground = root.querySelector('ht-ground-map');
    expect(ground?.querySelector('[aria-label="Ground map viewport"]')).not.toBeNull();
    expect(locationCodes(root)).toEqual(overviewOrder);
    const ids = Array.from(root.querySelectorAll('[id]'), (element) => element.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(root.querySelectorAll('a[href="/demo/dogs/maple-id"]').length).toBe(1);

    button(root, 'Map view', 'Overview').click();
    await render(fixture);
    expect(root.querySelector('ht-ground-map')).toBeNull();
    expect(root.querySelector('.kennel-canvas')).not.toBeNull();
    expect(locationCodes(root)).toEqual(overviewOrder);
    const params = router.parseUrl(router.url).queryParamMap;
    expect(params.get('date')).toBe('2026-01-14');
    expect(params.get('layer')).toBe('class');
    expect(params.get('view') ?? 'overview').toBe('overview');
    http.expectNone((request) => request.url.includes('/kennel-map'));
  });

  it('restores the active projection and layer on Back and Forward', async () => {
    const { fixture, root, router, http } = await setup(
      '/demo/kennel?view=overview&date=2026-01-14&layer=class',
    );
    http.expectOne('/api/v1/kennel-map?date=2026-01-14').flush({
      ...snapshot,
      selected_date: '2026-01-14',
    });
    await render(fixture);
    button(root, 'Map view', 'Ground').click();
    await render(fixture);
    button(root, 'Visual layer', 'Unavailable').click();
    await render(fixture);

    const history = TestBed.inject(Location);
    const travel = async (direction: 'back' | 'forward', view: string, layer: string) => {
      history[direction]();
      await new Promise((resolve) => setTimeout(resolve, 0));
      await render(fixture);
      expect(router.parseUrl(router.url).queryParams).toEqual({ view, date: '2026-01-14', layer });
      expect(root.querySelector('ht-ground-map') !== null).toBe(view === 'ground');
      expect(root.querySelector('.map-legend')?.getAttribute('aria-label')).toBe(`${layer} layer legend`);
    };
    await travel('back', 'ground', 'class');
    await travel('back', 'overview', 'class');
    await travel('forward', 'ground', 'class');
    await travel('forward', 'ground', 'unavailable');
    http.expectNone((request) => request.url.includes('/kennel-map'));
  });

  it('applies all five Ground layers and keeps view, date, and the ordered map', async () => {
    const { fixture, root, router, http } = await setup('/demo/kennel?view=ground&date=2026-01-14');
    http.expectOne('/api/v1/kennel-map?date=2026-01-14').flush({
      ...snapshot,
      selected_date: '2026-01-14',
    });
    await render(fixture);
    const order = locationCodes(root);
    expect(order.length).toBe(22);

    const layers = [
      { name: 'Gender', value: 'gender', dog: 'maple-id', tone: 'female', legend: 'Female' },
      { name: 'Neutered', value: 'neutered', dog: 'fjord-id', tone: 'neutered', legend: 'Neutered / spayed' },
      { name: 'Class', value: 'class', dog: 'maple-id', tone: 'standard', legend: 'Puppy' },
      { name: 'Unavailable', value: 'unavailable', dog: 'maple-id', tone: 'injured', legend: 'Injured' },
      { name: 'Default', value: 'default', dog: 'taro-id', tone: 'default', legend: 'Class and sex' },
    ];
    for (const layer of layers) {
      const control = button(root, 'Visual layer', layer.name);
      control.click();
      await render(fixture);
      expect(control.getAttribute('aria-pressed')).toBe('true');
      expect(root.querySelector('.map-legend')?.textContent).toContain(layer.legend);
      expect(root.querySelector(`#map-dog-${layer.dog}`)?.getAttribute('data-tone')).toBe(layer.tone);
      expect(router.parseUrl(router.url).queryParams).toEqual({
        view: 'ground', date: '2026-01-14', layer: layer.value,
      });
      expect(locationCodes(root)).toEqual(order);
      http.expectNone((request) => request.url.includes('/kennel-map'));
    }

    const date = root.querySelector<HTMLInputElement>('input[type="date"]')!;
    date.value = '2026-02-01';
    date.dispatchEvent(new Event('input'));
    await render(fixture);
    expect(root.textContent).toContain('Loading the dated kennel snapshot');
    http.expectOne('/api/v1/kennel-map?date=2026-02-01').flush({
      ...snapshot,
      selected_date: '2026-02-01',
    });
    await render(fixture);
    expect(router.parseUrl(router.url).queryParams).toEqual({
      view: 'ground', date: '2026-02-01', layer: 'default',
    });
    expect(root.textContent).toContain('February 1, 2026');
    expect(root.querySelector('ht-ground-map')).not.toBeNull();

    date.value = '';
    date.dispatchEvent(new Event('input'));
    await render(fixture);
    http.expectOne('/api/v1/kennel-map?date=2026-03-31').flush(snapshot);
    await render(fixture);
    date.value = '';
    date.dispatchEvent(new Event('input'));
    await render(fixture);
    expect(date.value).toBe('2026-03-31');
    expect(router.parseUrl(router.url).queryParams).toEqual({
      view: 'ground', date: '2026-03-31', layer: 'default',
    });
    http.expectNone((request) => request.url.includes('/kennel-map'));
  });

  it('finds the dated resident in Ground and keeps its profile link reachable in either projection', async () => {
    const { fixture, root, router, http } = await setup('/demo/kennel?view=ground&date=2026-01-01');
    http.expectOne('/api/v1/kennel-map?date=2026-01-01').flush({
      ...snapshot,
      selected_date: '2026-01-01',
      locations: snapshot.locations.map((item) => {
        if (item.code === 'A1-01') {
          return { ...item, residents: [{ ...maple, id: 'prefix-id', name: 'Novaline' }] };
        }
        return item.code === 'B1-05' ? { ...item, residents: [nova] } : item;
      }),
    });
    await render(fixture);

    const find = async (query: string) => {
      const search = root.querySelector<HTMLInputElement>('input[type="search"]')!;
      search.value = query;
      search.dispatchEvent(new Event('input'));
      fixture.detectChanges();
      expect(root.querySelector('.search-announcement')).toBeNull();
      root.querySelector<HTMLFormElement>('.dog-finder')!.dispatchEvent(new Event('submit'));
      await new Promise((resolve) => setTimeout(resolve, 0));
      await render(fixture);
    };
    await find('line');
    expect(root.querySelector('.search-announcement')?.textContent).toContain('Novaline is in A1-01');
    await find('nov');
    expect(root.querySelector('.search-announcement')?.textContent).toContain('Novaline is in A1-01');
    await find('NoVa');
    expect(root.querySelector('.search-announcement')?.textContent).toContain('Nova is in B1-05');
    expect(document.activeElement).toBe(root.querySelector('ht-ground-map #map-dog-nova-id'));

    for (const view of ['Overview', 'Ground']) {
      button(root, 'Map view', view).click();
      await render(fixture);
      const link = root.querySelector<HTMLAnchorElement>('[data-location-code="B1-05"].highlighted a.highlighted');
      expect(link?.getAttribute('href')).toBe('/demo/dogs/nova-id');
      expect(link?.tabIndex).toBe(0);
    }
    http.expectNone((request) => request.url.includes('/kennel-map'));
    const navigated = firstValueFrom(router.events.pipe(filter((event) => event instanceof NavigationEnd)));
    root.querySelector<HTMLAnchorElement>('a.highlighted')!.click();
    fixture.destroy();
    await navigated;
    expect(router.url).toBe('/demo/dogs/nova-id');
  });

  it('lists every resident in sparse and crowded adult and puppy locations', async () => {
    const { fixture, root, http } = await setup('/demo/kennel?view=ground');
    const occupancies = new Map([
      ['A1-01', 0], ['A1-02', 1], ['A1-03', 2], ['A1-04', 3], ['A1-05', 4],
      ['B1-05', 12], ['PUPPY-A', 8],
    ]);
    const crowded: KennelMapSnapshot = {
      ...snapshot,
      summary: {
        ...snapshot.summary,
        resident_dogs: Array.from(occupancies.values()).reduce((sum, count) => sum + count, 0),
        occupied_locations: 6,
      },
      locations: snapshot.locations.map((item) => ({
        ...item,
        residents: Array.from({ length: occupancies.get(item.code) ?? 0 }, (_, index) => ({
          ...(item.location_type === 'puppy_area' ? taro : maple),
          id: `fixture-${item.code}-${index}`,
          name: `Long synthetic fixture name ${item.code} resident ${index + 1}`,
          housing_code: item.code,
        })),
      })),
    };
    http.expectOne('/api/v1/kennel-map?date=2026-03-31').flush(crowded);
    await render(fixture);

    for (const view of ['Ground', 'Overview']) {
      button(root, 'Map view', view).click();
      await render(fixture);
      expect(locationCodes(root)).toEqual(crowded.locations.map((item) => item.code));
      for (const item of crowded.locations) {
        const cell = root.querySelector<HTMLElement>(`[data-location-code="${item.code}"]`)!;
        const labels = Array.from(cell.querySelectorAll('.resident-dog strong'), (node) => node.textContent);
        expect(labels).toEqual(item.residents.map((dog) => dog.name));
        expect(cell.getAttribute('aria-label')).toContain(`${item.residents.length} / ${item.capacity}`);
        if (view === 'Ground' && !item.residents.length) expect(cell.textContent).toContain('Empty');
      }
      expect(root.querySelectorAll('a.resident-dog').length).toBe(crowded.summary.resident_dogs);
    }
    http.expectNone((request) => request.url.includes('/kennel-map'));
  });

  it('retries a failed Ground snapshot and shows the topology on an empty date', async () => {
    const { fixture, root, http } = await setup('/demo/kennel?view=ground');
    expect(root.textContent).toContain('Loading the dated kennel snapshot');
    expect(root.querySelector('ht-ground-map')).toBeNull();
    http.expectOne('/api/v1/kennel-map?date=2026-03-31').flush(snapshot);
    await render(fixture);
    const search = root.querySelector<HTMLInputElement>('input[type="search"]')!;
    search.value = 'Maple';
    search.dispatchEvent(new Event('input'));
    root.querySelector<HTMLFormElement>('.dog-finder')!.dispatchEvent(new Event('submit'));
    await render(fixture);
    expect(root.querySelector('.search-announcement')?.textContent).toContain('Maple');

    const date = root.querySelector<HTMLInputElement>('input[type="date"]')!;
    date.value = '2026-02-01';
    date.dispatchEvent(new Event('input'));
    await render(fixture);
    http.expectOne('/api/v1/kennel-map?date=2026-02-01').flush('offline', {
      status: 503,
      statusText: 'Unavailable',
    });
    await render(fixture);
    const error = root.querySelector('[role="alert"]');
    expect(error?.textContent).toContain('The kennel map is temporarily unavailable');
    expect(root.querySelector('ht-ground-map')).toBeNull();
    expect(root.querySelector('.search-announcement')).toBeNull();

    error?.querySelector('button')?.click();
    await render(fixture);
    expect(root.textContent).toContain('Loading the dated kennel snapshot');
    http.expectOne('/api/v1/kennel-map?date=2026-02-01').flush({
      ...snapshot,
      selected_date: '2026-02-01',
      summary: {
        ...snapshot.summary,
        resident_dogs: 0,
        occupied_locations: 0,
        unavailable_dogs: 0,
      },
      locations: snapshot.locations.map((item) => ({ ...item, residents: [] })),
    });
    await render(fixture);
    expect(root.querySelector('[role="alert"]')).toBeNull();
    expect(root.textContent).toContain('No resident dogs on this date');
    expect(root.querySelector('ht-ground-map')).not.toBeNull();
    expect(root.querySelector('.search-announcement')).toBeNull();
    expect(root.querySelectorAll('ht-kennel-location-card').length).toBe(22);
    expect(root.querySelectorAll('a.resident-dog').length).toBe(0);
  });
});
