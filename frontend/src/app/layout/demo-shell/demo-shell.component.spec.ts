import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';

import { DemoShellComponent } from './demo-shell.component';

@Component({ template: '<h1>Archive</h1>' })
class EmptyRouteComponent {}

describe('DemoShellComponent', () => {
  async function setup() {
    await TestBed.configureTestingModule({
      imports: [DemoShellComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([
          {
            path: 'demo',
            component: DemoShellComponent,
            children: [
              { path: 'dashboard', component: EmptyRouteComponent },
              { path: 'archive', component: EmptyRouteComponent },
            ],
          },
          { path: 'about', component: EmptyRouteComponent },
          { path: '', component: EmptyRouteComponent },
        ]),
      ],
    }).compileComponents();
    const router = TestBed.inject(Router);
    const fixture = TestBed.createComponent(DemoShellComponent);
    fixture.detectChanges();
    TestBed.inject(HttpTestingController).expectOne('/api/v1/health').flush({
      status: 'ok',
      service: 'Husky Tracking API',
      version: '0.1.0',
      demo_season: 'Demo season — Winter 2025–2026',
      demo_season_start: '2025-12-01',
      demo_season_end: '2026-03-31',
      demo_reference_date: '2026-03-31',
    });
    fixture.detectChanges();
    return { fixture, router };
  }

  it('renders mature operational navigation under demo routes', async () => {
    const { fixture } = await setup();
    expect(fixture.nativeElement.textContent).toContain('Dashboard');
    expect(fixture.nativeElement.textContent).toContain('Kennel Map');
    expect(fixture.nativeElement.textContent).toContain('Daily Plan');
    expect(fixture.nativeElement.textContent).toContain('Daily Entry');
    expect(fixture.nativeElement.textContent).toContain('Analytics');
    expect(fixture.nativeElement.textContent).toContain('Archive');
    expect(fixture.nativeElement.textContent).toContain('changes may reset');
    expect(fixture.nativeElement.textContent).toContain('Private demo session');
    expect(fixture.nativeElement.textContent).toContain('Do not enter real personal');
    const marks = fixture.nativeElement.querySelectorAll('.brand ht-brand-mark img, .mobile-brand ht-brand-mark img') as NodeListOf<HTMLImageElement>;
    expect(marks.length).toBe(2);
    for (const mark of marks) {
      expect(mark.getAttribute('src')).toBe('/brand-mark.png');
      expect(mark.getAttribute('alt')).toBe('');
    }
    const reset = fixture.nativeElement.querySelector('.workspace-reset') as HTMLButtonElement;
    reset.click();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('removes only your plans');
    expect(fixture.nativeElement.querySelector('a[href="/about"]')).not.toBeNull();
    expect(fixture.nativeElement.querySelectorAll('.desktop-sidebar .nav-mark svg').length).toBe(7);
    expect(fixture.nativeElement.querySelectorAll('.desktop-sidebar .nav-mark').item(0).textContent.trim()).toBe('');
    expect(fixture.nativeElement.querySelector('.desktop-sidebar .exit-link')?.getAttribute('aria-label')).toBe('Exit demo and return to Husky Tracking website');
  });

  it('keeps skip-link activation on dashboard and a deeper demo route', async () => {
    const { fixture, router } = await setup();
    for (const route of ['/demo/dashboard', '/demo/archive']) {
      await router.navigateByUrl(route);
      fixture.detectChanges();
      const skip = fixture.nativeElement.querySelector('.skip-link') as HTMLAnchorElement;
      const main = fixture.nativeElement.querySelector('#main-content') as HTMLElement;
      expect(skip.getAttribute('href')).toBe(`${route}#main-content`);
      skip.focus();
      expect(document.activeElement).toBe(skip);
      skip.click();
      expect(router.url).toBe(route);
      expect(document.activeElement).toBe(main);
    }
  });

  it('opens, closes, and navigates from the mobile drawer', async () => {
    const { fixture, router } = await setup();
    const trigger = fixture.nativeElement.querySelector('.menu-button') as HTMLButtonElement;
    trigger.click();
    await new Promise((resolve) => setTimeout(resolve, 0));
    fixture.detectChanges();

    expect(trigger.getAttribute('aria-expanded')).toBe('true');
    const archive = fixture.nativeElement.querySelector(
      '.mobile-drawer a[href="/demo/archive"]',
    ) as HTMLAnchorElement;
    archive.click();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(router.url).toBe('/demo/archive');
    expect(fixture.nativeElement.querySelector('.mobile-drawer')).toBeNull();
  });

  it('exits from the mobile drawer without resetting the demo workspace', async () => {
    const { fixture, router } = await setup();
    (fixture.nativeElement.querySelector('.menu-button') as HTMLButtonElement).click();
    fixture.detectChanges();
    const exit = fixture.nativeElement.querySelector('.mobile-drawer .exit-link') as HTMLAnchorElement;
    expect(exit).not.toBeNull();
    exit.click();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(router.url).toBe('/');
    expect(fixture.nativeElement.querySelector('.mobile-drawer')).toBeNull();
  });
});
