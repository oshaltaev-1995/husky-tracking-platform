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
});
