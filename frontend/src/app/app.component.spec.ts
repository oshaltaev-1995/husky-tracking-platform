import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { Component } from '@angular/core';
import { provideRouter, Router } from '@angular/router';

import { AppComponent } from './app.component';

@Component({ template: '' })
class EmptyRouteComponent {}

describe('AppComponent', () => {
  it('renders the fixed demo season returned by the API', async () => {
    await TestBed.configureTestingModule({
      imports: [AppComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([{ path: 'archive', component: EmptyRouteComponent }]),
      ],
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
      'Winter 2025–2026',
    );
    expect(fixture.nativeElement.textContent).toContain('Dogs');
    expect(fixture.nativeElement.textContent).toContain('Kennel Map');
    expect(fixture.nativeElement.textContent).toContain('Daily Plan');
    expect(fixture.nativeElement.textContent).toContain('Daily Entry');
    expect(fixture.nativeElement.textContent).toContain('Analytics');
    expect(fixture.nativeElement.textContent).toContain('Archive');
    expect(fixture.nativeElement.querySelector('.desktop-sidebar')).not.toBeNull();
    http.verify();
  });

  it('opens, closes, and navigates from the accessible mobile drawer', async () => {
    await TestBed.configureTestingModule({
      imports: [AppComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([{ path: 'archive', component: EmptyRouteComponent }]),
      ],
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

    const trigger = fixture.nativeElement.querySelector('.menu-button') as HTMLButtonElement;
    trigger.click();
    await new Promise((resolve) => setTimeout(resolve, 0));
    fixture.detectChanges();
    expect(trigger.getAttribute('aria-expanded')).toBe('true');
    expect(fixture.nativeElement.querySelector('.mobile-drawer')).not.toBeNull();
    expect(document.body.classList.contains('mobile-nav-open')).toBe(true);
    expect(document.activeElement?.getAttribute('aria-label')).toBe('Close navigation');

    const archiveLink = fixture.nativeElement.querySelector(
      '.mobile-drawer a[href="/archive"]',
    ) as HTMLAnchorElement;
    archiveLink.click();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(TestBed.inject(Router).url).toBe('/archive');
    expect(fixture.nativeElement.querySelector('.mobile-drawer')).toBeNull();
    expect(document.body.classList.contains('mobile-nav-open')).toBe(false);
    http.verify();
  });
});
