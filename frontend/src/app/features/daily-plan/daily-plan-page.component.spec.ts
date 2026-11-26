import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { By } from '@angular/platform-browser';

import {
  DailyPlan,
  Eligibility,
  PlannedActivity,
  TrainingDayProposal,
} from '../../core/api/daily-plans.models';
import { DemoSessionService } from '../../core/api/demo-session.service';
import { OperationsReview } from '../../core/api/operations.models';
import { OperationsReviewComponent } from './operations-review.component';
import { DailyPlanPageComponent } from './daily-plan-page.component';

const atlas = {
  id: 'atlas-id',
  name: 'Atlas',
  housing_code: 'A1-01',
  dog_class: 'standard',
  availability: 'available',
};

const activity: PlannedActivity = {
  id: 'activity-id',
  activity_type: 'training',
  sequence: 1,
  start_time: '09:15:00',
  title: 'Forest Loop',
  distance_km: 10,
  notes: 'Check trail surface.',
  participants: [atlas],
  team_count: 0,
  arranged_dog_count: 0,
};

function plan(activities: PlannedActivity[] = [], revision: number | null = null): DailyPlan {
  return {
    selected_date: '2026-03-31',
    season_start: '2025-12-01',
    season_end: '2026-03-31',
    reference_date: '2026-03-31',
    minimum_team_size: 4,
    exists: activities.length > 0,
    id: activities.length ? 'plan-id' : null,
    revision,
    notes: null,
    activities,
  };
}

const eligibility: Eligibility = {
  selected_date: '2026-03-31',
  activity_type: 'training',
  distance_km: 5,
  max_daily_training_km: 30,
  dogs: [
    { ...atlas, eligible: true, reasons: [], planned_training_km: 20 },
    {
      id: 'nala-id',
      name: 'Nala',
      housing_code: 'B1-03',
      dog_class: 'training',
      availability: 'available',
      eligible: true,
      reasons: [],
      planned_training_km: 5,
    },
    {
      id: 'sanchez-id',
      name: 'Sanchez',
      housing_code: 'B2-03',
      dog_class: 'junior',
      availability: 'available',
      eligible: false,
      reasons: ['Junior'],
      planned_training_km: 0,
    },
  ],
};

function trainingProposal(): TrainingDayProposal {
  return {
    date: '2026-03-29', preset_version: 'training-day-v1', available: true, unavailable_reason: null,
    activities: [
      ['09:00:00', '10:00:00'], ['10:30:00', '11:30:00'], ['12:30:00', '13:30:00'], ['14:00:00', '15:00:00'],
    ].map(([start_time, suggested_end_time], index) => ({ sequence: index + 1, start_time, suggested_end_time, title: `Group ${index + 1}`, distance_km: 5 })),
    participants: Array.from({ length: 16 }, (_, index) => ({ ...atlas, id: `review-dog-${index}`, name: `Synthetic Dog ${index + 1}`, capabilities: ['lead', 'team', 'wheel'] })),
    unique_dogs: 16, planned_participations: 64, planned_dog_km: 320, planned_km_per_dog: 20,
    precondition: 'opaque-reviewed-precondition',
  };
}

function button(fixture: ComponentFixture<DailyPlanPageComponent>, label: string): HTMLButtonElement {
  const found = Array.from(fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>)
    .find((element) => element.textContent.trim() === label);
  if (!found) throw new Error(`Missing test button: ${label}`);
  return found;
}

function examplePlan(): DailyPlan {
  const example = trainingProposal();
  return { ...plan(), exists: true, id: 'example-plan', revision: 1, selected_date: example.date,
    activities: example.activities.map((item) => ({ ...activity, id: `example-${item.sequence}`, sequence: item.sequence,
      start_time: item.start_time, title: item.title, distance_km: 5, participants: example.participants, team_count: 0, arranged_dog_count: 0 })) };
}

function savedVersion(fixture: ComponentFixture<DailyPlanPageComponent>): number {
  const review = fixture.debugElement.query(By.directive(OperationsReviewComponent)).componentInstance as OperationsReviewComponent;
  return review.savedContextVersion()();
}

