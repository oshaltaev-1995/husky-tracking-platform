import { provideHttpClient } from '@angular/common/http';
import { Location } from '@angular/common';
import { HttpTestingController, provideHttpClientTesting, TestRequest } from '@angular/common/http/testing';
import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter, Router, RouterOutlet } from '@angular/router';

import { DemoSessionService } from '../../core/api/demo-session.service';
import {
  KennelMapLocation,
  KennelMapResident,
  KennelMapSnapshot,
} from '../../core/api/kennel-map.models';
import { KennelMapPageComponent } from './kennel-map-page.component';
import { housingDateGuard, housingLeaveGuard } from './housing-navigation.guard';

const ATLAS = '00000000-0000-4000-8000-000000000001';
const MAPLE = '00000000-0000-4000-8000-000000000002';

function dog(id: string, name: string, code: string): KennelMapResident {
  return {
    id,
    name,
    housing_code: code,
    sex: 'female',
    is_neutered: false,
    dog_class: code.startsWith('PUPPY') ? 'puppy' : 'standard',
    availability: name === 'Maple' ? 'injured' : 'available',
    lifecycle: 'active',
    litter_code: code === 'PUPPY-A' ? 'T' : null,
    photo_key: null,
  };
}

function location(code: string, residents: KennelMapResident[]): KennelMapLocation {
  const puppy = code.startsWith('PUPPY');
  return {
    id: code,
    code,
    display_name: code,
    location_type: puppy ? 'puppy_area' : 'adult_enclosure',
    zone: puppy ? 'PUPPY' : code[0],
    row: puppy ? code.slice(-1) : code[1],
    position: puppy ? 1 : Number(code.slice(-2)),
    capacity: puppy ? 5 : 2,
    is_active: true,
    residents,
  };
}

function snapshot(): KennelMapSnapshot {
  return {
    selected_date: '2026-03-31',
    season_start: '2025-12-01',
    season_end: '2026-03-31',
    reference_date: '2026-03-31',
    housing_edit: {
      editable: true,
      effective_date: '2026-03-31',
      revision: 0,
      precondition: 'test-only-initial-precondition',
      reason: null,
    },
    summary: {
      resident_dogs: 9,
      occupied_locations: 4,
      unavailable_dogs: 1,
      class_counts: { standard: 3, puppy: 6 },
      sex_counts: { female: 9 },
      neutered_counts: { intact: 9 },
      availability_counts: { available: 8, injured: 1 },
    },
    locations: [
      location('A1-01', [dog(ATLAS, 'Atlas', 'A1-01'), dog(MAPLE, 'Maple', 'A1-01')]),
      location('A1-02', []),
      location('B1-05', [dog('freya-id', 'Freya', 'B1-05')]),
      location('PUPPY-A', ['Taro', 'Tessa', 'Theo', 'Tindra', 'Toast'].map((name) =>
        dog(`fixture-${name}`, name, 'PUPPY-A'),
      )),
      location('PUPPY-B', [dog('viva-id', 'Viva', 'PUPPY-B')]),
    ],
  };
}

function immutable<T>(value: T): T {
  if (value && typeof value === 'object') {
    Object.values(value).forEach((child) => immutable(child));
    Object.freeze(value);
  }
  return value;
}

@Component({ template: '<h1>Test profile</h1>' })
class TestProfileComponent {}

@Component({ imports: [RouterOutlet], template: '<router-outlet />' })
class TestRouterComponent {}

async function setup(data = snapshot(), view: 'overview' | 'ground' = 'overview') {
  await TestBed.configureTestingModule({
    imports: [TestRouterComponent],
    providers: [
      provideHttpClient(),
      provideHttpClientTesting(),
      provideRouter([
        {
          path: 'demo/kennel', component: KennelMapPageComponent,
          canActivate: [housingDateGuard], canDeactivate: [housingLeaveGuard],
          runGuardsAndResolvers: 'paramsOrQueryParamsChange',
        },
        { path: 'demo/dogs/:id', component: TestProfileComponent },
      ]),
    ],
  }).compileComponents();
  const router = TestBed.inject(Router);
  router.setUpLocationChangeListener();
  const fixture = TestBed.createComponent(TestRouterComponent);
  fixture.detectChanges();
  await router.navigateByUrl(`/demo/kennel?date=${data.selected_date}&view=${view}`);
  fixture.detectChanges();
  const http = TestBed.inject(HttpTestingController);
  http.expectOne(`/api/v1/kennel-map?date=${data.selected_date}`).flush(data);
  await render(fixture);
  return { fixture, root: fixture.nativeElement as HTMLElement, http, router };
}

