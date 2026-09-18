import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';

import { PublicShellComponent } from './public-shell.component';

@Component({ template: '<h1>Public page</h1>' })
class PublicPageComponent {}

describe('PublicShellComponent', () => {
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
