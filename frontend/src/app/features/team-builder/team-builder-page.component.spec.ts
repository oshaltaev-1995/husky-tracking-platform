import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { of } from 'rxjs';

import {
  PlannedTeam,
  TeamBuilderCandidate,
  TeamBuilderContext,
} from '../../core/api/team-builder.models';
import { TeamBuilderPageComponent } from './team-builder-page.component';

const dogNames = ['Atlas', 'Aurora', 'Clover', 'Daisy', 'Drift', 'Dune', 'Freya', 'Harbor'];

const candidates: TeamBuilderCandidate[] = dogNames.map((name, index) => ({
  id: `dog-${index + 1}`,
  name,
  housing_code: `A1-0${Math.floor(index / 2) + 1}`,
  dog_class: 'standard',
  availability: 'available',
  capabilities: ['lead', 'team', 'wheel'],
  eligible: true,
  reasons: [],
  workload: {
    km_7d: index * 5,
    km_14d: index * 10,
    season_km: 100 + index * 10,
    starts_14d: index,
    days_since_last_work: index + 1,
    planned_km_today: 10,
  },
}));

const team: PlannedTeam = {
  id: null,
  sequence: 1,
  display_label: 'Team 1',
  team_size: 8,
  slots: candidates.map((dog, index) => {
    const pairIndex = Math.floor(index / 2);
    const role = pairIndex === 0 ? 'lead' : pairIndex === 3 ? 'wheel' : 'team';
    return {
      dog_id: dog.id,
      dog_name: dog.name,
      pair_index: pairIndex,
      pair_label: role === 'team' ? `Team ${pairIndex}` : role[0].toUpperCase() + role.slice(1),
      side: index % 2 === 0 ? ('left' as const) : ('right' as const),
      harness_role: role as 'lead' | 'team' | 'wheel',
      position_order: index + 1,
      explanations: [`${role[0].toUpperCase() + role.slice(1)} capable`],
    };
  }),
};

function context(savedTeams: PlannedTeam[] = []): TeamBuilderContext {
  return {
    activity: {
      id: 'activity-id',
      date: '2026-03-31',
      title: 'Forest Loop',
      distance_km: 10,
      participant_count: 8,
      plan_revision: savedTeams.length ? 2 : 1,
    },
    recommended_team_count: 1,
    recommended_team_size: 8,
    supported_team_sizes: [4, 6, 8, 10, 12],
    capability_summary: { lead: 8, team: 8, wheel: 8 },
    candidates,
    relationships: [
      { dog_a_id: 'dog-1', dog_b_id: 'dog-2', kind: 'preferred_pair' },
    ],
    saved_teams: savedTeams,
  };
}

async function setup() {
  await TestBed.configureTestingModule({
    imports: [TeamBuilderPageComponent],
    providers: [
      provideHttpClient(),
      provideHttpClientTesting(),
      provideRouter([
        {
          path: 'daily/:date/activities/:activityId/teams',
          component: TeamBuilderPageComponent,
        },
        { path: 'dogs/:dogId', component: TeamBuilderPageComponent },
      ]),
      {
        provide: ActivatedRoute,
        useValue: {
          paramMap: of(
            convertToParamMap({ date: '2026-03-31', activityId: 'activity-id' }),
          ),
        },
      },
    ],
  }).compileComponents();
  const fixture = TestBed.createComponent(TeamBuilderPageComponent);
  fixture.detectChanges();
  return { fixture, http: TestBed.inject(HttpTestingController) };
}

