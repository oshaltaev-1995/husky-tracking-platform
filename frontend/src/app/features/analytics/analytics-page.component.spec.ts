import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';

import {
  AnalyticsDogsResponse,
  AnalyticsOverview,
  PopulationAnalytics,
} from '../../core/api/analytics.models';
import { AnalyticsPageComponent } from './analytics-page.component';

const overview: AnalyticsOverview = {
  date_from: '2025-12-01',
  date_to: '2026-03-31',
  season_start: '2025-12-01',
  season_end: '2026-03-31',
  context_date: '2026-03-31',
  summary: {
    sessions: 140,
    dogs_worked: 36,
    dog_starts: 1120,
    dog_km: 8400,
    average_km_per_worked_dog: 233.3,
    average_km_per_start: 7.5,
    starts_5km: 560,
    starts_10km: 560,
    max_daily_dog_km: 10,
  },
  weekly: [
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
      week_start: '2025-12-01',
      week_end: '2025-12-07',
      period_start: '2025-12-01',
      period_end: '2025-12-07',
      iso_week: 49,
    },
  ],
  distance_breakdown: [
    { distance_km: 5, dog_starts: 560, dog_km: 2800 },
    { distance_km: 10, dog_starts: 560, dog_km: 5600 },
  ],
  role_breakdown: [
    { role: 'lead', dog_starts: 100, dog_km: 750 },
    { role: 'team', dog_starts: 860, dog_km: 6450 },
    { role: 'wheel', dog_starts: 160, dog_km: 1200 },
    { role: 'unpositioned', dog_starts: 0, dog_km: 0 },
  ],
  attention_population: 33,
  underused: [
    {
      id: 'cedar-id',
      name: 'Cedar',
      dog_class: 'standard',
      availability: 'restricted',
      dog_km: 235,
      dog_starts: 30,
      eligible_days: 109,
      worked_days: 30,
      recent_7d_km: 0,
      recent_14d_km: 5,
      longest_work_streak: 1,
      eligible_rest_streak: 0,
      workload_rate: 15.09,
      peer_median_rate: 17.64,
      reason: '235 km across 109 eligible days · below standard peer pace',
    },
  ],
  higher_workload: [
    {
      id: 'aurora-id',
      name: 'Aurora',
      dog_class: 'standard',
      availability: 'available',
      dog_km: 350,
      dog_starts: 42,
      eligible_days: 116,
      worked_days: 42,
      recent_7d_km: 20,
      recent_14d_km: 45,
      longest_work_streak: 1,
      eligible_rest_streak: 0,
      workload_rate: 21.12,
      peer_median_rate: 17.64,
      reason: '350 km · 45 km in the final 14 days · above standard peer pace',
    },
  ],
};

const dogs: AnalyticsDogsResponse = {
  date_from: '2025-12-01',
  date_to: '2026-03-31',
  context_date: '2026-03-31',
  result_count: 2,
  items: [
    {
      id: 'aurora-id',
      name: 'Aurora',
      sex: 'female',
      dog_class: 'standard',
      lifecycle: 'active',
      availability: 'available',
      housing_code: 'A1-01',
      housing_zone: 'A',
      capabilities: ['lead', 'team'],
      dog_starts: 42,
      dog_km: 350,
      starts_5km: 14,
      starts_10km: 28,
      last_work_date: '2026-03-31',
      worked_days: 42,
      eligible_days: 116,
      longest_work_streak: 1,
      eligible_rest_streak: 0,
      recent_7d_km: 20,
      recent_14d_km: 45,
      workload_status: 'higher',
      attention_reason: 'Above peer pace',
    },
    {
      id: 'taro-id',
      name: 'Taro',
      sex: 'male',
      dog_class: 'puppy',
      lifecycle: 'active',
      availability: 'available',
      housing_code: 'PUPPY-A',
      housing_zone: 'PUPPY',
      capabilities: [],
      dog_starts: 0,
      dog_km: 0,
      starts_5km: 0,
      starts_10km: 0,
      last_work_date: null,
      worked_days: 0,
      eligible_days: 0,
      longest_work_streak: 0,
      eligible_rest_streak: 0,
      recent_7d_km: 0,
      recent_14d_km: 0,
      workload_status: 'not_applicable',
      attention_reason: 'Puppy · not in regular sled-work comparison',
    },
  ],
};

