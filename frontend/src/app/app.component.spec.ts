import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';

import { AppComponent } from './app.component';

describe('AppComponent', () => {
  it('renders the fixed demo season returned by the API', async () => {
    await TestBed.configureTestingModule({
      imports: [AppComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();

    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();

    const http = TestBed.inject(HttpTestingController);
    http.expectOne('/api/v1/health').flush({
      status: 'ok',
      service: 'Husky Tracking API',
      version: '0.1.0',
      demo_season: 'Demo season — Winter 2025–2026',
      demo_season_start: '2025-12-01',
      demo_season_end: '2026-03-31',
      demo_reference_date: '2026-03-31',
    });
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain(
      'Demo season — Winter 2025–2026',
    );
    http.verify();
  });
});
