import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter, Router, RouterOutlet } from '@angular/router';
import { vi } from 'vitest';

import { DemoSessionService } from '../../core/api/demo-session.service';
import {
  KennelMapLocation,
  KennelMapResident,
  KennelMapSnapshot,
} from '../../core/api/kennel-map.models';
import { housingDateGuard, housingLeaveGuard } from './housing-navigation.guard';
import { KennelMapPageComponent } from './kennel-map-page.component';

const ATLAS = '00000000-0000-4000-8000-000000000101';
const MAPLE = '00000000-0000-4000-8000-000000000102';

function dog(id: string, name: string, code: string): KennelMapResident {
  return {
    id, name, housing_code: code, sex: 'female', is_neutered: false,
    dog_class: code.startsWith('PUPPY') ? 'puppy' : 'standard',
    availability: name === 'Maple' ? 'injured' : 'available', lifecycle: 'active',
    litter_code: code.startsWith('PUPPY') ? 'T' : null, photo_key: null,
  };
}

function location(code: string, residents: KennelMapResident[] = []): KennelMapLocation {
  const puppy = code.startsWith('PUPPY');
  return {
    id: `test-only-location-${code}`, code, display_name: code,
    location_type: puppy ? 'puppy_area' : 'adult_enclosure',
    zone: puppy ? 'PUPPY' : code[0], row: puppy ? code.slice(-1) : code[1],
    position: puppy ? (code.endsWith('A') ? 1 : 2) : Number(code.slice(-2)),
    capacity: puppy ? 5 : 2, is_active: true, residents,
  };
}

function snapshot(): KennelMapSnapshot {
  const codes = ['A1', 'A2', 'B1', 'B2'].flatMap((row) =>
    Array.from({ length: 5 }, (_, index) => `${row}-${String(index + 1).padStart(2, '0')}`),
  );
  return {
    selected_date: '2026-03-31', season_start: '2025-12-01', season_end: '2026-03-31',
    reference_date: '2026-03-31',
    housing_edit: {
      editable: true, effective_date: '2026-03-31', revision: 0,
      precondition: 'test-only-private-precondition', reason: null,
    },
    summary: {
      resident_dogs: 3, occupied_locations: 2, unavailable_dogs: 1,
      class_counts: { standard: 2, puppy: 1 }, sex_counts: { female: 3 },
      neutered_counts: { intact: 3 }, availability_counts: { available: 2, injured: 1 },
    },
    locations: [
      ...codes.map((code) => location(code, code === 'A1-01' ? [
        dog(ATLAS, 'Atlas', code), dog(MAPLE, 'Maple', code),
      ] : [])),
      location('PUPPY-A', [dog('test-only-taro-id', 'Taro', 'PUPPY-A')]),
      location('PUPPY-B'),
    ],
  };
}

function committedMove(): KennelMapSnapshot {
  const data = snapshot();
  data.locations[0].residents = data.locations[0].residents.filter((resident) => resident.id !== ATLAS);
  data.locations.find((item) => item.code === 'PUPPY-A')!.residents.push(dog(ATLAS, 'Atlas', 'PUPPY-A'));
  data.housing_edit.revision = 1;
  data.housing_edit.precondition = 'test-only-next-private-precondition';
  return data;
}

@Component({ template: '<h1>Other page</h1>' })
class TestOtherPageComponent {}

@Component({ imports: [RouterOutlet], template: '<router-outlet />' })
class TestRouterComponent {}

async function render(fixture: ComponentFixture<unknown>): Promise<void> {
  await fixture.whenStable();
  fixture.detectChanges();
}

async function start(data = snapshot(), view = 'overview', layer = 'default') {
  await TestBed.configureTestingModule({
    imports: [TestRouterComponent],
    providers: [
      provideHttpClient(), provideHttpClientTesting(),
      provideRouter([
        {
          path: 'demo/kennel', component: KennelMapPageComponent,
          canActivate: [housingDateGuard], canDeactivate: [housingLeaveGuard],
          runGuardsAndResolvers: 'paramsOrQueryParamsChange',
        },
        { path: 'other', component: TestOtherPageComponent },
      ]),
    ],
  }).compileComponents();
  const router = TestBed.inject(Router);
  router.setUpLocationChangeListener();
  const fixture = TestBed.createComponent(TestRouterComponent);
  fixture.detectChanges();
  await router.navigateByUrl(`/demo/kennel?date=${data.selected_date}&view=${view}&layer=${layer}`);
  fixture.detectChanges();
  return { fixture, root: fixture.nativeElement as HTMLElement, http: TestBed.inject(HttpTestingController), router };
}

async function setup(data = snapshot(), view = 'overview', layer = 'default') {
  const context = await start(data, view, layer);
  context.http.expectOne(`/api/v1/kennel-map?date=${data.selected_date}`).flush(data);
  await render(context.fixture);
  return context;
}