function emptyReview(): OperationsReview {
  return {
    provenance: 'ai_selected_server_observations',
    snapshot_id: '00000000-0000-0000-0000-000000000001', selected_date: '2026-03-31',
    captured_at: '2026-11-22T06:00:00Z', explanation: 'The saved day has no plan.',
    presentation: { status: 'ready', message: null, segments: [{ text: 'The saved day has no plan.', entity: null, path: null }] },
    summary: { plan_exists: false, activity_count: 0, selected_unique_dogs: 0,
      selected_participations: 0, activities: [], omitted_activities: 0,
      actual: { sessions: 0, dogs_worked: 0, dog_starts: 0, dog_km: 0 } },
    finding_groups: [], facts: [], findings: [], evidence: [], links: [], checked_rules: [],
    status_counts: { passed: 0, violations: 0, attention: 0, unverified: 0 }, omitted_findings: 0,
    provider: 'groq', model: 'openai/gpt-oss-20b', fallback: false, http_calls: 2,
    tool_calls: 1, trace: [{ tool_name: 'validate_day', provider: 'groq', outcome: 'ok', elapsed_ms: 1 }],
    usage: { known_prompt_tokens: null, known_completion_tokens: null, incomplete: true },
  };
}

async function setup(url = '/daily', reviewEnabled = false) {
  await TestBed.configureTestingModule({
    imports: [DailyPlanPageComponent],
    providers: [
      provideHttpClient(),
      provideHttpClientTesting(),
      provideRouter([{ path: 'daily', component: DailyPlanPageComponent }]),
    ],
  }).compileComponents();
  const router = TestBed.inject(Router);
  if (reviewEnabled) TestBed.inject(DemoSessionService).session.set({
    active: true, expires_at: new Date(Date.now() + 3_600_000).toISOString(),
    ttl_hours: 1, ttl_seconds: 3600, created: false, replaced_expired: false,
  });
  await router.navigateByUrl(url);
  const fixture = TestBed.createComponent(DailyPlanPageComponent);
  fixture.detectChanges();
  TestBed.inject(HttpTestingController).expectOne('/api/v1/operations/capabilities').flush({
    enabled: reviewEnabled, external_processing: reviewEnabled, providers: reviewEnabled ? ['groq'] : [], selected_scenario: 'review_operations',
    season_start: '2025-12-01', season_end: '2026-03-31',
  });
  return { fixture, router, http: TestBed.inject(HttpTestingController) };
}