async function render(fixture: ComponentFixture<unknown>): Promise<void> {
  await fixture.whenStable();
  fixture.detectChanges();
}

async function pendingNavigation(fixture: ComponentFixture<unknown>): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0));
  fixture.detectChanges();
}

function control(root: ParentNode, label: string): HTMLButtonElement {
  const found = Array.from(root.querySelectorAll<HTMLButtonElement>('button'))
    .find((button) => button.textContent.trim() === label || button.getAttribute('aria-label') === label);
  if (!found) throw new Error(`Missing button: ${label}`);
  return found;
}

function select(root: HTMLElement, label: string, value: string): void {
  const field = root.querySelector<HTMLSelectElement>(`select[aria-label="${label}"]`)
    ?? Array.from(root.querySelectorAll<HTMLLabelElement>('label'))
      .filter((candidate) => candidate.textContent.trim().startsWith(label))
      .map((candidate) => candidate.querySelector('select')
        ?? root.ownerDocument.getElementById(candidate.htmlFor) as HTMLSelectElement)
      .find(Boolean);
  if (!field) throw new Error(`Missing select: ${label}`);
  field.value = value;
  field.dispatchEvent(new Event('change', { bubbles: true }));
}

async function stage(fixture: ComponentFixture<unknown>, root: HTMLElement, dogId: string, code: string): Promise<void> {
  select(root, 'Dog to move', dogId);
  await render(fixture);
  select(root, 'Move to', code);
  await render(fixture);
  control(root, 'Stage move').click();
  await render(fixture);
}

function review(root: HTMLElement): void {
  const button = Array.from(root.querySelectorAll<HTMLButtonElement>('button'))
    .find((candidate) => /^Review \d+ moves?$/.test(candidate.textContent.trim()));
  if (!button) throw new Error('Missing Review changes button');
  button.focus();
  button.click();
}

function residents(root: HTMLElement, code: string): string[] {
  return Array.from(root.querySelectorAll(`[data-location-code="${code}"] .resident-dog .resident-copy strong`),
    (name) => name.textContent.trim(),
  );
}

function noMoves(http: HttpTestingController): void {
  http.expectNone((request) => request.method === 'POST' && request.url === '/api/v1/kennel-map/moves');
}

function dragTransfer() {
  const values = new Map<string, string>();
  return {
    get types() { return Array.from(values.keys()); },
    setData: (key: string, value: string) => values.set(key, value),
    getData: (key: string) => values.get(key) ?? '',
    effectAllowed: 'none',
    dropEffect: 'none',
  };
}

function drag(element: Element, type: string, dataTransfer: ReturnType<typeof dragTransfer>): void {
  const event = new Event(type, { bubbles: true, cancelable: true });
  Object.defineProperty(event, 'dataTransfer', { value: dataTransfer });
  element.dispatchEvent(event);
}

async function prepared() {
  const context = await setup();
  control(context.root, 'Move dogs').click();
  await render(context.fixture);
  await stage(context.fixture, context.root, ATLAS, 'PUPPY-A');
  await render(context.fixture);
  review(context.root);
  await render(context.fixture);
  return context;
}

function confirm(root: HTMLElement, http: HttpTestingController): TestRequest {
  control(root.querySelector('[role="dialog"]')!, 'Confirm moves').click();
  return http.expectOne('/api/v1/kennel-map/moves');
}

