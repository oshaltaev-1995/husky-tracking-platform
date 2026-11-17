import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { DemoSessionService } from './demo-session.service';

describe('DemoSessionService', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
  });

  afterEach(() => TestBed.inject(HttpTestingController).verify());

  it('initializes one opaque server session and retains expiry metadata', () => {
    const service = TestBed.inject(DemoSessionService);
    service.ensure().subscribe();
    service.ensure().subscribe();
    TestBed.inject(HttpTestingController).expectOne('/api/v1/demo/session').flush({
      active: true,
      expires_at: '2026-09-19T12:00:00Z',
      ttl_hours: 24,
      ttl_seconds: 86400,
      created: true,
      replaced_expired: false,
    });
    expect(service.session()?.ttl_seconds).toBe(86400);
  });

  it('resets only through the scoped demo endpoint', () => {
    const service = TestBed.inject(DemoSessionService);
    service.reset().subscribe();
    const request = TestBed.inject(HttpTestingController).expectOne('/api/v1/demo/reset');
    expect(request.request.method).toBe('POST');
    request.flush({ status: 'reset', expires_at: '2026-09-19T12:00:00Z' });
  });

  it('exposes a recognizable replacement state after server-side expiry', () => {
    const service = TestBed.inject(DemoSessionService);
    service.recognizeReplacement('2026-09-20T12:00:00Z');
    expect(service.session()?.replaced_expired).toBe(true);
    expect(service.session()?.expires_at).toBe('2026-09-20T12:00:00Z');
  });

  it('explicitly reinitializes a cached but invalid browser session without replaying writes', () => {
    const service = TestBed.inject(DemoSessionService);
    const http = TestBed.inject(HttpTestingController);
    const session = {
      active: true,
      expires_at: '2099-01-01T00:00:00Z',
      ttl_hours: 24,
      ttl_seconds: 86400,
      created: false,
      replaced_expired: false,
    };
    service.ensure().subscribe();
    http.expectOne('/api/v1/demo/session').flush(session);
    service.ensure().subscribe();
    http.expectNone('/api/v1/demo/session');

    service.reinitialize().subscribe();
    const replacement = http.expectOne('/api/v1/demo/session');
    expect(replacement.request.method).toBe('GET');
    replacement.flush({ ...session, created: true, replaced_expired: true });
    expect(service.session()?.replaced_expired).toBe(true);
    service.ensure().subscribe();
    http.expectNone('/api/v1/demo/session');
    http.expectNone((request) => request.method !== 'GET');
  });

  it('announces reset start and completion only around the scoped API response', () => {
    const service = TestBed.inject(DemoSessionService);
    const events: string[] = [];
    service.resetStarted$.subscribe(() => events.push('started'));
    service.resetCompleted$.subscribe(() => events.push('completed'));
    service.resetFailed$.subscribe(() => events.push('failed'));
    service.reset().subscribe();
    expect(events).toEqual(['started']);
    TestBed.inject(HttpTestingController).expectOne('/api/v1/demo/reset')
      .flush({ status: 'reset', expires_at: '2099-01-01T00:00:00Z' });
    expect(events).toEqual(['started', 'completed']);
  });

  it('exposes failed reset so a suspended editor can reconcile without claiming success', () => {
    const service = TestBed.inject(DemoSessionService);
    const events: string[] = [];
    service.resetStarted$.subscribe(() => events.push('started'));
    service.resetCompleted$.subscribe(() => events.push('completed'));
    service.resetFailed$.subscribe(() => events.push('failed'));
    service.reset().subscribe({ error: () => events.push('subscriber error') });
    TestBed.inject(HttpTestingController).expectOne('/api/v1/demo/reset')
      .flush('offline', { status: 503, statusText: 'Unavailable' });
    expect(events).toEqual(['started', 'failed', 'subscriber error']);
  });
});
