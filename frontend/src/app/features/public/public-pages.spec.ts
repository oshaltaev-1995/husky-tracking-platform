import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';

import { routes } from '../../app.routes';
import { DemoSessionService } from '../../core/api/demo-session.service';
import { AboutPageComponent } from './about/about-page.component';
import { ContactPageComponent } from './contact/contact-page.component';
import { FeaturesPageComponent } from './features/features-page.component';
import { HomePageComponent } from './home/home-page.component';
import { NotFoundPageComponent } from './not-found/not-found-page.component';
import { PrivacyPageComponent } from './privacy/privacy-page.component';
import { of } from 'rxjs';

describe('Public pages', () => {
  it('renders the positioning, disclosure, feature links, and demo CTA on Home', async () => {
    await TestBed.configureTestingModule({
      imports: [HomePageComponent],
      providers: [provideRouter([])],
    }).compileComponents();
    const fixture = TestBed.createComponent(HomePageComponent);
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('h1').textContent).toContain(
      'Sled-dog operations',
    );
    expect(fixture.nativeElement.textContent).toContain('entirely fictional kennel data');
    expect(fixture.nativeElement.querySelector('a[href="/demo/dashboard"]')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('a[href="/features"]')).not.toBeNull();
    expect(fixture.nativeElement.querySelectorAll('.feature-overview a').length).toBe(6);
    expect(fixture.nativeElement.textContent).not.toContain('Historical Records');
    expect(fixture.nativeElement.querySelector('.mini-brand img')?.getAttribute('src')).toBe('/brand-mark.png');
  });

  it('renders Features, About, and intentional Not Found content', async () => {
    await TestBed.configureTestingModule({
      imports: [FeaturesPageComponent, AboutPageComponent, NotFoundPageComponent],
      providers: [provideRouter([])],
    }).compileComponents();

    const features = TestBed.createComponent(FeaturesPageComponent);
    const about = TestBed.createComponent(AboutPageComponent);
    const notFound = TestBed.createComponent(NotFoundPageComponent);
    features.detectChanges();
    about.detectChanges();
    notFound.detectChanges();

    expect(features.nativeElement.textContent).toContain('Team Builder');
    expect(features.nativeElement.querySelector('a[href="/demo/analytics"]')).not.toBeNull();
    expect(about.nativeElement.textContent).toContain('independently developed demonstration');
    expect(about.nativeElement.textContent).toContain('Synthetic by design');
    expect(notFound.nativeElement.textContent).toContain('Page not found');
    expect(notFound.nativeElement.querySelector('a[href="/"]')).not.toBeNull();
  });

  it('validates Contact and keeps text on delivery failure', async () => {
    await TestBed.configureTestingModule({
      imports: [ContactPageComponent],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(ContactPageComponent);
    fixture.detectChanges();
    const submit = fixture.nativeElement.querySelector('button[type="submit"]') as HTMLButtonElement;
    submit.click();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelectorAll('.field-error').length).toBeGreaterThan(0);

    const component = fixture.componentInstance as unknown as {
      form: {
        setValue(value: Record<string, string>): void;
        controls: { message: { value: string } };
      };
    };
    component.form.setValue({
      name: 'Demo Visitor',
      email: 'visitor@example.com',
      company: '',
      subject: 'Project question',
      message: 'This is a sufficiently detailed project enquiry for the contact form.',
      website: '',
    });
    submit.click();
    TestBed.inject(HttpTestingController)
      .expectOne('/api/v1/contact')
      .flush({ detail: 'Unavailable' }, { status: 503, statusText: 'Unavailable' });
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('could not be delivered');
    expect(component.form.controls.message.value).toContain('sufficiently detailed');
  });

  it('shows Contact success and clears the completed form', async () => {
    await TestBed.configureTestingModule({
      imports: [ContactPageComponent],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(ContactPageComponent);
    fixture.detectChanges();
    const component = fixture.componentInstance as unknown as {
      form: {
        setValue(value: Record<string, string>): void;
        controls: { message: { value: string } };
      };
    };
    component.form.setValue({
      name: 'Demo Visitor',
      email: 'visitor@example.com',
      company: '',
      subject: 'Project question',
      message: 'This is a sufficiently detailed project enquiry for the contact form.',
      website: '',
    });
    fixture.nativeElement.querySelector('button[type="submit"]').click();
    TestBed.inject(HttpTestingController)
      .expectOne('/api/v1/contact')
      .flush({ accepted: true, message: 'Thanks — your message has been received.' });
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('your message has been received');
    expect(component.form.controls.message.value).toBe('');
  });

  it('renders plain-language privacy metadata from the public endpoint', async () => {
    await TestBed.configureTestingModule({
      imports: [PrivacyPageComponent],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    const fixture = TestBed.createComponent(PrivacyPageComponent);
    fixture.detectChanges();
    TestBed.inject(HttpTestingController).expectOne('/api/v1/public/privacy').flush({
      controller_name: 'Husky Tracking project operator',
      contact_email: 'privacy@example.com',
      controller_country: 'Finland',
      hosting_region: 'EEA',
      effective_date: '2026-09-18',
      mail_provider_name: 'Example Mail',
      mail_provider_region: 'EEA',
      demo_workspace_ttl_hours: 24,
    });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Anonymous demo workspace');
    expect(fixture.nativeElement.textContent).toContain('Cloudflare Email Routing');
    expect(fixture.nativeElement.textContent).toContain('delivered through Brevo');
    expect(fixture.nativeElement.textContent).not.toContain('before public launch');
    expect(fixture.nativeElement.textContent).not.toContain('deployment acceptance item');
    expect(fixture.nativeElement.textContent).toContain('privacy@example.com');
    expect(fixture.nativeElement.textContent).toContain('24 hours');
    for (const fragment of ['anonymous-demo', 'contact-form', 'technical-data', 'your-choices']) {
      expect(fixture.nativeElement.querySelector(`.privacy-index a[href="/privacy#${fragment}"]`)).not.toBeNull();
      expect(fixture.nativeElement.querySelector(`#${fragment}`)).not.toBeNull();
    }
  });
});

describe('Public and demo routing', () => {
  beforeEach(() => {
    const session = {
      expires_at: '2026-09-19T12:00:00Z',
      ttl_hours: 24,
      created: true,
      replaced_expired: false,
    };
    TestBed.configureTestingModule({
      providers: [
        provideRouter(routes),
        provideHttpClient(),
        { provide: DemoSessionService, useValue: { ensure: () => of(session), session: signal(session) } },
      ],
    });
  });

  it(
    'resolves canonical public and demo entries',
    async () => {
      const router = TestBed.inject(Router);
      await router.navigateByUrl('/');
      expect(router.url).toBe('/');
      await router.navigateByUrl('/features');
      expect(router.url).toBe('/features');
      await router.navigateByUrl('/about');
      expect(router.url).toBe('/about');
      await router.navigateByUrl('/contact');
      expect(router.url).toBe('/contact');
      await router.navigateByUrl('/privacy');
      expect(router.url).toBe('/privacy');
      await router.navigateByUrl('/privacy#technical-data');
      expect(router.url).toBe('/privacy#technical-data');
      await router.navigateByUrl('/demo');
      expect(router.url).toBe('/demo/dashboard');
    },
    20_000,
  );

  it('preserves path and query state through legacy redirects', async () => {
    const router = TestBed.inject(Router);
    await router.navigateByUrl('/dogs/example-id?tab=work');
    expect(router.url).toBe('/demo/dogs/example-id?tab=work');
    await router.navigateByUrl('/kennel?date=2026-02-10&layer=class');
    expect(router.url).toBe('/demo/kennel?date=2026-02-10&layer=class');
    await router.navigateByUrl('/analytics?from=2026-03-01&to=2026-03-31');
    expect(router.url).toBe('/demo/analytics?from=2026-03-01&to=2026-03-31');
  });

  it('keeps unknown URLs for the public 404 experience', async () => {
    const router = TestBed.inject(Router);
    await router.navigateByUrl('/not-a-real-page');
    expect(router.url).toBe('/not-a-real-page');
  });
});
