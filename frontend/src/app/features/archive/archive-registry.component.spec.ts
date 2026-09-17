import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { ArchiveRegistryComponent } from './archive-registry.component';

describe('ArchiveRegistryComponent', () => {
  it('presents preserved records with human archive terminology and profile links', async () => {
    await TestBed.configureTestingModule({
      imports: [ArchiveRegistryComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();
    const fixture = TestBed.createComponent(ArchiveRegistryComponent);
    fixture.detectChanges();
    const http = TestBed.inject(HttpTestingController);
    http.expectOne('/api/v1/archive?sort=name').flush({
      reference_date: '2026-03-31',
      result_count: 1,
      total_archived: 10,
      items: [
        {
          id: 'b265ec9a-985f-5533-9142-7ba9d59f899f',
          name: 'Django',
          birth_date: '2019-01-02',
          age_years: 7,
          age_months: 2,
          age_label: '7 years, 2 months',
          sex: 'male',
          litter_code: 'D',
          archive: {
            archive_date: '2025-12-15',
            reason: 'deceased',
            note: 'Natural fictional end-of-life record.',
          },
          offspring_count: 6,
          photo_key: null,
        },
      ],
    });
    await fixture.whenStable();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Died naturally');
    expect(fixture.nativeElement.textContent).toContain('6 offspring');
    const link = fixture.nativeElement.querySelector('.archive-row') as HTMLAnchorElement;
    expect(link.getAttribute('href')).toContain('b265ec9a-985f-5533-9142-7ba9d59f899f');
    http.verify();
  });
});