describe('Kennel Map Move Together', () => {
  afterEach(() => TestBed.inject(HttpTestingController).verify());

  it('starts in View and accepts the server editing context with revision zero', async () => {
    const { fixture, root, http } = await setup();
    expect(root.querySelector('select')).toBeNull();
    expect(root.querySelector(`a[href="/demo/dogs/${ATLAS}"]`)).not.toBeNull();
    control(root, 'Move dogs').click();
    await render(fixture);
    expect(root.textContent).toContain('Housing changes affect your demo workspace only');
    expect(root.querySelector('select')).not.toBeNull();
    noMoves(http);
  });

  for (const reason of ['historical_date', 'workspace_required'] as const) {
    it(`keeps a ${reason} snapshot read-only without a mutation`, async () => {
      const data = snapshot();
      data.housing_edit = {
        editable: false, effective_date: '2026-03-31', revision: null,
        precondition: null, reason,
      };
      if (reason === 'historical_date') data.selected_date = '2026-03-29';
      const { root, http } = await setup(data);
      const move = Array.from(root.querySelectorAll<HTMLButtonElement>('button'))
        .find((button) => button.textContent.trim() === 'Move dogs');
      expect(move === undefined || move.disabled).toBe(true);
      expect(root.querySelector('select')).toBeNull();
      expect(root.textContent?.toLowerCase()).toContain(reason === 'historical_date' ? 'read-only' : 'session');
      noMoves(http);
    });
  }

  for (const missing of ['revision', 'precondition', 'matching date']) {
    it(`requires a coherent editing context including ${missing}`, async () => {
      const data = snapshot();
      if (missing === 'revision') data.housing_edit.revision = null;
      if (missing === 'precondition') data.housing_edit.precondition = null;
      if (missing === 'matching date') data.housing_edit.effective_date = '2026-03-30';
      const { root, http } = await setup(data);
      expect(control(root, 'Move dogs').disabled).toBe(true);
      expect(root.querySelector('select')).toBeNull();
      noMoves(http);
    });
  }

  it('never edits through an old reference snapshot while a historical request loads or fails', async () => {
    const { fixture, root, http } = await setup();
    const date = root.querySelector<HTMLInputElement>('input[type="date"]')!;
    date.value = '2026-03-29';
    date.dispatchEvent(new Event('input'));
    await render(fixture);
    expect(root.textContent).toContain('Loading the dated kennel snapshot');
    const editing = () => Array.from(root.querySelectorAll<HTMLButtonElement>('button'))
      .filter((button) => button.textContent.trim() === 'Move dogs');
    expect(editing().every((button) => button.disabled)).toBe(true);
    expect(root.querySelector('select')).toBeNull();
    http.expectOne('/api/v1/kennel-map?date=2026-03-29')
      .flush('offline', { status: 503, statusText: 'Unavailable' });
    await render(fixture);
    expect(root.querySelector('[role="alert"]')).not.toBeNull();
    expect(editing().every((button) => button.disabled)).toBe(true);
    expect(root.querySelector('select')).toBeNull();
    noMoves(http);
  });

  it('previews occupied placement in both views without mutating the committed snapshot', async () => {
    const data = immutable(snapshot());
    const original = JSON.stringify(data);
    const { fixture, root, http } = await setup(data);
    control(root, 'Move dogs').click();
    await render(fixture);
    await stage(fixture, root, ATLAS, 'B1-05');
    await render(fixture);
    await stage(fixture, root, MAPLE, 'B1-05');
    await render(fixture);
    expect(residents(root, 'A1-01')).toEqual([]);
    expect(new Set(residents(root, 'B1-05'))).toEqual(new Set(['Freya', 'Atlas', 'Maple']));
    expect(root.textContent).toContain('Preview');
    for (const view of ['Ground', 'Overview']) {
      control(root, view).click();
      await render(fixture);
      expect(root.querySelectorAll('.resident-dog').length).toBe(9);
      expect(new Set(Array.from(root.querySelectorAll('.resident-dog'), (link) => link.id)).size).toBe(9);
      expect(residents(root, 'B1-05').length).toBe(3);
      noMoves(http);
      http.expectNone((request) => request.url === '/api/v1/kennel-map');
    }
    control(root, 'Class').click();
    await render(fixture);
    expect(residents(root, 'B1-05').length).toBe(3);
    expect(JSON.stringify(data)).toBe(original);
    noMoves(http);
  });

  for (const view of ['overview', 'ground'] as const) {
    it(`stages ${view} drag/drop locally and a cancelled gesture leaves placement unchanged`, async () => {
      const { fixture, root, http } = await setup(snapshot(), view);
      control(root, 'Move dogs').click();
      await render(fixture);
      const source = root.querySelector(`[id="map-dog-${ATLAS}"]`)!;
      const transfer = dragTransfer();
      drag(source, 'dragstart', transfer);
      drag(source, 'dragend', transfer);
      await render(fixture);
      expect(residents(root, 'A1-01')).toContain('Atlas');
      expect(root.querySelector('.draft-summary')).toBeNull();
      noMoves(http);

      drag(source, 'dragstart', transfer);
      const target = root.querySelector('[data-location-code="B1-05"]')!;
      drag(target, 'dragover', transfer);
      drag(target, 'drop', transfer);
      drag(source, 'dragend', transfer);
      await render(fixture);
      expect(residents(root, 'B1-05')).toContain('Atlas');
      expect(residents(root, 'A1-01')).not.toContain('Atlas');
      expect(root.textContent).toContain('Pending move');
      noMoves(http);
    });
  }

  it('searches the pending housing and keeps beforeunload warnings scoped to an unsaved draft', async () => {
    const { fixture, root, http } = await setup(snapshot(), 'ground');
    const event = () => new Event('beforeunload', { cancelable: true });
    const clean = event();
    window.dispatchEvent(clean);
    expect(clean.defaultPrevented).toBe(false);
    control(root, 'Move dogs').click();
    await render(fixture);
    await stage(fixture, root, ATLAS, 'PUPPY-A');
    const dirty = event();
    window.dispatchEvent(dirty);
    expect(dirty.defaultPrevented).toBe(true);
    const search = root.querySelector<HTMLInputElement>('input[type="search"]')!;
    search.value = 'Atlas';
    search.dispatchEvent(new Event('input'));
    root.querySelector<HTMLFormElement>('.dog-finder')!.dispatchEvent(new Event('submit'));
    await render(fixture);
    expect(root.querySelector('.search-announcement')?.textContent).toContain('Atlas is in PUPPY-A');
    expect(root.ownerDocument.activeElement?.id).toBe(`map-dog-${ATLAS}`);
    control(root, 'Discard').click();
    await render(fixture);
    const discarded = event();
    window.dispatchEvent(discarded);
    expect(discarded.defaultPrevented).toBe(false);
    fixture.destroy();
    const disposed = event();
    window.dispatchEvent(disposed);
    expect(disposed.defaultPrevented).toBe(false);
    noMoves(http);
  });

  it('normalizes repeated moves and Undo restores the previous intention', async () => {
    const { fixture, root, http } = await setup();
    control(root, 'Move dogs').click();
    await render(fixture);
    await stage(fixture, root, ATLAS, 'B1-05');
    await render(fixture);
    await stage(fixture, root, ATLAS, 'PUPPY-A');
    await render(fixture);
    expect(residents(root, 'PUPPY-A')).toContain('Atlas');
    control(root, 'Undo').click();
    await render(fixture);
    expect(residents(root, 'B1-05')).toContain('Atlas');
    await stage(fixture, root, ATLAS, 'A1-01');
    await render(fixture);
    expect(residents(root, 'A1-01')).toContain('Atlas');
    expect(Array.from(root.querySelectorAll<HTMLButtonElement>('button'))
      .filter((button) => /^Review 0/.test(button.textContent.trim()))
      .every((button) => button.disabled)).toBe(true);
    control(root, 'Undo').click();
    await render(fixture);
    expect(residents(root, 'B1-05')).toContain('Atlas');
    await stage(fixture, root, ATLAS, 'B1-05');
    await render(fixture);
    control(root, 'Undo').click();
    await render(fixture);
    expect(residents(root, 'A1-01')).toContain('Atlas');
    noMoves(http);
  });

  it('shows every resulting resident in Review and Cancel preserves a writable draft', async () => {
    const { fixture, root, http } = await prepared();
    const dialog = root.querySelector('[role="dialog"]')!;
    expect(dialog.textContent).toContain('Review housing moves');
    expect(dialog.textContent).toContain('31 March 2026');
    for (const name of ['Atlas', 'Taro', 'Tessa', 'Theo', 'Tindra', 'Toast']) {
      expect(dialog.textContent).toContain(name);
    }
    expect(dialog.textContent).toContain('A1-01');
    expect(dialog.textContent).toContain('PUPPY-A');
    expect(dialog.textContent?.toLowerCase()).toContain('nominal');
    noMoves(http);
    control(dialog, 'Cancel').click();
    await render(fixture);
    expect(root.querySelector('[role="dialog"]')).toBeNull();
    expect(residents(root, 'PUPPY-A')).toContain('Atlas');
    review(root);
    await render(fixture);
    expect(root.querySelector('[role="dialog"]')).not.toBeNull();
    noMoves(http);
  });

  it('closes Review with Escape, restores focus, and discards only when explicitly asked', async () => {
    const { fixture, root, http } = await prepared();
    const dialog = root.querySelector<HTMLElement>('[role="dialog"]')!;
    expect(dialog.getAttribute('aria-modal')).toBe('true');
    expect(dialog.contains(root.ownerDocument.activeElement)).toBe(true);
    const actions = Array.from(dialog.querySelectorAll<HTMLButtonElement>('button:not([disabled])'));
    actions.at(-1)!.focus();
    actions.at(-1)!.dispatchEvent(new KeyboardEvent('keydown', {
      key: 'Tab', bubbles: true, cancelable: true,
    }));
    expect(root.ownerDocument.activeElement).toBe(actions[0]);
    actions[0].dispatchEvent(new KeyboardEvent('keydown', {
      key: 'Tab', shiftKey: true, bubbles: true, cancelable: true,
    }));
    expect(root.ownerDocument.activeElement).toBe(actions.at(-1)!);
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    await render(fixture);
    expect(root.querySelector('[role="dialog"]')).toBeNull();
    expect(residents(root, 'PUPPY-A')).toContain('Atlas');
    expect(root.ownerDocument.activeElement?.textContent).toMatch(/Review 1 move/);
    control(root, 'Discard').click();
    await pendingNavigation(fixture);
    const discard = root.querySelector('[role="dialog"]');
    if (discard) control(discard, 'Discard changes').click();
    await render(fixture);
    expect(residents(root, 'A1-01')).toContain('Atlas');
    noMoves(http);
  });

  it('keeps the date, URL, and draft when a dirty date change or Profile navigation is cancelled', async () => {
    const { fixture, root, router, http } = await prepared();
    control(root.querySelector('[role="dialog"]')!, 'Cancel').click();
    await render(fixture);
    const date = root.querySelector<HTMLInputElement>('input[type="date"]')!;
    date.value = '2026-03-29';
    date.dispatchEvent(new Event('input'));
    await pendingNavigation(fixture);
    const warning = root.querySelector('[role="dialog"]')!;
    expect(warning.textContent).toContain('Discard housing changes?');
    control(warning, 'Keep editing').click();
    await render(fixture);
    expect(date.value).toBe('2026-03-31');
    expect(router.parseUrl(router.url).queryParams['date']).toBe('2026-03-31');
    expect(residents(root, 'PUPPY-A')).toContain('Atlas');
    http.expectNone('/api/v1/kennel-map?date=2026-03-29');

    const navigation = router.navigateByUrl(`/demo/dogs/${ATLAS}`);
    await pendingNavigation(fixture);
    control(root.querySelector('[role="dialog"]')!, 'Keep editing').click();
    expect(await navigation).toBe(false);
    await render(fixture);
    expect(router.url).toContain('/demo/kennel');
    expect(residents(root, 'PUPPY-A')).toContain('Atlas');
    noMoves(http);
  });

  it('guards browser Back and permits explicit Discard without saving or changing history data', async () => {
    const old = snapshot();
    old.selected_date = '2026-03-29';
    old.housing_edit = { editable: false, effective_date: '2026-03-31', revision: null, precondition: null, reason: 'historical_date' };
    const { fixture, root, router, http } = await setup(old);
    const date = root.querySelector<HTMLInputElement>('input[type="date"]')!;
    date.value = '2026-03-31';
    date.dispatchEvent(new Event('input'));
    await render(fixture);
    http.expectOne('/api/v1/kennel-map?date=2026-03-31').flush(snapshot());
    await render(fixture);
    control(root, 'Move dogs').click();
    await render(fixture);
    await stage(fixture, root, ATLAS, 'A1-02');
    await render(fixture);
    TestBed.inject(Location).back();
    await new Promise((resolve) => setTimeout(resolve, 0));
    await pendingNavigation(fixture);
    expect(root.querySelector('[role="dialog"]')?.textContent).toContain('Discard housing changes?');
    control(root.querySelector('[role="dialog"]')!, 'Discard changes').click();
    await render(fixture);
    http.expectOne('/api/v1/kennel-map?date=2026-03-29').flush(old);
    await render(fixture);
    expect(router.parseUrl(router.url).queryParams['date']).toBe('2026-03-29');
    expect(residents(root, 'A1-01')).toContain('Atlas');
    noMoves(http);
  });

  it('sends exactly one reviewed batch and adopts the full server response and next token', async () => {
    const { fixture, root, http } = await prepared();
    const submit = control(root.querySelector('[role="dialog"]')!, 'Confirm moves');
    submit.click();
    submit.click();
    submit.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    await render(fixture);
    const request = http.expectOne('/api/v1/kennel-map/moves');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({
      effective_date: '2026-03-31',
      precondition: 'test-only-initial-precondition',
      moves: [{ dog_id: ATLAS, destination_code: 'PUPPY-A' }],
    });
    expect(submit.disabled).toBe(true);
    const reply = snapshot();
    reply.housing_edit.revision = 7;
    reply.housing_edit.precondition = 'test-only-next-precondition';
    reply.locations[0].residents = reply.locations[0].residents.filter((dog) => dog.id !== ATLAS);
    reply.locations[3].residents.push({ ...dog(ATLAS, 'Atlas', 'PUPPY-A') });
    reply.locations[2].residents = [];
    reply.locations[4].residents.push(dog('freya-id', 'Freya', 'PUPPY-B'));
    reply.summary.occupied_locations = 3;
    request.flush(reply);
    await render(fixture);
    expect(root.querySelector('[role="dialog"]')).toBeNull();
    expect(root.textContent?.toLowerCase()).toContain('saved');
    expect(root.querySelector('.snapshot-strip')?.textContent).toContain('3');
    expect(residents(root, 'PUPPY-A')).toContain('Atlas');
    expect(residents(root, 'PUPPY-B')).toContain('Freya');
    noMoves(http);
    await stage(fixture, root, ATLAS, 'A1-02');
    await render(fixture);
    review(root);
    await render(fixture);
    const next = confirm(root, http);
    expect(next.request.body.precondition).toBe('test-only-next-precondition');
    next.flush(reply);
    await render(fixture);
  });

  for (const code of [401, 409, 422, 403, 500, 0]) {
    it(`handles HTTP ${code} without optimistic success or automatic mutation replay`, async () => {
      const { fixture, root, http } = await prepared();
      if (code === 401) {
        TestBed.inject(DemoSessionService).ensure().subscribe();
        http.expectOne('/api/v1/demo/session').flush({
          active: true, expires_at: '2099-01-01T00:00:00Z', ttl_hours: 24,
          ttl_seconds: 86400, created: false, replaced_expired: false,
        });
      }
      const request = confirm(root, http);
      if (code === 0) request.error(new ProgressEvent('error'));
      else request.flush({ detail: { code: code === 409 ? 'housing_changed' : code === 401 ? 'housing_session_required' : 'housing_invalid_destination', message: 'Controlled test failure' } }, { status: code, statusText: 'Rejected' });
      await render(fixture);
      expect(root.querySelector('[role="alert"]')).not.toBeNull();
      expect(root.textContent).not.toContain('Housing moves saved');
      noMoves(http);
      http.expectNone('/api/v1/demo/session');
      if ([401, 409, 500, 0].includes(code)) {
        control(root, 'Done moving').click();
        await pendingNavigation(fixture);
        control(root.querySelector('[role="dialog"]')!, 'Discard changes').click();
        await render(fixture);
        const enter = control(root, 'Move dogs');
        expect(enter.disabled).toBe(true);
        enter.click();
        await render(fixture);
        expect(root.querySelector('select')).toBeNull();
        noMoves(http);
      }
      if ([409, 500, 0].includes(code)) {
        expect(control(root, 'Reload housing')).not.toBeNull();
        expect(Array.from(root.querySelectorAll<HTMLButtonElement>('button'))
          .filter((button) => /^Review /.test(button.textContent.trim()))
          .every((button) => button.disabled)).toBe(true);
        if ([500, 0].includes(code)) expect(root.textContent?.toLowerCase()).toContain('not be confirmed');
        control(root, 'Reload housing').click();
        await render(fixture);
        http.expectOne('/api/v1/kennel-map?date=2026-03-31').flush(snapshot());
        await render(fixture);
        expect(residents(root, 'A1-01')).toContain('Atlas');
        noMoves(http);
      }
      if (code === 401) {
        control(root, 'Restore demo session').click();
        await render(fixture);
        // The HTTP interceptor can announce a replacement during explicit recovery.
        TestBed.inject(DemoSessionService).recognizeReplacement('2099-01-01T00:00:00Z');
        http.expectOne('/api/v1/demo/session').flush({
          active: true, expires_at: '2099-01-01T00:00:00Z', ttl_hours: 24,
          ttl_seconds: 86400, created: true, replaced_expired: false,
        });
        await render(fixture);
        http.expectOne('/api/v1/kennel-map?date=2026-03-31').flush(snapshot());
        await render(fixture);
        expect(residents(root, 'A1-01')).toContain('Atlas');
        expect(control(root, 'Move dogs').disabled).toBe(false);
        noMoves(http);
      }
    });
  }

  it('renders standard validation details as controlled text instead of raw object or HTML', async () => {
    const { fixture, root, http } = await prepared();
    confirm(root, http).flush({ detail: [{ loc: ['body', 'moves'], msg: 'Choose a valid destination <img src=x onerror=alert(1)>', type: 'value_error' }] }, { status: 422, statusText: 'Unprocessable Entity' });
    await render(fixture);
    expect(root.querySelector('[role="alert"]')).not.toBeNull();
    expect(root.textContent).not.toContain('[object Object]');
    expect(root.querySelector('img[src="x"]')).toBeNull();
    noMoves(http);
  });

  it('invalidates the pending confirmation on Reset and ignores an old save response', async () => {
    const { fixture, root, http } = await prepared();
    const oldSave = confirm(root, http);
    TestBed.inject(DemoSessionService).reset().subscribe();
    http.expectOne('/api/v1/demo/reset').flush({ status: 'reset', expires_at: '2099-01-01T00:00:00Z' });
    await render(fixture);
    http.expectOne('/api/v1/kennel-map?date=2026-03-31').flush(snapshot());
    await render(fixture);
    if (!oldSave.cancelled) oldSave.flush({ ...snapshot(), summary: { ...snapshot().summary, resident_dogs: 999 } });
    await render(fixture);
    expect(root.querySelector('[role="dialog"]')).toBeNull();
    expect(root.textContent).not.toContain('999');
    expect(residents(root, 'A1-01')).toContain('Atlas');
    noMoves(http);
  });

  it('invalidates a review after session replacement and restores without replaying it', async () => {
    const { fixture, root, http } = await prepared();
    TestBed.inject(DemoSessionService).recognizeReplacement('2099-01-01T00:00:00Z');
    await render(fixture);
    expect(root.querySelector('[role="dialog"]')).toBeNull();
    expect(residents(root, 'A1-01')).toContain('Atlas');
    expect(control(root, 'Restore demo session')).not.toBeNull();
    noMoves(http);
  });

  it('rejects an ordinary reload response after the workspace session is replaced', async () => {
    const { fixture, root, http } = await prepared();
    confirm(root, http).flush({ detail: { code: 'housing_changed', message: 'Stale preview' } }, {
      status: 409, statusText: 'Conflict',
    });
    await render(fixture);
    control(root, 'Reload housing').click();
    await render(fixture);
    const reload = http.expectOne('/api/v1/kennel-map?date=2026-03-31');
    TestBed.inject(DemoSessionService).recognizeReplacement('2099-01-01T00:00:00Z');
    const stale = snapshot();
    stale.summary.resident_dogs = 999;
    reload.flush(stale);
    await render(fixture);
    expect(root.textContent).not.toContain('999');
    expect(control(root, 'Restore demo session')).not.toBeNull();
    const entry = Array.from(root.querySelectorAll<HTMLButtonElement>('button'))
      .find((button) => button.textContent.trim() === 'Move dogs');
    if (entry) expect(entry.disabled).toBe(true);
    expect(root.querySelectorAll('select:not([disabled])').length).toBe(0);
    noMoves(http);
  });

  it('does not apply a late save to a profile opened after explicitly discarding its pending context', async () => {
    const { fixture, root, router, http } = await prepared();
    const request = confirm(root, http);
    const navigation = router.navigateByUrl(`/demo/dogs/${ATLAS}`);
    await pendingNavigation(fixture);
    control(root.querySelector('[role="dialog"]')!, 'Discard changes').click();
    expect(await navigation).toBe(true);
    await render(fixture);
    if (!request.cancelled) request.flush(snapshot());
    await render(fixture);
    expect(root.textContent).toContain('Test profile');
    expect(root.querySelector('ht-kennel-map-page')).toBeNull();
    expect(document.activeElement?.id).not.toBe(`map-dog-${ATLAS}`);
    noMoves(http);
  });
});