describe('TeamBuilderPageComponent', () => {
  afterEach(() => TestBed.inject(HttpTestingController).verify());

  it('explains a two-dog deep link without offering generation', async () => {
    const { fixture, http } = await setup();
    http.expectOne('/api/v1/daily-plans/2026-03-31/activities/activity-id/team-builder')
      .flush({
        ...context(),
        activity: { ...context().activity, participant_count: 2 },
        candidates: candidates.slice(0, 2),
      });
    await fixture.whenStable();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('needs at least 4 eligible dogs');
    expect(fixture.nativeElement.textContent).toContain('recorded without teams');
    expect(fixture.nativeElement.querySelector('.configuration')).toBeNull();
    expect(fixture.nativeElement.querySelector('.empty-builder a').getAttribute('href'))
      .toContain('/demo/daily');
  });

  it('explains a four-dog pool with only two currently eligible dogs', async () => {
    const { fixture, http } = await setup();
    http.expectOne('/api/v1/daily-plans/2026-03-31/activities/activity-id/team-builder')
      .flush({
        ...context(),
        activity: { ...context().activity, participant_count: 4 },
        candidates: [
          ...candidates.slice(0, 2),
          ...candidates.slice(2, 4).map((dog) => ({
            ...dog,
            eligible: false,
            reasons: ['Injured'],
          })),
        ],
      });
    await fixture.whenStable();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('2 of 4 selected dogs are eligible');
    expect(fixture.nativeElement.textContent).toContain('Injured');
    expect(fixture.nativeElement.querySelector('.configuration')).toBeNull();
  });

  it('generates, renders, manually swaps, and saves an explainable harness', async () => {
    const { fixture, http } = await setup();
    http
      .expectOne('/api/v1/daily-plans/2026-03-31/activities/activity-id/team-builder')
      .flush(context());
    await fixture.whenStable();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Lead capable');
    expect(fixture.nativeElement.textContent).toContain('Recommended: 1 × 8');
    (fixture.nativeElement.querySelector('.configuration .primary') as HTMLButtonElement).click();
    const generation = http.expectOne(
      '/api/v1/daily-plans/2026-03-31/activities/activity-id/teams/generate',
    );
    expect(generation.request.body).toEqual({ team_count: 1, team_size: 8 });
    generation.flush({ activity: context().activity, persisted: false, teams: [team], unassigned: [] });
    await fixture.whenStable();
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelectorAll('.harness-pair').length).toBe(4);
    expect(fixture.nativeElement.textContent).toContain('Direction of travel');
    const slotButtons = fixture.nativeElement.querySelectorAll('.slot-select') as NodeListOf<HTMLButtonElement>;
    slotButtons[0].click();
    slotButtons[1].click();
    fixture.detectChanges();
    expect(slotButtons[0].textContent).toContain('Aurora');

    (fixture.nativeElement.querySelector('.lineup-actions .primary') as HTMLButtonElement).click();
    const save = http.expectOne(
      '/api/v1/daily-plans/2026-03-31/activities/activity-id/teams',
    );
    expect(save.request.body.expected_revision).toBe(1);
    expect(save.request.body.teams[0].slots.length).toBe(8);
    save.flush(context([{ ...team, id: 'team-id' }]));
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Team lineup saved');
    expect(fixture.nativeElement.textContent).toContain('Edit saved lineup');
  });

  it('shows solver shortage detail without destroying the current view', async () => {
    const { fixture, http } = await setup();
    http
      .expectOne('/api/v1/daily-plans/2026-03-31/activities/activity-id/team-builder')
      .flush(context());
    await fixture.whenStable();
    fixture.detectChanges();
    (fixture.nativeElement.querySelector('.configuration .primary') as HTMLButtonElement).click();
    http
      .expectOne('/api/v1/daily-plans/2026-03-31/activities/activity-id/teams/generate')
      .flush(
        { detail: { code: 'lead_shortage', message: 'Need 4 lead-capable dogs; selected pool has 2.' } },
        { status: 422, statusText: 'Unprocessable Entity' },
      );
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="alert"]').textContent).toContain(
      'Need 4 lead-capable dogs',
    );
  });

  it('requires acknowledgement before rebuilding saved manual work', async () => {
    const { fixture, http } = await setup();
    http
      .expectOne('/api/v1/daily-plans/2026-03-31/activities/activity-id/team-builder')
      .flush(context([{ ...team, id: 'team-id' }]));
    await fixture.whenStable();
    fixture.detectChanges();
    (fixture.nativeElement.querySelector('.configuration .primary') as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Replace the current arrangement?');
    http.expectNone('/api/v1/daily-plans/2026-03-31/activities/activity-id/teams/generate');
    const confirm = Array.from(
      fixture.nativeElement.querySelectorAll('.confirmation button') as NodeListOf<HTMLButtonElement>,
    ).find((button) => button.textContent.includes('Generate replacement'))!;
    confirm.click();
    http
      .expectOne('/api/v1/daily-plans/2026-03-31/activities/activity-id/teams/generate')
      .flush({ activity: context().activity, persisted: false, teams: [team], unassigned: [] });
  });
});
