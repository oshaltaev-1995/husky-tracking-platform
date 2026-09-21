import { HttpErrorResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { BehaviorSubject, of, throwError } from 'rxjs';

import { DogProfileBundle } from '../../../core/api/dogs.models';
import { DogsService } from '../../../core/api/dogs.service';
import { DogProfileComponent } from './dog-profile.component';

const id = '9422673b-331b-5e72-a700-5fff0574a209';
const relativeId = 'b265ec9a-985f-5533-9142-7ba9d59f899f';
const bundle: DogProfileBundle = {
  profile: {
    id,
    name: 'Aurora',
    birth_date: '2016-01-10',
    age_years: 10,
    age_months: 2,
    age_label: '10 years, 2 months',
    sex: 'female',
    is_neutered: true,
    neutered_on: '2023-01-01',
    photo_key: '9422673b-331b-5e72-a700-5fff0574a209.webp',
    notes: 'Calm foundation dog.',
    litter_code: null,
    litter_birth_date: null,
    capabilities: ['team'],
    state: {
      reference_date: '2026-03-31',
      lifecycle: 'active',
      dog_class: 'standard',
      class_is_historical: false,
      availability: 'available',
      housing: {
        code: 'A1-01',
        display_name: 'A1 enclosure 1',
        location_type: 'adult_enclosure',
        zone: 'A',
        row: '1',
      },
    },
    archive: null,
    last_known_housing: {
      code: 'A1-01',
      display_name: 'A1 enclosure 1',
      location_type: 'adult_enclosure',
      zone: 'A',
      row: '1',
    },
  },
  pedigree: {
    dog_id: id,
    mother: null,
    father: null,
    maternal_grandparents: { mother: null, father: null },
    paternal_grandparents: { mother: null, father: null },
    litter: null,
    offspring: [
      {
        code: 'C',
        birth_date: '2018-06-15',
        children: [
          {
            id: relativeId,
            name: 'Cedar',
            birth_date: '2018-06-15',
            lifecycle: 'archived',
            dog_class: 'standard',
          },
        ],
      },
    ],
  },
  work: {
    dog_id: id,
    season_start: '2025-12-01',
    season_end: '2026-03-31',
    summary: {
      total_km: 0,
      starts: 0,
      starts_5km: 0,
      starts_10km: 0,
      last_work_date: null,
      average_km_per_start: null,
    },
    weekly: [],
    entries: [],
  },
  history: {
    dog_id: id,
    reference_date: '2026-03-31',
    availability: [
      {
        value: 'available',
        valid_from: '2025-12-01',
        valid_to: null,
        is_current: true,
        note: null,
      },
    ],
    classes: [],
    lifecycle: [],
    housing: [],
    archive: null,
  },
};

describe('DogProfileComponent', () => {
  const params = new BehaviorSubject(convertToParamMap({ dogId: id }));
  const query = new BehaviorSubject(convertToParamMap({}));

  async function setup(getProfileBundle = () => of(bundle)) {
    await TestBed.configureTestingModule({
      imports: [DogProfileComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { paramMap: params, queryParamMap: query } },
        { provide: DogsService, useValue: { getProfileBundle } },
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(DogProfileComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    return fixture;
  }

  afterEach(() => {
    params.next(convertToParamMap({ dogId: id }));
    query.next(convertToParamMap({}));
  });

  it('renders the profile and switches tabs without refetching', async () => {
    let calls = 0;
    const fixture = await setup(() => {
      calls += 1;
      return of(bundle);
    });
    expect(fixture.nativeElement.textContent).toContain('Aurora');
    expect(fixture.nativeElement.textContent).toContain('Kennel record');
    const portrait = fixture.nativeElement.querySelector('.profile-media img') as HTMLImageElement;
    expect(portrait.getAttribute('alt')).toBe('Portrait of Aurora');
    expect(portrait.getAttribute('loading')).toBe('eager');
    expect(fixture.nativeElement.textContent).toContain('Team');
    expect(fixture.nativeElement.textContent).not.toContain('Work rolesteam');

    query.next(convertToParamMap({ tab: 'pedigree' }));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Parents and grandparents');
    const relation = fixture.nativeElement.querySelector('a.relation-card') as HTMLAnchorElement;
    expect(relation.getAttribute('href')).toContain(relativeId);

    query.next(convertToParamMap({ tab: 'work' }));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No regular sled work');
    expect(calls).toBe(1);
  });

  it('renders a not-found state for an invalid dog', async () => {
    const fixture = await setup(() =>
      throwError(() => new HttpErrorResponse({ status: 404 })),
    );
    expect(fixture.nativeElement.textContent).toContain('This dog profile is unavailable');
  });

  it('keeps archive metadata in the normal profile experience', async () => {
    const archived = structuredClone(bundle);
    archived.profile.state.lifecycle = 'archived';
    archived.profile.state.availability = null;
    archived.profile.state.housing = null;
    archived.profile.archive = {
      archive_date: '2025-12-15',
      reason: 'euthanized',
      note: 'Humane fictional end-of-life record.',
    };
    query.next(convertToParamMap({ from: 'archive' }));
    const fixture = await setup(() => of(archived));
    expect(fixture.nativeElement.textContent).toContain('Archived');
    expect(fixture.nativeElement.textContent).toContain('Euthanized');
    expect(fixture.nativeElement.textContent).toContain('Back to Archive');
    const workTab = Array.from(
      fixture.nativeElement.querySelectorAll('.profile-tabs a') as NodeListOf<HTMLAnchorElement>,
    ).find((link) => link.textContent.trim() === 'Work')!;
    expect(workTab.getAttribute('href')).toContain('from=archive');
  });

  it('returns a directly opened archived profile to Dogs without an archive origin', async () => {
    const archived = structuredClone(bundle);
    archived.profile.state.lifecycle = 'archived';
    archived.profile.state.availability = null;
    archived.profile.archive = {
      archive_date: '2025-12-15',
      reason: 'deceased',
      note: null,
    };
    const fixture = await setup(() => of(archived));
    expect(fixture.nativeElement.textContent).toContain('Back to Dogs');
    expect(fixture.nativeElement.textContent).not.toContain('Back to Archive');
  });

  it('shows five recent work entries until the ledger is expanded', async () => {
    const worked = structuredClone(bundle);
    worked.work.summary.starts = 7;
    worked.work.entries = Array.from({ length: 7 }, (_, index) => ({
      date: `2026-03-${String(31 - index).padStart(2, '0')}`,
      distance_km: 10,
      activity_type: 'training',
      label: `Run ${index + 1}`,
      role: null,
    }));
    const fixture = await setup(() => of(worked));
    query.next(convertToParamMap({ tab: 'work' }));
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelectorAll('.work-list article').length).toBe(5);
    const toggle = fixture.nativeElement.querySelector('.work-disclosure') as HTMLButtonElement;
    expect(toggle.textContent).toContain('Show all 7 records');
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    toggle.click();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelectorAll('.work-list article').length).toBe(7);
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    toggle.click();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelectorAll('.work-list article').length).toBe(5);
  });
});