type Context = Awaited<ReturnType<typeof setup>>;

function button(root: ParentNode, name: string): HTMLButtonElement {
  const match = Array.from(root.querySelectorAll<HTMLButtonElement>('button'))
    .find((control) => control.textContent.trim() === name || control.getAttribute('aria-label') === name);
  if (!match) throw new Error(`Missing button: ${name}`);
  return match;
}

function preview(): HTMLElement | null {
  return document.querySelector('ht-kennel-print-preview');
}

async function open(context: Context): Promise<HTMLElement> {
  const trigger = button(context.root, 'Print map');
  trigger.focus();
  trigger.click();
  await render(context.fixture);
  const modal = preview();
  if (!modal) throw new Error('Print preview did not open');
  return modal;
}

function documentRoot(): HTMLElement {
  const root = document.querySelector<HTMLElement>('ht-kennel-print-document');
  if (!root) throw new Error('Print document is absent');
  return root;
}

function noPrintRequests(http: HttpTestingController): void {
  http.expectNone((request) => request.url === '/api/v1/kennel-map' || request.method !== 'GET');
  http.expectNone('/api/v1/demo/session');
}

function blocked(root: HTMLElement): void {
  const trigger = button(root, 'Print map');
  expect(trigger.disabled).toBe(true);
  const description = trigger.getAttribute('aria-describedby');
  expect(description).not.toBeNull();
  expect(root.ownerDocument.getElementById(description!)?.textContent?.trim().length).toBeGreaterThan(0);
  trigger.click();
  expect(preview()).toBeNull();
}

async function stage(context: Context, id = ATLAS, code = 'PUPPY-A'): Promise<void> {
  const { root, fixture } = context;
  const dog = root.querySelector<HTMLSelectElement>('select[name="move-dog"]')!;
  dog.value = id;
  dog.dispatchEvent(new Event('change', { bubbles: true }));
  await render(fixture);
  const destination = root.querySelector<HTMLSelectElement>('select[name="move-destination"]')!;
  destination.value = code;
  destination.dispatchEvent(new Event('change', { bubbles: true }));
  await render(fixture);
  button(root, 'Stage move').click();
  await render(fixture);
}

async function saving(context: Context) {
  button(context.root, 'Review 1 move').click();
  await render(context.fixture);
  button(context.root.querySelector('[role="dialog"]')!, 'Confirm moves').click();
  await render(context.fixture);
  return context.http.expectOne('/api/v1/kennel-map/moves');
}