describe('DailyPlanPageComponent', () => {
  afterEach(() => TestBed.inject(HttpTestingController).verify());

  it('renders a useful lazy empty day and opens the participant editor', async () => {
    const { fixture, http } = await setup();
    expect(fixture.nativeElement.textContent).toContain('Loading this day’s plan');
    http.expectOne('/api/v1/daily-plans/2026-03-31').flush(plan());
    await fixture.whenStable();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('No activities planned');
    expect(fixture.nativeElement.querySelector('ht-operations-review')?.textContent).toContain('31 March 2026');
    expect(fixture.nativeElement.querySelector('ht-operations-review')?.textContent).toContain('AI review is not enabled');
    http.expectNone('/api/v1/operations/review');
    (fixture.nativeElement.querySelector('.activities-heading .primary') as HTMLButtonElement).click();
    fixture.detectChanges();
    http
      .expectOne(
        '/api/v1/daily-plans/2026-03-31/eligible-dogs?activity_type=training&distance_km=5',
      )
      .flush(eligibility);
    await fixture.whenStable();
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('[role="dialog"]')).not.toBeNull();
    expect(fixture.nativeElement.textContent).toContain('20 km planned');
    const sanchez = fixture.nativeElement.querySelector(
      'input[name="dog-sanchez-id"]',
    ) as HTMLInputElement;
    expect(sanchez.disabled).toBe(true);
    expect(sanchez.closest('.candidate-row')?.textContent).toContain('Junior');
  });

  it('creates a 5 km Training activity with selected participants', async () => {
    const { fixture, http } = await setup();
    http.expectOne('/api/v1/daily-plans/2026-03-31').flush(plan());
    await fixture.whenStable();
    fixture.detectChanges();
    (fixture.nativeElement.querySelector('.activities-heading .primary') as HTMLButtonElement).click();
    fixture.detectChanges();
    http
      .expectOne(
        '/api/v1/daily-plans/2026-03-31/eligible-dogs?activity_type=training&distance_km=5',
      )
      .flush(eligibility);
    await fixture.whenStable();
    fixture.detectChanges();

    const atlasCheckbox = fixture.nativeElement.querySelector(
      'input[name="dog-atlas-id"]',
    ) as HTMLInputElement;
    atlasCheckbox.click();
    fixture.detectChanges();
    (fixture.nativeElement.querySelector('.activity-dialog form') as HTMLFormElement).dispatchEvent(
      new Event('submit'),
    );
    const request = http.expectOne('/api/v1/daily-plans/2026-03-31/activities');
    expect(request.request.method).toBe('POST');
    expect(request.request.body.activity_type).toBe('training');
    expect(request.request.body.distance_km).toBe(5);
    expect(request.request.body.participant_ids).toEqual(['atlas-id']);
    expect(request.request.body.expected_revision).toBeNull();
    const previousVersion = savedVersion(fixture);
    request.flush(plan([{ ...activity, distance_km: 5, title: 'Training Loop' }], 1));
    expect(savedVersion(fixture)).toBe(previousVersion + 1);
    await fixture.whenStable();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Activity added');
    expect(fixture.nativeElement.textContent).toContain('Atlas');
    expect(fixture.nativeElement.querySelector('[role="dialog"]')).toBeNull();
  });

  it('keeps a completed review while an editor is opened/cancelled, then invalidates it only after the activity is saved', async () => {
    const { fixture, http } = await setup('/daily', true);
    http.expectOne('/api/v1/daily-plans/2026-03-31').flush(plan());
    await fixture.whenStable(); fixture.detectChanges();
    button(fixture, 'Review this day').click();
    http.expectOne('/api/v1/operations/review').flush(emptyReview());
    await fixture.whenStable(); fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('AI-assisted review ready.');
    expect(fixture.nativeElement.textContent).toContain('No saved plan for this date.');
    const previousVersion = savedVersion(fixture);

    async function openEditor() {
      button(fixture, 'Add first activity').click(); fixture.detectChanges();
      http.expectOne('/api/v1/daily-plans/2026-03-31/eligible-dogs?activity_type=training&distance_km=5').flush(eligibility);
      await fixture.whenStable(); fixture.detectChanges();
    }
    await openEditor();
    expect(savedVersion(fixture)).toBe(previousVersion);
    expect(fixture.nativeElement.querySelector('.review-result')).not.toBeNull();
    button(fixture, 'Cancel').click(); fixture.detectChanges();
    expect(savedVersion(fixture)).toBe(previousVersion);
    expect(fixture.nativeElement.textContent).not.toContain('The saved day changed after this review.');
    expect(fixture.nativeElement.textContent).toContain('AI-assisted review ready.');

    await openEditor();
    (fixture.nativeElement.querySelector('input[name="dog-atlas-id"]') as HTMLInputElement).click();
    fixture.detectChanges();
    (fixture.nativeElement.querySelector('.activity-dialog form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    const save = http.expectOne('/api/v1/daily-plans/2026-03-31/activities');
    expect(savedVersion(fixture)).toBe(previousVersion);
    save.flush(plan([{ ...activity, distance_km: 5 }], 1));
    // This reads the shared signal before input rebinding/effect cleanup can run.
    expect(savedVersion(fixture)).toBe(previousVersion + 1);
    await fixture.whenStable(); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.review-result')).toBeNull();
    expect(fixture.nativeElement.textContent).not.toContain('AI-assisted review ready.');
    expect(fixture.nativeElement.textContent).not.toContain('No saved plan for this date.');
    expect(fixture.nativeElement.textContent).toContain('The saved day changed after this review. Start a new review to include your latest changes.');
    expect(button(fixture, 'Start a new review').disabled).toBe(false);
    http.expectNone('/api/v1/operations/review');
  });

  it('advances the saved context when a first note creates a plan, but not while editing or after a failed save', async () => {
    const { fixture, http } = await setup();
    http.expectOne('/api/v1/daily-plans/2026-03-31').flush(plan());
    await fixture.whenStable(); fixture.detectChanges();
    const previousVersion = savedVersion(fixture);
    const note = fixture.nativeElement.querySelector('.daily-note textarea') as HTMLTextAreaElement;
    note.value = 'Synthetic note'; note.dispatchEvent(new Event('input'));
    await fixture.whenStable(); fixture.detectChanges();
    expect(savedVersion(fixture)).toBe(previousVersion);
    button(fixture, 'Save note').click();
    http.expectOne('/api/v1/daily-plans/2026-03-31').flush(
      { detail: 'The note could not be saved.' }, { status: 503, statusText: 'Unavailable' },
    );
    await fixture.whenStable(); fixture.detectChanges();
    expect(savedVersion(fixture)).toBe(previousVersion);
    button(fixture, 'Save note').click();
    const save = http.expectOne('/api/v1/daily-plans/2026-03-31');
    expect(save.request.body.expected_revision).toBeNull();
    save.flush({ ...plan(), exists: true, id: 'notes-plan', revision: 1, notes: 'Synthetic note' });
    expect(savedVersion(fixture)).toBe(previousVersion + 1);
    await fixture.whenStable(); fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Daily note saved.');
    http.expectNone('/api/v1/operations/review');
  });

  it('retains accepted context across an unchanged reload and advances it when the reload accepts a newer revision', async () => {
    const { fixture, http } = await setup();
    http.expectOne('/api/v1/daily-plans/2026-03-31').flush(plan([activity], 1));
    await fixture.whenStable(); fixture.detectChanges();
    const previousVersion = savedVersion(fixture);
    const page = fixture.componentInstance as unknown as { retry(): void };
    page.retry(); fixture.detectChanges();
    expect(savedVersion(fixture)).toBe(previousVersion);
    http.expectOne('/api/v1/daily-plans/2026-03-31').flush(plan([activity], 1));
    await fixture.whenStable(); fixture.detectChanges();
    expect(savedVersion(fixture)).toBe(previousVersion);
    page.retry(); fixture.detectChanges();
    http.expectOne('/api/v1/daily-plans/2026-03-31').flush(plan([{ ...activity, distance_km: 5 }], 2));
    expect(savedVersion(fixture)).toBe(previousVersion + 1);
    await fixture.whenStable(); fixture.detectChanges();
    http.expectNone('/api/v1/operations/review');
  });

  it('keeps a small Training plan valid without offering an impossible Build teams action', async () => {
    const small = { ...activity, participants: [atlas, { ...atlas, id: 'daisy-id', name: 'Daisy' }] };
    const { fixture, http } = await setup();
    http.expectOne('/api/v1/daily-plans/2026-03-31').flush(plan([small], 1));
    await fixture.whenStable();
    fixture.detectChanges();

    const handoff = fixture.nativeElement.querySelector('.team-handoff') as HTMLElement;
    expect(handoff.textContent).toContain('at least 4 selected dogs');
    expect(handoff.querySelector('a')).toBeNull();
    (handoff.querySelector('button') as HTMLButtonElement).click();
    fixture.detectChanges();
    http.expectOne('/api/v1/daily-plans/2026-03-31/eligible-dogs?activity_type=training&distance_km=10&exclude_activity_id=activity-id')
      .flush({ ...eligibility, distance_km: 10 });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="dialog"]')).not.toBeNull();
  });

  for (const size of [4, 16]) {
    it(`offers Build teams for a ${size}-dog pool`, async () => {
      const participants = Array.from({ length: size }, (_, index) => ({
        ...atlas,
        id: `dog-${index}`,
        name: `Dog ${index}`,
      }));
      const { fixture, http } = await setup();
      http.expectOne('/api/v1/daily-plans/2026-03-31').flush(
        plan([{ ...activity, participants }], 1),
      );
      await fixture.whenStable();
      fixture.detectChanges();
      expect((fixture.nativeElement.querySelector('.team-handoff a') as HTMLAnchorElement).textContent)
        .toContain('Build teams');
    });
  }

  it('changes date with previous-day navigation and reloads the plan', async () => {
    const { fixture, router, http } = await setup();
    http.expectOne('/api/v1/daily-plans/2026-03-31').flush(plan());
    await fixture.whenStable();
    fixture.detectChanges();

    (fixture.nativeElement.querySelector('[aria-label="Previous day"]') as HTMLButtonElement).click();
    await fixture.whenStable();
    fixture.detectChanges();
    http.expectOne('/api/v1/daily-plans/2026-03-30').flush({
      ...plan(),
      selected_date: '2026-03-30',
    });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(router.url).toContain('date=2026-03-30');
    expect(fixture.nativeElement.textContent).toContain('Monday, 30 March 2026');
  });

  it('edits and deletes an activity with revision-aware requests', async () => {
    const { fixture, http } = await setup();
    http.expectOne('/api/v1/daily-plans/2026-03-31').flush(plan([activity], 3));
    await fixture.whenStable();
    fixture.detectChanges();

    const editButton = Array.from(
      fixture.nativeElement.querySelectorAll('.activity-actions button') as NodeListOf<HTMLButtonElement>,
    ).find((button) => button.textContent.trim() === 'Edit') as HTMLButtonElement;
    editButton.click();
    fixture.detectChanges();
    http
      .expectOne(
        '/api/v1/daily-plans/2026-03-31/eligible-dogs?activity_type=training&distance_km=10&exclude_activity_id=activity-id',
      )
      .flush({ ...eligibility, distance_km: 10 });
    await fixture.whenStable();
    fixture.detectChanges();
    (fixture.nativeElement.querySelector('.activity-dialog form') as HTMLFormElement).dispatchEvent(
      new Event('submit'),
    );
    const patch = http.expectOne('/api/v1/daily-plans/2026-03-31/activities/activity-id');
    expect(patch.request.method).toBe('PATCH');
    expect(patch.request.body.expected_revision).toBe(3);
    const previousVersion = savedVersion(fixture);
    patch.flush(plan([activity], 4));
    expect(savedVersion(fixture)).toBe(previousVersion + 1);
    await fixture.whenStable();
    fixture.detectChanges();

    (fixture.nativeElement.querySelector('.activity-actions .remove') as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Remove?');
    (fixture.nativeElement.querySelector('.delete-confirm .danger') as HTMLButtonElement).click();
    const deletion = http.expectOne(
      '/api/v1/daily-plans/2026-03-31/activities/activity-id?expected_revision=4',
    );
    expect(deletion.request.method).toBe('DELETE');
    deletion.flush(plan());
    expect(savedVersion(fixture)).toBe(previousVersion + 2);
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No activities planned');
  });

  it('publishes a newer saved context for a successfully reordered activity without starting another review', async () => {
    const other = { ...activity, id: 'other-activity', title: 'Second loop', sequence: 2 };
    const { fixture, http } = await setup();
    http.expectOne('/api/v1/daily-plans/2026-03-31').flush(plan([activity, other], 3));
    await fixture.whenStable(); fixture.detectChanges();
    const previousVersion = savedVersion(fixture);
    (fixture.nativeElement.querySelector('[aria-label="Move Forest Loop later"]') as HTMLButtonElement).click();
    const move = http.expectOne('/api/v1/daily-plans/2026-03-31/activities/activity-id/move');
    expect(move.request.body).toEqual({ direction: 'down', expected_revision: 3 });
    expect(savedVersion(fixture)).toBe(previousVersion);
    move.flush(plan([{ ...other, sequence: 1 }, { ...activity, sequence: 2 }], 4));
    expect(savedVersion(fixture)).toBe(previousVersion + 1);
    await fixture.whenStable(); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.activity-card h3').textContent).toContain('Second loop');
    http.expectNone('/api/v1/operations/review');
  });

  it('displays a server validation error without closing the editor', async () => {
    const { fixture, http } = await setup();
    http.expectOne('/api/v1/daily-plans/2026-03-31').flush(plan());
    await fixture.whenStable();
    fixture.detectChanges();
    (fixture.nativeElement.querySelector('.activities-heading .primary') as HTMLButtonElement).click();
    fixture.detectChanges();
    http
      .expectOne(
        '/api/v1/daily-plans/2026-03-31/eligible-dogs?activity_type=training&distance_km=5',
      )
      .flush(eligibility);
    await fixture.whenStable();
    fixture.detectChanges();
    (fixture.nativeElement.querySelector('input[name="dog-atlas-id"]') as HTMLInputElement).click();
    fixture.detectChanges();
    (fixture.nativeElement.querySelector('.activity-dialog form') as HTMLFormElement).dispatchEvent(
      new Event('submit'),
    );
    http.expectOne('/api/v1/daily-plans/2026-03-31/activities').flush(
      { detail: { code: 'dog_not_eligible', message: 'Atlas has reached 30 km.' } },
      { status: 422, statusText: 'Unprocessable Entity' },
    );
    await fixture.whenStable();
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('.form-error').textContent).toContain('30 km');
    expect(fixture.nativeElement.querySelector('[role="dialog"]')).not.toBeNull();
  });

  it('links Training to Team Builder and explicitly confirms lineup clearing', async () => {
    const arranged = { ...activity, team_count: 1, arranged_dog_count: 8 };
    const { fixture, http } = await setup();
    http.expectOne('/api/v1/daily-plans/2026-03-31').flush(plan([arranged], 3));
    await fixture.whenStable();
    fixture.detectChanges();
    const teamLink = fixture.nativeElement.querySelector('.team-handoff a') as HTMLAnchorElement;
    const previousVersion = savedVersion(fixture);
    expect(teamLink.textContent).toContain('View teams');
    expect(teamLink.getAttribute('href')).toContain(
      '/demo/daily/2026-03-31/activities/activity-id/teams',
    );

    const editButton = Array.from(
      fixture.nativeElement.querySelectorAll('.activity-actions button') as NodeListOf<HTMLButtonElement>,
    ).find((button) => button.textContent.trim() === 'Edit')!;
    editButton.click();
    fixture.detectChanges();
    http
      .expectOne(
        '/api/v1/daily-plans/2026-03-31/eligible-dogs?activity_type=training&distance_km=10&exclude_activity_id=activity-id',
      )
      .flush({ ...eligibility, distance_km: 10 });
    await fixture.whenStable();
    fixture.detectChanges();
    (fixture.nativeElement.querySelector('.activity-dialog form') as HTMLFormElement).dispatchEvent(
      new Event('submit'),
    );
    http.expectOne('/api/v1/daily-plans/2026-03-31/activities/activity-id').flush(
      {
        detail: {
          code: 'saved_teams_require_clear',
          message: 'Changing the participant pool will clear the saved team lineup.',
        },
      },
      { status: 409, statusText: 'Conflict' },
    );
    await fixture.whenStable();
    fixture.detectChanges();
    expect(savedVersion(fixture)).toBe(previousVersion);
    expect(fixture.nativeElement.textContent).toContain('Clear the saved lineup?');
    const confirm = Array.from(
      fixture.nativeElement.querySelectorAll('.lineup-clear-warning button') as NodeListOf<HTMLButtonElement>,
    ).find((button) => button.textContent.includes('Clear teams'))!;
    confirm.click();
    const cleared = http.expectOne(
      '/api/v1/daily-plans/2026-03-31/activities/activity-id',
    );
    expect(cleared.request.body.clear_saved_teams).toBe(true);
    cleared.flush(plan([{ ...activity, team_count: 0, arranged_dog_count: 0 }], 4));
    expect(savedVersion(fixture)).toBe(previousVersion + 1);
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.team-handoff a')).toBeNull();
  });

  async function preparedTrainingDay() {
    const context = await setup();
    context.http.expectOne('/api/v1/daily-plans/2026-03-31').flush(plan());
    await context.fixture.whenStable();
    context.fixture.detectChanges();
    button(context.fixture, 'Try a training day').click();
    context.fixture.detectChanges();
    context.http.expectOne('/api/v1/training-day-example').flush(trainingProposal());
    await context.fixture.whenStable();
    context.fixture.detectChanges();
    return context;
  }

  it('reviews and cancels the example without changing the selected date or writing a plan', async () => {
    const { fixture, http, router } = await preparedTrainingDay();
    expect(fixture.nativeElement.textContent).toContain('Sunday, 29 March 2026');
    expect(fixture.nativeElement.textContent).not.toContain('Saturday, 28 March');
    expect(fixture.nativeElement.querySelector('.day-identity').textContent).toContain('Tuesday, 31 March 2026');
    expect(fixture.nativeElement.querySelectorAll('.example-pool li').length).toBe(16);
    expect(fixture.nativeElement.textContent).not.toContain('opaque-reviewed-precondition');
    button(fixture, 'Cancel').click();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('ht-training-day-review')).toBeNull();
    expect(router.url).not.toContain('2026-03-29');
    http.expectNone((request) => request.method !== 'GET');
  });

  it('preserves an unsaved note and does not prepare or silently select the example date', async () => {
    const { fixture, http, router } = await setup();
    http.expectOne('/api/v1/daily-plans/2026-03-31').flush(plan());
    await fixture.whenStable();
    fixture.detectChanges();
    const textarea = fixture.nativeElement.querySelector('.daily-note textarea') as HTMLTextAreaElement;
    textarea.value = 'Unsaved synthetic note';
    textarea.dispatchEvent(new Event('input'));
    await fixture.whenStable();
    fixture.detectChanges();
    button(fixture, 'Try a training day').click();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Save or discard the current note');
    expect(textarea.value).toBe('Unsaved synthetic note');
    expect(fixture.nativeElement.querySelector('ht-training-day-review')).toBeNull();
    http.expectNone('/api/v1/training-day-example');
    await router.navigateByUrl('/daily?date=2026-03-29');
    await fixture.whenStable();
    fixture.detectChanges();
    expect(router.url).toContain('date=2026-03-31');
    expect(textarea.value).toBe('Unsaved synthetic note');
    http.expectNone('/api/v1/daily-plans/2026-03-29');
  });

  it('submits one atomic Apply despite rapid confirmation and shows the saved ordinary plan', async () => {
    const { fixture, http, router } = await preparedTrainingDay();
    const apply = button(fixture, 'Apply training day');
    apply.click();
    apply.click();
    const request = http.expectOne('/api/v1/training-day-example/apply');
    expect(request.request.method).toBe('POST');
    const previousVersion = savedVersion(fixture);
    expect(request.request.body).toEqual({
      date: '2026-03-29', preset_version: 'training-day-v1',
      participant_ids: trainingProposal().participants.map((dog) => dog.id), precondition: 'opaque-reviewed-precondition',
    });
    fixture.detectChanges();
    expect(button(fixture, 'Applying…').disabled).toBe(true);
    expect(button(fixture, 'Cancel').disabled).toBe(true);
    request.flush(examplePlan());
    expect(savedVersion(fixture)).toBe(previousVersion + 1);
    await fixture.whenStable();
    fixture.detectChanges();
    expect(router.url).toContain('date=2026-03-29');
    expect(fixture.nativeElement.querySelectorAll('.activity-card').length).toBe(4);
    expect(fixture.nativeElement.querySelectorAll('.team-handoff a').length).toBe(4);
    expect(fixture.nativeElement.textContent).toContain('Teams and actual work are still separate');
    expect(fixture.nativeElement.querySelector('ht-training-day-review')).toBeNull();
    http.expectNone((item) => item.method !== 'GET');
    http.expectNone('/api/v1/daily-plans/2026-03-29');
  });

  it('keeps an occupied date unchanged and opens its current plan only on an explicit action', async () => {
    const { fixture, http, router } = await setup();
    http.expectOne('/api/v1/daily-plans/2026-03-31').flush(plan());
    await fixture.whenStable();
    fixture.detectChanges();
    button(fixture, 'Try a training day').click();
    http.expectOne('/api/v1/training-day-example').flush({ ...trainingProposal(), available: false,
      unavailable_reason: 'This date already has a plan or actual work.', precondition: null, participants: [] });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('already has a plan or actual work');
    expect(fixture.nativeElement.querySelector('ht-training-day-review .primary')).toBeNull();
    expect(router.url).not.toContain('2026-03-29');
    button(fixture, 'Open current day').click();
    http.expectOne('/api/v1/daily-plans/2026-03-29').flush(examplePlan());
    await fixture.whenStable();
    fixture.detectChanges();
    expect(router.url).toContain('date=2026-03-29');
    expect(fixture.nativeElement.querySelectorAll('.activity-card').length).toBe(4);
    http.expectNone((request) => request.method !== 'GET');
  });

  it('shows a definite rejection and requires a fresh explicit review rather than replaying Apply', async () => {
    const { fixture, http } = await preparedTrainingDay();
    button(fixture, 'Apply training day').click();
    http.expectOne('/api/v1/training-day-example/apply').flush({ detail: { code: 'training_day_stale', message: 'This review is stale. Prepare a new proposal.' } }, { status: 409, statusText: 'Conflict' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('This review is stale');
    expect(fixture.nativeElement.querySelector('ht-training-day-review .primary')).toBeNull();
    http.expectNone('/api/v1/training-day-example/apply');
    button(fixture, 'Review again').click();
    http.expectOne('/api/v1/training-day-example').flush({ ...trainingProposal(), precondition: 'new-reviewed-token' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(button(fixture, 'Apply training day').disabled).toBe(false);
    http.expectNone('/api/v1/training-day-example/apply');
  });

  it('explains a preview rate limit in the persistent feedback area without retrying or submitting a plan', async () => {
    const { fixture, http } = await setup();
    http.expectOne('/api/v1/daily-plans/2026-03-31').flush(plan());
    await fixture.whenStable();
    fixture.detectChanges();
    button(fixture, 'Try a training day').click();
    http.expectOne('/api/v1/training-day-example').flush({ detail: 'Rate limited' }, { status: 429, statusText: 'Too Many Requests' });
    await fixture.whenStable();
    fixture.detectChanges();
    const feedback = fixture.nativeElement.querySelector('.training-day-feedback') as HTMLElement;
    expect(feedback.querySelector('[role="alert"]')?.textContent).toContain('Too many training-day requests');
    expect(feedback.textContent).toContain('No plan was submitted');
    expect(fixture.nativeElement.querySelector('.training-day-content').contains(feedback)).toBe(false);
    expect(button(fixture, 'Cancel').disabled).toBe(false);
    expect(button(fixture, 'Review again').disabled).toBe(false);
    expect(fixture.nativeElement.querySelector('ht-training-day-review .primary')).toBeNull();
    http.expectNone('/api/v1/training-day-example');
    http.expectNone('/api/v1/training-day-example/apply');
  });

  it('handles Apply 429 as a definite rejection and requires a fresh review instead of automatically retrying POST', async () => {
    const { fixture, http } = await preparedTrainingDay();
    button(fixture, 'Apply training day').click();
    http.expectOne('/api/v1/training-day-example/apply').flush({ detail: 'Rate limited' }, { status: 429, statusText: 'Too Many Requests' });
    await fixture.whenStable();
    fixture.detectChanges();
    const feedback = fixture.nativeElement.querySelector('.training-day-feedback') as HTMLElement;
    expect(feedback.querySelector('[role="alert"]')?.textContent).toContain('Too many training-day requests');
    expect(feedback.textContent).toContain('Nothing will be retried automatically');
    expect(button(fixture, 'Open current day').disabled).toBe(false);
    expect(button(fixture, 'Review again').disabled).toBe(false);
    expect(fixture.nativeElement.querySelector('ht-training-day-review .primary')).toBeNull();
    http.expectNone('/api/v1/training-day-example/apply');
    button(fixture, 'Review again').click();
    http.expectOne('/api/v1/training-day-example').flush({ ...trainingProposal(), precondition: 'fresh-rate-limit-review' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(button(fixture, 'Apply training day').disabled).toBe(false);
    http.expectNone('/api/v1/training-day-example/apply');
  });

  it('treats a lost Apply response as unknown and reconciles a committed plan by GET without a second POST', async () => {
    const { fixture, http, router } = await preparedTrainingDay();
    button(fixture, 'Apply training day').click();
    http.expectOne('/api/v1/training-day-example/apply').error(new ProgressEvent('error'));
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('The day may already be saved');
    expect(fixture.nativeElement.textContent).not.toContain('nothing was saved');
    expect(fixture.nativeElement.querySelector('ht-training-day-review .primary')).toBeNull();
    button(fixture, 'Check current day').click();
    http.expectOne('/api/v1/daily-plans/2026-03-29').flush(examplePlan());
    await fixture.whenStable();
    fixture.detectChanges();
    expect(router.url).toContain('date=2026-03-29');
    expect(fixture.nativeElement.querySelectorAll('.activity-card').length).toBe(4);
    expect(fixture.nativeElement.textContent).toContain('no save request was repeated');
    http.expectNone('/api/v1/training-day-example/apply');
  });

  it('does not interpret an empty reconciliation read as proof of rollback or automatically resubmit', async () => {
    const { fixture, http } = await preparedTrainingDay();
    button(fixture, 'Apply training day').click();
    http.expectOne('/api/v1/training-day-example/apply').flush({}, { status: 504, statusText: 'Gateway Timeout' });
    await fixture.whenStable();
    fixture.detectChanges();
    button(fixture, 'Check current day').click();
    http.expectOne('/api/v1/daily-plans/2026-03-29').flush({ ...plan(), selected_date: '2026-03-29' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('does not prove an earlier request has stopped');
    expect(fixture.nativeElement.querySelector('ht-training-day-review .primary')).toBeNull();
    http.expectNone('/api/v1/training-day-example/apply');
    button(fixture, 'Review again').click();
    http.expectOne('/api/v1/training-day-example').flush(trainingProposal());
    await fixture.whenStable();
    fixture.detectChanges();
    expect(button(fixture, 'Apply training day')).toBeTruthy();
    http.expectNone('/api/v1/training-day-example/apply');
  });

  it('invalidates a review on Reset or session replacement and never reuses its old authorization', async () => {
    const { fixture, http } = await preparedTrainingDay();
    const session = TestBed.inject(DemoSessionService);
    session.resetStarted$.next();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('ht-training-day-review')).toBeNull();
    session.resetCompleted$.next();
    http.expectOne('/api/v1/daily-plans/2026-03-31').flush(plan());
    await fixture.whenStable();
    fixture.detectChanges();
    button(fixture, 'Try a training day').click();
    http.expectOne('/api/v1/training-day-example').flush(trainingProposal());
    await fixture.whenStable();
    fixture.detectChanges();
    session.replaced$.next();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('ht-training-day-review')).toBeNull();
    expect(fixture.nativeElement.textContent).toContain('Your demo session changed');
    http.expectNone('/api/v1/training-day-example/apply');
  });

  it('detaches an in-flight Apply on date change without accepting its old UI result or replaying it', async () => {
    const { fixture, http, router } = await preparedTrainingDay();
    button(fixture, 'Apply training day').click();
    const pending = http.expectOne('/api/v1/training-day-example/apply');
    await router.navigateByUrl('/daily?date=2026-03-30');
    await fixture.whenStable();
    fixture.detectChanges();
    expect(pending.cancelled).toBe(true);
    http.expectOne('/api/v1/daily-plans/2026-03-30').flush({ ...plan(), selected_date: '2026-03-30' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('ht-training-day-review')).toBeNull();
    expect(fixture.nativeElement.querySelector('.day-identity').textContent).toContain('Monday, 30 March 2026');
    expect(fixture.nativeElement.textContent).toContain('Changing the view cannot cancel it');
    http.expectNone('/api/v1/training-day-example/apply');
  });

  it('invalidates the review when the known session has expired', async () => {
    const { fixture, http } = await preparedTrainingDay();
    TestBed.inject(DemoSessionService).session.set({ active: true, expires_at: '2000-01-01T00:00:00Z', ttl_hours: 24, ttl_seconds: 86400, created: false, replaced_expired: false });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('ht-training-day-review')).toBeNull();
    expect(fixture.nativeElement.textContent).toContain('Your demo session expired');
    button(fixture, 'Try a training day').click();
    http.expectNone('/api/v1/training-day-example');
    http.expectNone('/api/v1/training-day-example/apply');
  });

  it('closes a pending proposal after destroy without submitting it', async () => {
    const { fixture, http } = await setup();
    http.expectOne('/api/v1/daily-plans/2026-03-31').flush(plan());
    await fixture.whenStable();
    fixture.detectChanges();
    button(fixture, 'Try a training day').click();
    const pending = http.expectOne('/api/v1/training-day-example');
    fixture.destroy();
    expect(pending.cancelled).toBe(true);
    expect(document.querySelector('ht-training-day-review')).toBeNull();
    http.expectNone('/api/v1/training-day-example/apply');
  });
});