const population: PopulationAnalytics = {
  snapshot_date: '2026-03-31',
  season_start: '2025-12-01',
  season_end: '2026-03-31',
  distribution_basis: 'active dogs on snapshot date',
  headline: {
    total_represented: 60,
    active_dogs: 50,
    archived_dogs: 10,
    average_age_years: 3.8,
    median_age_years: 3.1,
  },
  sex: [
    { key: 'female', label: 'Female', count: 22 },
    { key: 'male', label: 'Male', count: 28 },
  ],
  age_bands: [{ key: 'under_1', label: 'Under 1 year', count: 10 }],
  birth_cohorts: [
    { birth_year: 2016, total: 4, active: 4, archived: 0, litter_codes: [] },
    { birth_year: 2026, total: 10, active: 10, archived: 0, litter_codes: ['T', 'V'] },
  ],
  classes: [
    { key: 'puppy', label: 'Puppy', count: 10 },
    { key: 'junior', label: 'Junior', count: 6 },
    { key: 'training', label: 'Training', count: 8 },
    { key: 'standard', label: 'Standard', count: 26 },
  ],
  neuter_status: [
    { key: 'neutered', label: 'Neutered / spayed', count: 22 },
    { key: 'intact', label: 'Intact', count: 28 },
  ],
  availability: [
    { key: 'available', label: 'Available', count: 46 },
    { key: 'retired', label: 'Retired', count: 1 },
  ],
  capabilities: [
    { key: 'lead', label: 'Lead capable', count: 13 },
    { key: 'team', label: 'Team capable', count: 34 },
    { key: 'wheel', label: 'Wheel capable', count: 16 },
  ],
  housing_areas: [
    { key: 'zone_a', label: 'Zone A', count: 20 },
    { key: 'zone_b', label: 'Zone B', count: 20 },
    { key: 'PUPPY-A', label: 'Puppy A', count: 5 },
    { key: 'PUPPY-B', label: 'Puppy B', count: 5 },
  ],
};

async function setup(url = '/analytics') {
  await TestBed.configureTestingModule({
    imports: [AnalyticsPageComponent],
    providers: [
      provideHttpClient(),
      provideHttpClientTesting(),
      provideRouter([
        { path: 'analytics', component: AnalyticsPageComponent },
        { path: 'dogs/:dogId', component: AnalyticsPageComponent },
      ]),
    ],
  }).compileComponents();
  const router = TestBed.inject(Router);
  await router.navigateByUrl(url);
  const fixture = TestBed.createComponent(AnalyticsPageComponent);
  fixture.detectChanges();
  return { fixture, router, http: TestBed.inject(HttpTestingController) };
}

function flushWorkload(
  http: HttpTestingController,
  overviewResponse = overview,
  dogResponse = dogs,
) {
  const requests = http.match((request) => request.url.startsWith('/api/v1/analytics/'));
  expect(requests.length).toBe(2);
  for (const request of requests) {
    if (request.request.url.endsWith('/overview')) request.flush(overviewResponse);
    else request.flush(dogResponse);
  }
}

