import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { DashboardResponse } from '../../core/api/dashboard.models';
import { DashboardPageComponent } from './dashboard-page.component';

const dashboard: DashboardResponse = {
  context: {
    selected_date: '2026-03-31',
    season_start: '2025-12-01',
    season_end: '2026-03-31',
    reference_date: '2026-03-31',
    season_label: 'Winter 2025–2026',
  },
  population: {
    active_dogs: 50,
    class_counts: { puppy: 10, junior: 6, training: 8, standard: 26 },
    available_dogs: 46,
    unavailable_dogs: 4,
    availability_counts: { available: 46, injured: 1, rest: 1, restricted: 1, retired: 1 },
    resident_dogs: 50,
    occupied_locations: 22,
    housing_areas: { 'Zone A': 20, 'Zone B': 20, 'Puppy A': 5, 'Puppy B': 5 },
  },
  unavailable_dogs: [
    { id: 'hazel-id', name: 'Hazel', availability: 'injured', housing_code: 'A2-02' },
  ],
  plan: {
    exists: false,
    activities_count: 0,
    activity_counts: {},
    planned_dogs: 0,
    planned_dog_km: 0,
    training_with_saved_teams: 0,
    training_without_saved_teams: 0,
    notes_preview: null,
    status_counts: {},
    training: [],
  },
  actual: { sessions: 2, dogs_worked: 16, dog_starts: 16, dog_km: 120 },
  attention: {
    date_from: '2026-03-18',
    date_to: '2026-03-31',
    label: 'Previous 14 days',
    underused_count: 9,
    higher_workload_count: 3,
    underused: [
      {
        id: 'nala-id',
        name: 'Nala',
        dog_class: 'training',
        availability: 'available',
        dog_km: 5,
        dog_starts: 1,
        eligible_days: 14,
        worked_days: 1,
        recent_7d_km: 5,
        recent_14d_km: 5,
        longest_work_streak: 1,
        eligible_rest_streak: 3,
        workload_rate: 2.5,
        peer_median_rate: 5,
        reason: '5 km across 14 eligible days · below training peer pace',
      },
    ],
    higher_workload: [],
  },
  recent_weekly: [
    {
      sessions: 8,
      dogs_worked: 32,
      dog_starts: 64,
      dog_km: 480,
      average_km_per_worked_dog: 15,
      average_km_per_start: 7.5,
      starts_5km: 32,
      starts_10km: 32,
      max_daily_dog_km: 10,
      week_start: '2026-03-23',
      week_end: '2026-03-29',
      period_start: '2026-03-23',
      period_end: '2026-03-29',
      iso_week: 13,
    },
  ],
};

async function setup() {
  await TestBed.configureTestingModule({
    imports: [DashboardPageComponent],
    providers: [
      provideHttpClient(),
      provideHttpClientTesting(),
      provideRouter([
        { path: 'dashboard', component: DashboardPageComponent },
        { path: 'dogs/:dogId', component: DashboardPageComponent },
      ]),
    ],
  }).compileComponents();
  const fixture = TestBed.createComponent(DashboardPageComponent);
  fixture.detectChanges();
  return { fixture, http: TestBed.inject(HttpTestingController) };
}

describe('DashboardPageComponent', () => {
  it('renders the clean-reset snapshot and purposeful no-plan state', async () => {
    const { fixture, http } = await setup();
    expect(fixture.nativeElement.textContent).toContain('Loading the operational dashboard');
    const request = http.expectOne(
      (candidate) =>
        candidate.url === '/api/v1/dashboard' && candidate.params.get('date') === '2026-03-31',
    );
    request.flush(dashboard);
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent;
    expect(text).toContain('50');
    expect(text).toContain('Active dogs');
    expect(text).toContain('No plan for this date');
    expect(text).toContain('120');
    expect(text).toContain('Hazel');
    expect(text).toContain('Nala');
    expect(fixture.nativeElement.querySelector('a[href^="/demo/daily"]')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('a[href^="/demo/daily-entry"]')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('a[href^="/demo/kennel"]')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('a[href^="/demo/analytics"]')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('a[href="/demo/dogs/hazel-id"]')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('a[href*="/dogs/nala-id"]')).not.toBeNull();
    http.verify();
  });

  it('uses singular copy in the recent workload trend', async () => {
    const { fixture, http } = await setup();
    const singular = structuredClone(dashboard);
    singular.recent_weekly[0].dog_starts = 1;
    singular.recent_weekly[0].dogs_worked = 1;
    http.expectOne((candidate) => candidate.url === '/api/v1/dashboard').flush(singular);
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('1 start · 1 dog');
    expect(fixture.nativeElement.textContent).not.toContain('1 starts');
    http.verify();
  });

  it('shows persisted plan and team state without rendering a second editor', async () => {
    const { fixture, http } = await setup();
    const planned = structuredClone(dashboard);
    planned.plan = {
      exists: true,
      activities_count: 2,
      activity_counts: { training: 1, rest: 1 },
      planned_dogs: 8,
      planned_dog_km: 80,
      training_with_saved_teams: 1,
      training_without_saved_teams: 0,
      notes_preview: 'Keep the day calm and compact.',
      status_counts: { not_recorded: 2 },
      training: [
        {
          id: 'activity-id',
          title: 'Forest Loop',
          distance_km: 10,
          participant_count: 8,
          team_count: 1,
          arranged_dog_count: 8,
          actual_status: 'not_recorded',
        },
      ],
    };
    http.expectOne((candidate) => candidate.url === '/api/v1/dashboard').flush(planned);
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent;
    expect(text).toContain('Forest Loop');
    expect(text).toContain('1 team · 8 arranged');
    expect(text).toContain('Not recorded');
    expect(text).toContain('Keep the day calm and compact.');
    expect(fixture.nativeElement.querySelector('a[href*="activity-id/teams"]')).not.toBeNull();
    http.verify();
  });

  it('shows an actionable API error state', async () => {
    const { fixture, http } = await setup();
    http
      .expectOne((candidate) => candidate.url === '/api/v1/dashboard')
      .flush('Unavailable', { status: 503, statusText: 'Unavailable' });
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Dashboard unavailable');
    expect(fixture.nativeElement.querySelector('button')?.textContent).toContain('Try again');
    http.verify();
  });
});
