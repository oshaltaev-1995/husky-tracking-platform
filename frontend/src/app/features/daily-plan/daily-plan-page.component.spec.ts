import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';

import {
  DailyPlan,
  Eligibility,
  PlannedActivity,
} from '../../core/api/daily-plans.models';
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

async function setup(url = '/daily') {
  await TestBed.configureTestingModule({
    imports: [DailyPlanPageComponent],
    providers: [
      provideHttpClient(),
      provideHttpClientTesting(),
      provideRouter([{ path: 'daily', component: DailyPlanPageComponent }]),
    ],
  }).compileComponents();
  const router = TestBed.inject(Router);
  await router.navigateByUrl(url);
  const fixture = TestBed.createComponent(DailyPlanPageComponent);
  fixture.detectChanges();
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
    request.flush(plan([{ ...activity, distance_km: 5, title: 'Training Loop' }], 1));
    await fixture.whenStable();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Activity added');
    expect(fixture.nativeElement.textContent).toContain('Atlas');
    expect(fixture.nativeElement.querySelector('[role="dialog"]')).toBeNull();
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
    patch.flush(plan([activity], 4));
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
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No activities planned');
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
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.team-handoff a')).toBeNull();
  });
});