describe('Kennel Map print entry and committed context', () => {
  beforeEach(() => vi.spyOn(window, 'print').mockImplementation(() => undefined));

  afterEach(() => {
    TestBed.inject(HttpTestingController).verify();
    TestBed.resetTestingModule();
    expect(preview()).toBeNull();
    vi.restoreAllMocks();
  });

  for (const view of ['overview', 'ground']) {
    it(`prints the already loaded ${view} snapshot without another request or interactive identities`, async () => {
      const data = snapshot();
      const context = await setup(data, view, 'unavailable');
      const modal = await open(context);
      const dialog = modal.querySelector('[role="dialog"]')!;
      const name = dialog.getAttribute('aria-label')
        ?? document.getElementById(dialog.getAttribute('aria-labelledby') ?? '')?.textContent;
      expect(name).toBe('Kennel Map print preview');
      const doc = documentRoot();
      expect(doc.textContent).toContain('Kennel Map');
      expect(doc.textContent).toContain('31 March 2026');
      expect(doc.textContent).toContain('Unavailable');
      for (const item of data.locations) {
        expect(doc.querySelector(`[data-print-location="${item.code}"]`)).not.toBeNull();
        const roster = Array.from(doc.querySelectorAll(`[data-print-roster="${item.code}"] .printed-resident strong`),
          (resident) => resident.textContent?.trim(),
        );
        expect(doc.querySelector(`[data-print-roster="${item.code}"]`)).not.toBeNull();
        expect(roster).toEqual(item.residents.map((resident) => resident.name));
      }
      expect(doc.querySelectorAll('.printed-resident').length).toBe(data.summary.resident_dogs);
      for (const name of ['Atlas', 'Maple', 'Taro']) expect(doc.textContent).toContain(name);
      for (const privateValue of [ATLAS, MAPLE, data.housing_edit.precondition!, data.locations[0].id]) {
        expect(doc.outerHTML).not.toContain(privateValue);
        expect(document.title).not.toContain(privateValue);
      }
      expect(doc.querySelectorAll('[id^="map-dog-"]').length).toBe(0);
      expect(context.root.querySelectorAll(`a[href="/demo/dogs/${ATLAS}"]`).length).toBe(1);
      expect(window.print).not.toHaveBeenCalled();
      noPrintRequests(context.http);
      button(modal, 'Print / Save as PDF').click();
      await render(context.fixture);
      expect(window.print).toHaveBeenCalledTimes(1);
      window.dispatchEvent(new Event('afterprint'));
      await render(context.fixture);
      expect(preview()).not.toBeNull();
      expect(modal.textContent).not.toContain('PDF saved');
      noPrintRequests(context.http);
      button(modal, 'Close').click();
      await render(context.fixture);
      expect(document.activeElement === button(context.root, 'Print map')).toBe(true);
      expect(context.router.parseUrl(context.router.url).queryParams).toEqual({
        date: '2026-03-31', view, layer: 'unavailable',
      });
    });
  }

  for (const reason of ['historical_date', 'workspace_required'] as const) {
    it(`permits read-only ${reason} printing independently of housing edit authorization`, async () => {
      const data = snapshot();
      if (reason === 'historical_date') data.selected_date = '2026-03-29';
      data.housing_edit = { editable: false, effective_date: '2026-03-31', revision: null, precondition: null, reason };
      const context = await setup(data);
      expect(button(context.root, 'Move dogs').disabled).toBe(true);
      expect(button(context.root, 'Print map').disabled).toBe(false);
      const modal = await open(context);
      expect(documentRoot().textContent).toContain(reason === 'historical_date' ? '29 March 2026' : '31 March 2026');
      noPrintRequests(context.http);
      button(modal, 'Close').click();
      await render(context.fixture);
    });
  }

  it('offers a keyboard-reachable document and closes with Escape without invoking print', async () => {
    const context = await setup();
    const modal = await open(context);
    const region = modal.querySelector<HTMLElement>('[role="region"][aria-label="Kennel Map print document"]')!;
    expect(region).not.toBeNull();
    expect(region.tabIndex).toBe(0);
    expect(modal.contains(document.activeElement)).toBe(true);
    region.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }));
    await render(context.fixture);
    expect(preview()).toBeNull();
    expect(document.activeElement === button(context.root, 'Print map')).toBe(true);
    expect(window.print).not.toHaveBeenCalled();
    noPrintRequests(context.http);
  });

  it('holds a stable print projection and preserves view, layer, search, and focus across repeated previews', async () => {
    const data = snapshot();
    const context = await setup(data, 'ground', 'class');
    const search = context.root.querySelector<HTMLInputElement>('input[type="search"]')!;
    search.value = 'Atlas';
    search.dispatchEvent(new Event('input'));
    context.root.querySelector<HTMLFormElement>('.dog-finder')!.dispatchEvent(new Event('submit'));
    await render(context.fixture);
    const announcement = context.root.querySelector('.search-announcement')!.textContent;
    const viewport = context.root.querySelector<HTMLElement>('.ground-viewport')!;
    const board = context.root.querySelector<HTMLElement>('.ground-board')!;
    viewport.scrollLeft = 80;
    viewport.scrollTop = 120;
    const screenZoom = board.style.zoom;
    const original = JSON.stringify(data);
    for (let attempt = 0; attempt < 2; attempt++) {
      const modal = await open(context);
      const printed = documentRoot().textContent;
      expect(printed).toContain('Class');
      // The projection is frozen once opened, even if its source object later changes.
      if (attempt === 0) {
        data.locations[0].residents[0].name = 'Mutated test-only source name';
        expect(documentRoot().textContent).toBe(printed);
        data.locations[0].residents[0].name = 'Atlas';
      }
      expect(documentRoot().querySelector('.highlighted')).toBeNull();
      button(modal, 'Close').click();
      await render(context.fixture);
      expect(search.value).toBe('Atlas');
      expect(context.root.querySelector('.search-announcement')?.textContent).toBe(announcement);
      expect(context.root.querySelector('ht-ground-map')).not.toBeNull();
      expect(viewport.scrollLeft).toBe(80);
      expect(viewport.scrollTop).toBe(120);
      expect(board.style.zoom).toBe(screenZoom);
      expect(document.activeElement === button(context.root, 'Print map')).toBe(true);
      noPrintRequests(context.http);
    }
    expect(JSON.stringify(data)).toBe(original);
  });

  it('blocks pending moves, but permits Move mode and a normalized empty draft with Undo history', async () => {
    const context = await setup();
    button(context.root, 'Move dogs').click();
    await render(context.fixture);
    expect(button(context.root, 'Print map').disabled).toBe(false);
    await stage(context);
    blocked(context.root);
    noPrintRequests(context.http);
    await stage(context, ATLAS, 'A1-01');
    expect(button(context.root, 'Undo').disabled).toBe(false);
    expect(button(context.root, 'Print map').disabled).toBe(false);
    const modal = await open(context);
    expect(documentRoot().textContent).not.toContain('Pending move');
    expect(documentRoot().textContent).not.toContain('Preview updated');
    button(modal, 'Close').click();
    await render(context.fixture);
    await stage(context);
    button(context.root, 'Discard').click();
    await render(context.fixture);
    expect(button(context.root, 'Print map').disabled).toBe(false);
    noPrintRequests(context.http);
  });

  it('prints the complete saved server response only after the submitted move succeeds', async () => {
    const context = await setup();
    button(context.root, 'Move dogs').click();
    await render(context.fixture);
    await stage(context);
    const request = await saving(context);
    blocked(context.root);
    request.flush(committedMove());
    await render(context.fixture);
    expect(button(context.root, 'Print map').disabled).toBe(false);
    const modal = await open(context);
    const printLocations = documentRoot().querySelectorAll('[data-print-roster="PUPPY-A"]');
    expect(printLocations.length).toBeGreaterThan(0);
    const roster = Array.from(printLocations, (item) => item.textContent).join(' ');
    expect(roster).toContain('Atlas');
    expect(roster).toContain('Taro');
    noPrintRequests(context.http);
    button(modal, 'Close').click();
    await render(context.fixture);
  });

  for (const status of [409, 503, 401]) {
    it(`requires explicit recovery from HTTP ${status} before printing committed housing`, async () => {
      const context = await setup();
      button(context.root, 'Move dogs').click();
      await render(context.fixture);
      await stage(context);
      const request = await saving(context);
      request.flush({ detail: { code: status === 401 ? 'housing_session_required' : 'housing_changed', message: 'Test-only failure' } }, { status, statusText: 'Rejected' });
      await render(context.fixture);
      blocked(context.root);
      noPrintRequests(context.http);
      button(context.root, status === 401 ? 'Restore demo session' : 'Reload housing').click();
      await render(context.fixture);
      blocked(context.root);
      if (status === 401) {
        context.http.expectOne('/api/v1/demo/session').flush({
          active: true, expires_at: '2099-01-01T00:00:00Z', ttl_hours: 24,
          ttl_seconds: 86400, created: true, replaced_expired: false,
        });
        await render(context.fixture);
      }
      context.http.expectOne('/api/v1/kennel-map?date=2026-03-31').flush(committedMove());
      await render(context.fixture);
      expect(button(context.root, 'Print map').disabled).toBe(false);
      await open(context);
      noPrintRequests(context.http);
    });
  }

  it('blocks loading and error states instead of printing an older selected date', async () => {
    const context = await start();
    blocked(context.root);
    context.http.expectOne('/api/v1/kennel-map?date=2026-03-31').flush('offline', { status: 503, statusText: 'Unavailable' });
    await render(context.fixture);
    blocked(context.root);
    noPrintRequests(context.http);
  });

  for (const invalidation of ['date', 'reset', 'replacement', 'destroy']) {
    it(`closes the frozen print context on ${invalidation}`, async () => {
      const context = await setup();
      await open(context);
      if (invalidation === 'date') {
        await context.router.navigateByUrl('/demo/kennel?date=2026-03-29&view=overview&layer=default');
        await render(context.fixture);
        expect(preview()).toBeNull();
        const historical = snapshot();
        historical.selected_date = '2026-03-29';
        historical.housing_edit = { editable: false, effective_date: '2026-03-31', revision: null, precondition: null, reason: 'historical_date' };
        context.http.expectOne('/api/v1/kennel-map?date=2026-03-29').flush(historical);
        await render(context.fixture);
        await open(context);
        expect(documentRoot().textContent).toContain('29 March 2026');
      }
      if (invalidation === 'reset') {
        TestBed.inject(DemoSessionService).reset().subscribe();
        await render(context.fixture);
        expect(preview()).toBeNull();
        blocked(context.root);
        context.http.expectOne('/api/v1/demo/reset').flush({ status: 'reset', expires_at: '2099-01-01T00:00:00Z' });
        await render(context.fixture);
        blocked(context.root);
        context.http.expectOne('/api/v1/kennel-map?date=2026-03-31').flush(snapshot());
        await render(context.fixture);
        expect(button(context.root, 'Print map').disabled).toBe(false);
      }
      if (invalidation === 'replacement') {
        TestBed.inject(DemoSessionService).recognizeReplacement('2099-01-01T00:00:00Z');
        await render(context.fixture);
        expect(preview()).toBeNull();
        blocked(context.root);
      }
      if (invalidation === 'destroy') {
        context.fixture.destroy();
        expect(preview()).toBeNull();
        expect(document.querySelector('ht-kennel-print-document')).toBeNull();
      }
    });
  }
});