describe('AnalyticsPageComponent', () => {
  afterEach(() => TestBed.inject(HttpTestingController).verify());

  it('loads full-season workload KPIs, weekly trend, attention, and dog links', async () => {
    const { fixture, http } = await setup();
    flushWorkload(http);
    await fixture.whenStable();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('8,400');
    expect(fixture.nativeElement.textContent).toContain('Weekly trend');
    expect(fixture.nativeElement.textContent).toContain('Cedar');
    expect(fixture.nativeElement.textContent).toContain('Aurora');
    expect(fixture.nativeElement.textContent).toContain('Taro');
    expect(fixture.nativeElement.querySelector('a[href="/dogs/aurora-id?tab=work"]')).not.toBeNull();
  });

  it('restores a custom range and changes weekly metric without refetching', async () => {
    const { fixture, router, http } = await setup(
      '/analytics?from=2026-01-01&to=2026-01-31',
    );
    const requests = http.match(() => true);
    expect(requests.every((request) => request.request.params.get('from') === '2026-01-01')).toBe(
      true,
    );
    for (const request of requests) {
      if (request.request.url.endsWith('/overview')) request.flush({
        ...overview,
        date_from: '2026-01-01',
        date_to: '2026-01-31',
      });
      else request.flush({ ...dogs, date_from: '2026-01-01', date_to: '2026-01-31' });
    }
    await fixture.whenStable();
    fixture.detectChanges();
    const starts = Array.from(
      fixture.nativeElement.querySelectorAll('.metric-switch button') as NodeListOf<HTMLButtonElement>,
    ).find((button) => button.textContent.trim() === 'Starts')!;
    starts.click();
    fixture.detectChanges();
    expect(starts.getAttribute('aria-pressed')).toBe('true');
    expect(router.url).toContain('from=2026-01-01');
    http.expectNone(() => true);
  });

  it('applies dog search, class, and sort through URL-backed API state', async () => {
    const { fixture, http } = await setup();
    flushWorkload(http);
    await fixture.whenStable();
    fixture.detectChanges();
    const search = fixture.nativeElement.querySelector('input[name="search"]') as HTMLInputElement;
    const dogClass = fixture.nativeElement.querySelector('select[name="dogClass"]') as HTMLSelectElement;
    const sort = fixture.nativeElement.querySelector('select[name="sort"]') as HTMLSelectElement;
    search.value = 'Aurora';
    search.dispatchEvent(new Event('input'));
    dogClass.value = 'standard';
    dogClass.dispatchEvent(new Event('change'));
    sort.value = 'lowest_km';
    sort.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    (fixture.nativeElement.querySelector('.dog-filters') as HTMLFormElement).dispatchEvent(
      new Event('submit'),
    );
    await fixture.whenStable();
    fixture.detectChanges();
    const requests = http.match(() => true);
    expect(requests.length).toBe(2);
    const dogRequest = requests.find((request) => request.request.url.endsWith('/dogs'))!;
    expect(dogRequest.request.params.get('search')).toBe('Aurora');
    expect(dogRequest.request.params.get('dog_class')).toBe('standard');
    expect(dogRequest.request.params.get('sort')).toBe('lowest_km');
    for (const request of requests) {
      request.flush(request === dogRequest ? { ...dogs, result_count: 1, items: [dogs.items[0]] } : overview);
    }
  });

  it('switches to the dated population view and renders cohorts and distributions', async () => {
    const { fixture, router, http } = await setup();
    flushWorkload(http);
    await fixture.whenStable();
    fixture.detectChanges();
    const populationButton = Array.from(
      fixture.nativeElement.querySelectorAll('.analytics-areas button') as NodeListOf<HTMLButtonElement>,
    ).find((button) => button.textContent.includes('Population'))!;
    populationButton.click();
    await fixture.whenStable();
    fixture.detectChanges();
    http.expectOne(
      (request) =>
        request.url.endsWith('/analytics/population') &&
        request.params.get('date') === '2026-03-31',
    ).flush(population);
    await fixture.whenStable();
    fixture.detectChanges();

    expect(router.url).toContain('view=population');
    expect(fixture.nativeElement.textContent).toContain('50');
    expect(fixture.nativeElement.textContent).toContain('Birth cohorts');
    expect(fixture.nativeElement.textContent).toContain('2016');
    expect(fixture.nativeElement.textContent).toContain('Puppy A');
  });

  it('shows an honest zero-work state', async () => {
    const { fixture, http } = await setup();
    flushWorkload(http, {
      ...overview,
      summary: {
        sessions: 0,
        dogs_worked: 0,
        dog_starts: 0,
        dog_km: 0,
        average_km_per_worked_dog: 0,
        average_km_per_start: 0,
        starts_5km: 0,
        starts_10km: 0,
        max_daily_dog_km: 0,
      },
      weekly: [],
      underused: [],
      higher_workload: [],
    });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No actual work in this range');

    const retry = fixture.nativeElement.querySelector('.range-form button') as HTMLButtonElement;
    expect(retry.disabled).toBe(false);
  });

  it('shows an API error state with retry', async () => {
    const { fixture, http } = await setup();
    const requests = http.match(() => true);
    requests[0].flush({ detail: 'offline' }, { status: 503, statusText: 'Unavailable' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Analytics unavailable');
    expect(fixture.nativeElement.textContent).toContain('Try again');
  });
});
