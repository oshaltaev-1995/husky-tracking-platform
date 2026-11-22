import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { vi } from 'vitest';

import { PrivacyPageComponent } from './privacy-page.component';

const metadata = {
  controller_name: 'Synthetic project operator',
  controller_country: 'Finland',
  contact_email: 'privacy@example.com',
  hosting_region: 'Netherlands / EEA',
  effective_date: '2026-11-21',
  mail_provider_name: 'Example Mail',
  mail_provider_region: 'EEA',
  demo_workspace_ttl_hours: 72,
};

describe('Privacy workspace disclosure', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PrivacyPageComponent],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
  });

  afterEach(() => {
    TestBed.inject(HttpTestingController).verify();
    vi.restoreAllMocks();
  });

  it('names the necessary cookie, edits and exact Reset behaviour without introducing AI processing', () => {
    const fixture = TestBed.createComponent(PrivacyPageComponent);
    fixture.detectChanges();
    TestBed.inject(HttpTestingController).expectOne('/api/v1/public/privacy').flush(metadata);
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('ht_demo_session');
    expect(text).toContain('notes, and temporary housing moves');
    expect(text).toContain('does not delete the cookie or extend its existing expiry');
    expect(text).toContain('No advertising or analytics tracking');
    expect(text).toContain('no localStorage, sessionStorage, IndexedDB');
    expect(text).not.toMatch(/Groq|OpenRouter/);
    expect(fixture.nativeElement.querySelector('[role="dialog"]')).toBeNull();
  });

  it('uses the runtime lifetime and only reads the public metadata without session or storage writes', () => {
    const storageWrite = vi.spyOn(Storage.prototype, 'setItem');
    const cookieBefore = document.cookie;
    const fixture = TestBed.createComponent(PrivacyPageComponent);
    fixture.detectChanges();
    const http = TestBed.inject(HttpTestingController);
    const requests = http.match(() => true);
    expect(requests.map((request) => [request.request.method, request.request.url])).toEqual([
      ['GET', '/api/v1/public/privacy'],
    ]);
    requests[0].flush(metadata);
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('72 hours');
    expect(text).not.toContain('24 hours');
    expect(document.cookie).toBe(cookieBefore);
    expect(storageWrite).not.toHaveBeenCalled();
    http.expectNone((request) => request.url.startsWith('/api/v1/demo/'));
  });

  it('does not invent a fixed lifetime when public metadata is unavailable', () => {
    const fixture = TestBed.createComponent(PrivacyPageComponent);
    fixture.detectChanges();
    TestBed.inject(HttpTestingController).expectOne('/api/v1/public/privacy')
      .flush(null, { status: 503, statusText: 'Unavailable' });
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).not.toContain('24 hours');
    expect(text).not.toContain('72 hours');
    expect(text).toContain('configured demo lifetime');
    TestBed.inject(HttpTestingController)
      .expectNone((request) => request.url.startsWith('/api/v1/demo/'));
  });

  it('describes only active Groq processing when the feature is enabled', () => {
    const fixture = TestBed.createComponent(PrivacyPageComponent);
    fixture.detectChanges();
    TestBed.inject(HttpTestingController).expectOne('/api/v1/public/privacy')
      .flush({ ...metadata, operations_review_enabled: true, operations_review_providers: ['groq'] });
    fixture.detectChanges();
    const text = fixture.nativeElement.querySelector('#operations-review')?.textContent ?? '';
    expect(text).toContain('Groq');
    expect(text).not.toContain('OpenRouter');
    expect(text).toContain('Free-text notes, Contact messages');
    expect(text).toContain('do not guarantee zero retention or EEA-only');
    expect(text).toContain('A request already sent may still finish');
    TestBed.inject(HttpTestingController).expectNone((request) => request.url.startsWith('/api/v1/demo/'));
  });

  it('discloses the optional reserve only when the server explicitly activates it', () => {
    const fixture = TestBed.createComponent(PrivacyPageComponent);
    fixture.detectChanges();
    TestBed.inject(HttpTestingController).expectOne('/api/v1/public/privacy')
      .flush({ ...metadata, operations_review_enabled: true, operations_review_providers: ['groq', 'openrouter'] });
    fixture.detectChanges();
    const text = fixture.nativeElement.querySelector('#operations-review')?.textContent ?? '';
    expect(text).toContain('Groq');
    expect(text).toContain('OpenRouter as a free reserve');
    expect(text).toContain('data collection denial');
    TestBed.inject(HttpTestingController).expectNone((request) => request.url.startsWith('/api/v1/demo/'));
  });

});
