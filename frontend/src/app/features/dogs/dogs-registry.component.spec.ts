import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { DogsRegistryResponse } from '../../core/api/dogs.models';
import { DogsRegistryComponent } from './dogs-registry.component';

const response: DogsRegistryResponse = {
  reference_date: '2026-03-31',
  result_count: 1,
  summary: { total: 50, puppy: 10, junior: 6, training: 8, standard: 26 },
  housing_groups: ['A1', 'PUPPY'],
  items: [
    {
      id: '9422673b-331b-5e72-a700-5fff0574a209',
      name: 'Aurora',
      birth_date: '2016-01-10',
      age_years: 10,
      age_months: 2,
      age_label: '10 years, 2 months',
      sex: 'female',
      is_neutered: true,
      litter_code: null,
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
      photo_key: null,
    },
  ],
};

describe('DogsRegistryComponent', () => {
  it('renders canonical summary, dog cards, and submits search', async () => {
    await TestBed.configureTestingModule({
      imports: [DogsRegistryComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();
    const fixture = TestBed.createComponent(DogsRegistryComponent);
    fixture.detectChanges();
    const http = TestBed.inject(HttpTestingController);
    http.expectOne('/api/v1/dogs?sort=name').flush(response);
    await fixture.whenStable();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('50');
    expect(fixture.nativeElement.textContent).toContain('Aurora');
    const profileLink = fixture.nativeElement.querySelector('.dog-card') as HTMLAnchorElement;
    expect(profileLink.getAttribute('href')).toContain(response.items[0].id);

    const search = fixture.nativeElement.querySelector('input[type="search"]') as HTMLInputElement;
    search.value = 'aurora';
    search.dispatchEvent(new Event('input'));
    await fixture.whenStable();
    (fixture.nativeElement.querySelector('form') as HTMLFormElement).dispatchEvent(
      new Event('submit'),
    );
    http.expectOne('/api/v1/dogs?search=aurora&sort=name').flush(response);
    http.verify();
  });
});
