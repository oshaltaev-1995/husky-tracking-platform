import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';

import { PublicShellComponent } from './public-shell.component';

@Component({ template: '<h1>Public page</h1>' })
class PublicPageComponent {}

describe('PublicShellComponent', () => {
  it('keeps skip-link activation on every public route and focuses the current main region', async () => {
    await TestBed.configureTestingModule({
      imports: [PublicShellComponent],
      providers: [provideRouter([{
        path: '',
        component: PublicShellComponent,
        children: ['', 'about', 'features', 'contact', 'privacy'].map((path) => ({
          path,
          component: PublicPageComponent,
        })),
      }])],
    }).compileComponents();
    const router = TestBed.inject(Router);
    const fixture = TestBed.createComponent(PublicShellComponent);
    for (const route of ['/', '/about', '/features', '/contact', '/privacy']) {
      await router.navigateByUrl(route);
      fixture.detectChanges();
      const skip = fixture.nativeElement.querySelector('.public-skip-link') as HTMLAnchorElement;
      const main = fixture.nativeElement.querySelector('#public-content') as HTMLElement;
      expect(skip.getAttribute('href')).toBe(`${route}#public-content`);
      skip.focus();
      expect(document.activeElement).toBe(skip);
      skip.click();
      expect(router.url).toBe(route);
      expect(document.activeElement).toBe(main);
    }
  });

  it('renders public navigation without the operational sidebar', async () => {
    await TestBed.configureTestingModule({
      imports: [PublicShellComponent],
      providers: [
        provideRouter([
          {
            path: '',
            component: PublicShellComponent,
            children: [
              { path: '', component: PublicPageComponent },
              { path: 'features', component: PublicPageComponent },
            ],
          },
          { path: 'demo/dashboard', component: PublicPageComponent },
        ]),
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(PublicShellComponent);
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('a[href="/features"]')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('a[href="/demo/dashboard"]')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('.desktop-sidebar')).toBeNull();
    const marks = fixture.nativeElement.querySelectorAll('.public-brand ht-brand-mark img') as NodeListOf<HTMLImageElement>;
    expect(marks.length).toBe(2);
    for (const mark of marks) {
      expect(mark.getAttribute('src')).toBe('/brand-mark.png');
      expect(mark.getAttribute('alt')).toBe('');
    }
  });

  it('supports accessible mobile open, Escape close, and navigation close', async () => {
    await TestBed.configureTestingModule({
      imports: [PublicShellComponent],
      providers: [
        provideRouter([
          { path: 'features', component: PublicPageComponent },
          { path: 'demo/dashboard', component: PublicPageComponent },
        ]),
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(PublicShellComponent);
    fixture.detectChanges();
    const trigger = fixture.nativeElement.querySelector(
      '.public-menu-button',
    ) as HTMLButtonElement;
    trigger.click();
    await new Promise((resolve) => setTimeout(resolve, 0));
    fixture.detectChanges();
    expect(trigger.getAttribute('aria-expanded')).toBe('true');

    const menu = fixture.nativeElement.querySelector('.public-mobile-menu') as HTMLElement;
    menu.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.public-mobile-menu')).toBeNull();

    trigger.click();
    fixture.detectChanges();
    const features = fixture.nativeElement.querySelector(
      '.public-mobile-menu a[href="/features"]',
    ) as HTMLAnchorElement;
    features.click();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(TestBed.inject(Router).url).toBe('/features');
    expect(fixture.nativeElement.querySelector('.public-mobile-menu')).toBeNull();
  });
});
