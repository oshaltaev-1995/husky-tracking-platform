import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';

import {
  ActualEligibility,
  ActualSession,
  DailyEntry,
} from '../../core/api/daily-entry.models';
import { DailyEntryPageComponent } from './daily-entry-page.component';

const atlas = {
  id: 'atlas-id',
  name: 'Atlas',
  housing_code: 'A1-01',
  dog_class: 'standard',
  availability: 'available',
  capabilities: ['lead', 'team', 'wheel'],
  actual_km_today: 20,
  eligible: true,
  reasons: [],
};

const session: ActualSession = {
  id: 'session-id',
  revision: 1,
  work_date: '2026-03-31',
  start_time: '09:00:00',
  distance_km: 10,
  label: 'Forest Loop',
  note: 'Firm trail.',
  source: 'planned',
  planned_activity_id: 'activity-id',
  planned_activity_title: 'Forest Loop',
  plan_status: 'modified',
  deviations: ['1 dog substituted'],
  team_count: 1,
  participants: [
    {
      dog_id: 'atlas-id',
      dog_name: 'Atlas',
      housing_code: 'A1-01',
      dog_class: 'standard',
      availability: 'available',
      assigned_role: 'lead',
      actual_team_sequence: 1,
      pair_index: 0,
      pair_label: 'Lead',
      side: 'left',
      position_order: 1,
    },
  ],
};

function entry(overrides: Partial<DailyEntry> = {}): DailyEntry {
  return {
    selected_date: '2026-03-31',
    season_start: '2025-12-01',
    season_end: '2026-03-31',
    reference_date: '2026-03-31',
    plan_exists: true,
    planned_activities: [
      {
        id: 'activity-id',
        activity_type: 'training',
        title: 'Forest Loop',
        start_time: '09:00:00',
        distance_km: 10,
        participant_count: 2,
        recording_participant_names: ['Atlas', 'Aurora'],
        team_count: 1,
        arranged_dog_count: 2,
        actual_status: 'modified',
        actual_session_id: 'session-id',
        deviations: ['1 dog substituted'],
      },
      {
        id: 'walk-id',
        activity_type: 'open_space_walk',
        title: 'Yard walk',
        start_time: null,
        distance_km: null,
        participant_count: 3,
        recording_participant_names: ['Atlas', 'Aurora', 'Daisy'],
        team_count: 0,
        arranged_dog_count: 0,
        actual_status: 'context_only',
        actual_session_id: null,
        deviations: [],
      },
    ],
    sessions: [session],
    summary: { actual_sessions: 1, dogs_worked: 1, dog_starts: 1, total_dog_km: 10 },
    housing_groups: [
      {
        code: 'A1-01',
        display_name: 'Adult enclosure A1-01',
        zone: 'A',
        row: 'A1',
        position: 1,
        dogs: [
          {
            id: 'atlas-id',
            name: 'Atlas',
            housing_code: 'A1-01',
            dog_class: 'standard',
            availability: 'available',
            starts: 1,
            actual_km: 10,
          },
          {
            id: 'aurora-id',
            name: 'Aurora',
            housing_code: 'A1-01',
            dog_class: 'standard',
            availability: 'available',
            starts: 0,
            actual_km: 0,
          },
        ],
      },
    ],
    ...overrides,
  };
}

const eligibility: ActualEligibility = {
  selected_date: '2026-03-31',
  distance_km: 5,
  max_daily_km: 30,
  dogs: [
    atlas,
    {
      id: 'sanchez-id',
      name: 'Sanchez',
      housing_code: 'B2-03',
      dog_class: 'junior',
      availability: 'available',
      capabilities: [],
      actual_km_today: 0,
      eligible: false,
      reasons: ['Junior'],
    },
  ],
};

