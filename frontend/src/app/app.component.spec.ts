import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';

import { AppComponent } from './app.component';

@Component({ template: '<h1>Route content</h1>' })
class EmptyRouteComponent {}

describe('AppComponent', () => {
  it('hosts routed content without imposing either shell', async () => {
    await TestBed.configureTestingModule({
      imports: [AppComponent],
      providers: [provideRouter([{ path: '', component: EmptyRouteComponent }])],
    }).compileComponents();

    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    await TestBed.inject(Router).navigateByUrl('/');
    await fixture.whenStable();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Route content');
    expect(fixture.nativeElement.querySelector('.desktop-sidebar')).toBeNull();
  });
});