async function setup(url = '/daily-entry') {
  await TestBed.configureTestingModule({
    imports: [DailyEntryPageComponent],
    providers: [
      provideHttpClient(),
      provideHttpClientTesting(),
      provideRouter([
        { path: 'daily-entry', component: DailyEntryPageComponent },
        { path: 'dogs/:dogId', component: DailyEntryPageComponent },
      ]),
    ],
  }).compileComponents();
  const router = TestBed.inject(Router);
  await router.navigateByUrl(url);
  const fixture = TestBed.createComponent(DailyEntryPageComponent);
  fixture.detectChanges();
  return { fixture, router, http: TestBed.inject(HttpTestingController) };
}

describe('DailyEntryPageComponent', () => {
  afterEach(() => TestBed.inject(HttpTestingController).verify());

  it('reopens actual work, plan differences, totals, and zero-work residents', async () => {
    const { fixture, http } = await setup();
    expect(fixture.nativeElement.textContent).toContain('Loading actual work');
    http.expectOne('/api/v1/daily-entry/2026-03-31').flush(entry());
    await fixture.whenStable();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Dog-km');
    expect(fixture.nativeElement.textContent).toContain('Modified from plan');
    expect(fixture.nativeElement.textContent).toContain('1 dog substituted');
    expect(fixture.nativeElement.textContent).not.toContain('Existing actual');
    expect(fixture.nativeElement.querySelector('#daily-dog-aurora-id').textContent).toContain(
      '0 km',
    );
    expect(
      fixture.nativeElement.querySelector('#daily-dog-atlas-id').getAttribute('aria-label'),
    ).toContain('1 start');
    expect(fixture.nativeElement.textContent).toContain('No sled kilometres');
  });

  it('navigates dates and finds a dog in dated housing', async () => {
    const { fixture, router, http } = await setup();
    http.expectOne('/api/v1/daily-entry/2026-03-31').flush(entry());
    await fixture.whenStable();
    fixture.detectChanges();

    const find = fixture.nativeElement.querySelector('input[name="find-dog"]') as HTMLInputElement;
    find.value = 'Aurora';
    find.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    (fixture.nativeElement.querySelector('.find-dog') as HTMLFormElement).dispatchEvent(
      new Event('submit'),
    );
    await new Promise((resolve) => setTimeout(resolve, 0));
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('#daily-dog-aurora-id').classList).toContain(
      'highlighted',
    );

    (fixture.nativeElement.querySelector('[aria-label="Previous day"]') as HTMLButtonElement).click();
    await fixture.whenStable();
    fixture.detectChanges();
    http.expectOne('/api/v1/daily-entry/2026-03-30').flush(
      entry({ selected_date: '2026-03-30', sessions: [] }),
    );
    await fixture.whenStable();
    fixture.detectChanges();
    expect(router.url).toContain('date=2026-03-30');
  });

  it('reviews planned actual work before recording and offers persisted undo', async () => {
    const notRecorded = entry({
      sessions: [],
      planned_activities: [
        {
          ...entry().planned_activities[0],
          actual_status: 'not_recorded',
          actual_session_id: null,
          deviations: [],
        },
      ],
    });
    const { fixture, http } = await setup();
    http.expectOne('/api/v1/daily-entry/2026-03-31').flush(notRecorded);
    await fixture.whenStable();
    fixture.detectChanges();

    const record = Array.from(
      fixture.nativeElement.querySelectorAll('.plan-actions button') as NodeListOf<HTMLButtonElement>,
    ).find((button) => button.textContent.includes('Record actual'))!;
    record.focus();
    record.click();
    fixture.detectChanges();
    const confirmUrl =
      '/api/v1/daily-entry/2026-03-31/planned-activities/activity-id/confirm';
    http.expectNone(confirmUrl);
    const dialog = fixture.nativeElement.querySelector('[role="dialog"]') as HTMLElement;
    expect(dialog.textContent).toContain('Record completed work?');
    expect(dialog.textContent).toContain('Tuesday, 31 March 2026');
    expect(dialog.textContent).toContain('Training · Forest Loop');
    expect(dialog.textContent).toContain('10 km');
    expect(dialog.textContent).toContain('Atlas, Aurora');
    expect(dialog.textContent).toContain('1 saved team · 2 arranged');

    const confirm = Array.from(
      dialog.querySelectorAll('button') as NodeListOf<HTMLButtonElement>,
    ).find((button) => button.textContent.includes('Confirm and record'))!;
    confirm.click();
    fixture.detectChanges();
    confirm.click();
    const requests = http.match(confirmUrl);
    expect(requests.length).toBe(1);
    expect(requests[0].request.method).toBe('POST');
    expect(confirm.disabled).toBe(true);
    requests[0].flush(entry());
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Actual work recorded');
    expect(fixture.nativeElement.textContent).toContain('Undo recording');

    (fixture.nativeElement.querySelector('#daily-entry-feedback button') as HTMLButtonElement).click();
    const undo = http.expectOne(
      '/api/v1/daily-entry/2026-03-31/sessions/session-id?expected_revision=1',
    );
    expect(undo.request.method).toBe('DELETE');
    undo.flush(notRecorded);
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Recording undone');
    expect(fixture.nativeElement.textContent).toContain('Not recorded');
  });

  it('cancels planned recording without a write and restores trigger focus', async () => {
    const notRecorded = entry({
      sessions: [],
      planned_activities: [
        {
          ...entry().planned_activities[0],
          actual_status: 'not_recorded',
          actual_session_id: null,
          deviations: [],
        },
      ],
    });
    const { fixture, http } = await setup();
    http.expectOne('/api/v1/daily-entry/2026-03-31').flush(notRecorded);
    await fixture.whenStable();
    fixture.detectChanges();
    const record = fixture.nativeElement.querySelector(
      '.plan-actions .primary',
    ) as HTMLButtonElement;
    record.focus();
    record.click();
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    http.expectNone(
      '/api/v1/daily-entry/2026-03-31/planned-activities/activity-id/confirm',
    );
    const cancel = Array.from(
      fixture.nativeElement.querySelectorAll('[role="dialog"] button') as NodeListOf<HTMLButtonElement>,
    ).find((button) => button.textContent.includes('Cancel'))!;
    expect(document.activeElement).toBe(cancel);
    cancel.click();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="dialog"]')).toBeNull();
    expect(document.activeElement).toBe(record);

    record.click();
    fixture.detectChanges();
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="dialog"]')).toBeNull();
    http.expectNone(
      '/api/v1/daily-entry/2026-03-31/planned-activities/activity-id/confirm',
    );
  });

  it('keeps the review open with a retryable error when recording fails', async () => {
    const notRecorded = entry({
      sessions: [],
      planned_activities: [
        {
          ...entry().planned_activities[0],
          actual_status: 'not_recorded',
          actual_session_id: null,
          deviations: [],
        },
      ],
    });
    const { fixture, http } = await setup();
    http.expectOne('/api/v1/daily-entry/2026-03-31').flush(notRecorded);
    await fixture.whenStable();
    fixture.detectChanges();
    (fixture.nativeElement.querySelector('.plan-actions .primary') as HTMLButtonElement).click();
    fixture.detectChanges();
    const confirm = Array.from(
      fixture.nativeElement.querySelectorAll('[role="dialog"] button') as NodeListOf<HTMLButtonElement>,
    ).find((button) => button.textContent.includes('Confirm and record'))!;
    confirm.click();
    http
      .expectOne('/api/v1/daily-entry/2026-03-31/planned-activities/activity-id/confirm')
      .flush(
        { detail: { code: 'dog_not_eligible', message: 'Atlas is no longer eligible.' } },
        { status: 422, statusText: 'Unprocessable Entity' },
      );
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="dialog"]')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('[role="alert"]').textContent).toContain(
      'no longer eligible',
    );
    expect(confirm.disabled).toBe(false);
    expect(fixture.nativeElement.textContent).not.toContain('Actual work recorded');
  });

  it('adds a manual session with daily-km context and ineligibility reason', async () => {
    const { fixture, http } = await setup();
    http.expectOne('/api/v1/daily-entry/2026-03-31').flush(entry({ sessions: [] }));
    await fixture.whenStable();
    fixture.detectChanges();
    (fixture.nativeElement.querySelector('.actual-section .primary') as HTMLButtonElement).click();
    fixture.detectChanges();
    http
      .expectOne('/api/v1/daily-entry/2026-03-31/eligible-dogs?distance_km=5')
      .flush(eligibility);
    await fixture.whenStable();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Today actual: 20 km');
    const junior = fixture.nativeElement.querySelector(
      'input[name="actual-dog-sanchez-id"]',
    ) as HTMLInputElement;
    expect(junior.disabled).toBe(true);
    expect(junior.closest('.candidate-row')?.textContent).toContain('Junior');
    (fixture.nativeElement.querySelector('input[name="actual-dog-atlas-id"]') as HTMLInputElement).click();
    fixture.detectChanges();
    (fixture.nativeElement.querySelector('.actual-dialog form') as HTMLFormElement).dispatchEvent(
      new Event('submit'),
    );
    const save = http.expectOne('/api/v1/daily-entry/2026-03-31/sessions');
    expect(save.request.body.participants[0].dog_id).toBe('atlas-id');
    expect(save.request.body.distance_km).toBe(5);
    save.flush(entry());
  });

  it('reopens positioned actual for replacement and exposes server validation', async () => {
    const { fixture, http } = await setup();
    http.expectOne('/api/v1/daily-entry/2026-03-31').flush(entry());
    await fixture.whenStable();
    fixture.detectChanges();
    (fixture.nativeElement.querySelector('.session-actions .secondary') as HTMLButtonElement).click();
    fixture.detectChanges();
    http
      .expectOne(
        '/api/v1/daily-entry/2026-03-31/eligible-dogs?distance_km=10&exclude_session_id=session-id',
      )
      .flush({ ...eligibility, distance_km: 10 });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Lead · Left');
    (fixture.nativeElement.querySelector('.actual-dialog form') as HTMLFormElement).dispatchEvent(
      new Event('submit'),
    );
    http.expectOne('/api/v1/daily-entry/2026-03-31/sessions/session-id').flush(
      { detail: { code: 'dog_not_eligible', message: 'Atlas would exceed 30 km.' } },
      { status: 422, statusText: 'Unprocessable Entity' },
    );
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.form-error').textContent).toContain('30 km');
    expect(fixture.nativeElement.querySelector('[role="dialog"]')).not.toBeNull();
  });

  it('requires confirmation before deleting actual work', async () => {
    const { fixture, http } = await setup();
    http.expectOne('/api/v1/daily-entry/2026-03-31').flush(entry());
    await fixture.whenStable();
    fixture.detectChanges();
    (fixture.nativeElement.querySelector('.session-actions .danger-text') as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Revert recorded work?');
    expect(fixture.nativeElement.textContent).toContain('plan will return to Not recorded');
    (fixture.nativeElement.querySelector('.delete-confirm .danger') as HTMLButtonElement).click();
    const deletion = http.expectOne(
      '/api/v1/daily-entry/2026-03-31/sessions/session-id?expected_revision=1',
    );
    expect(deletion.request.method).toBe('DELETE');
    deletion.flush(entry({ sessions: [] }));
  });

  it('keeps actual work visible and correction retryable when reversal fails', async () => {
    const { fixture, http } = await setup();
    http.expectOne('/api/v1/daily-entry/2026-03-31').flush(entry());
    await fixture.whenStable();
    fixture.detectChanges();
    (fixture.nativeElement.querySelector('.session-actions .danger-text') as HTMLButtonElement).click();
    fixture.detectChanges();
    (fixture.nativeElement.querySelector('.delete-confirm .danger') as HTMLButtonElement).click();
    http
      .expectOne('/api/v1/daily-entry/2026-03-31/sessions/session-id?expected_revision=1')
      .flush(
        { detail: { code: 'actual_changed', message: 'This actual session changed.' } },
        { status: 409, statusText: 'Conflict' },
      );
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.session-card').textContent).toContain(
      'Forest Loop',
    );
    expect(fixture.nativeElement.querySelector('.message.error').textContent).toContain(
      'session changed',
    );
    expect(fixture.nativeElement.querySelector('.delete-confirm .danger').disabled).toBe(false);
  });
});
