import { provideHttpClient } from '@angular/common/http';
import { HttpHeaders } from '@angular/common/http';
import { HttpTestingController } from '@angular/common/http/testing';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { vi } from 'vitest';

import { DemoSession, DemoSessionService } from '../../core/api/demo-session.service';
import { OperationsCapabilities, OperationsReview, ReviewCheck } from '../../core/api/operations.models';
import { OperationsReviewComponent } from './operations-review.component';

@Component({ template: '' })
class OtherPageComponent {}

const capabilities: OperationsCapabilities = {
  enabled: true, external_processing: true, providers: ['groq', 'openrouter'],
  selected_scenario: 'review_operations', season_start: '2025-12-01', season_end: '2026-03-31',
};

function currentSession(): DemoSession {
  return {
    active: true, expires_at: new Date(Date.now() + 3_600_000).toISOString(),
    ttl_hours: 1, ttl_seconds: 3600, created: false, replaced_expired: false,
  };
}

function result(): OperationsReview {
  const fact: ReviewCheck = {
    rule: 'ACTUAL_LEDGER', status: 'pass', explanation: 'Actual work only.',
    selected_date: '2026-03-31', entities: [{ kind: 'day', id: '2026-03-31' }], evidence_ids: ['e-actual'],
  };
  return {
    snapshot_id: '00000000-0000-0000-0000-000000000001', selected_date: '2026-03-31',
    captured_at: '2026-11-22T06:00:00Z', explanation: 'No saved teams exist for the selected day.',
    facts: [fact], findings: [{ ...fact, rule: 'SAVED_LINEUP', status: 'attention', explanation: 'No saved teams; a selected pool is not an arranged harness.' }],
    evidence: [{ id: 'e-actual', selected_date: '2026-03-31', entities: fact.entities,
      values: [{ name: 'sessions', value: 1, unit: 'count' }, { name: 'dog_starts', value: 8, unit: 'count' }, { name: 'dog_km', value: 80, unit: 'km' }] }],
    links: [
      { entity: { kind: 'day', id: '2026-03-31' }, label: 'Open Daily Plan', path: '/demo/daily?date=2026-03-31' },
      { entity: { kind: 'dog', id: '00000000-0000-0000-0000-000000000002' }, label: 'Atlas', path: '/demo/dogs/00000000-0000-0000-0000-000000000002?tab=work' },
    ],
    checked_rules: ['PLAN_PRESENCE', 'SAVED_LINEUP', 'ACTUAL_LEDGER'],
    status_counts: { passed: 4, violations: 0, attention: 1, unverified: 0 }, omitted_findings: 0,
    provider: 'groq', model: 'openai/gpt-oss-20b', fallback: false,
    http_calls: 2, tool_calls: 1,
    trace: [{ tool_name: 'validate_day', provider: 'groq', outcome: 'ok', elapsed_ms: 4 }],
    usage: { known_prompt_tokens: null, known_completion_tokens: null, incomplete: true },
  };
}

describe('OperationsReviewComponent', () => {
  let fixture: ComponentFixture<OperationsReviewComponent>;
  let http: HttpTestingController;
  let session: DemoSessionService;

  async function setup(enabled = true, hasSession = true, capabilitiesAvailable = true) {
    await TestBed.configureTestingModule({
      imports: [OperationsReviewComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([{ path: 'elsewhere', component: OtherPageComponent }])],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    session = TestBed.inject(DemoSessionService);
    session.session.set(hasSession ? currentSession() : null);
    fixture = TestBed.createComponent(OperationsReviewComponent);
    document.body.append(fixture.nativeElement);
    fixture.componentRef.setInput('selectedDate', '2026-03-31');
    fixture.detectChanges();
    const availability = http.expectOne('/api/v1/operations/capabilities');
    if (capabilitiesAvailable) {
      availability.flush({ ...capabilities, enabled, external_processing: enabled, providers: enabled ? capabilities.providers : [] });
    } else {
      availability.flush({}, { status: 503, statusText: 'Unavailable' });
    }
    fixture.detectChanges();
    return fixture;
  }

  function button(text: string): HTMLButtonElement {
    const found = Array.from(fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>)
      .find((item) => item.textContent.trim() === text);
    if (!found) throw new Error(`Missing button: ${text}`);
    return found;
  }

  function start() {
    button('Review operations').click();
    fixture.detectChanges();
    return http.expectOne('/api/v1/operations/review');
  }

  afterEach(() => {
    fixture?.destroy();
    fixture?.nativeElement.remove();
    http?.verify();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('reads public availability without starting a review, session or browser storage', async () => {
    const write = vi.spyOn(Storage.prototype, 'setItem');
    await setup();
    expect(fixture.nativeElement.textContent).toContain('31 March 2026');
    expect(fixture.nativeElement.textContent).toContain('Groq or the free OpenRouter reserve');
    http.expectNone('/api/v1/operations/review');
    http.expectNone('/api/v1/demo/session');
    expect(write).not.toHaveBeenCalled();
  });

  it('keeps a disabled feature explicit without blocking planning or creating a session', async () => {
    await setup(false, false);
    expect(fixture.nativeElement.textContent).toContain('AI review is not enabled');
    expect(fixture.nativeElement.querySelector('.review-actions')).toBeNull();
    http.expectNone('/api/v1/demo/session');
    http.expectNone('/api/v1/operations/review');
  });

  it('requires an existing current session without initializing a new one', async () => {
    await setup(true, false);
    expect(button('Review operations').disabled).toBe(true);
    expect(fixture.nativeElement.textContent).toContain('Open a current demo session');
    http.expectNone('/api/v1/demo/session');
  });

  it('handles an availability failure without starting a review and retries only when chosen', async () => {
    await setup(true, true, false);
    expect(fixture.nativeElement.textContent).toContain('Review availability could not be checked');
    http.expectNone('/api/v1/operations/capabilities');
    http.expectNone('/api/v1/operations/review');
    button('Check review availability').click(); fixture.detectChanges();
    http.expectOne('/api/v1/operations/capabilities').flush(capabilities); fixture.detectChanges();
    expect(button('Review operations').disabled).toBe(false);
    http.expectNone('/api/v1/operations/review');
  });

  it('sends only the selected date after an explicit click and prevents duplicate submission', async () => {
    await setup();
    const trigger = button('Review operations');
    trigger.click(); trigger.click();
    fixture.detectChanges();
    const request = http.expectOne('/api/v1/operations/review');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ selected_date: '2026-03-31' });
    expect(button('Reviewing…').disabled).toBe(true);
    expect(button('Cancel review').disabled).toBe(false);
    request.flush(result());
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Operations review ready');
    expect(fixture.nativeElement.textContent).toContain('Snapshot');
    expect(fixture.nativeElement.textContent).toContain('AI explanation');
    expect(fixture.nativeElement.textContent).toContain('Checked facts');
    expect(fixture.nativeElement.textContent).toContain('80 km');
    expect(fixture.nativeElement.textContent).toContain('not independently verified');
    http.expectNone('/api/v1/operations/review');
  });

  it('cancels the request, explains the remote limit and restores useful keyboard focus', async () => {
    await setup();
    const request = start();
    const reviewButton = button('Reviewing…');
    button('Cancel review').focus();
    button('Cancel review').click();
    // In the browser a microtask runs before Angular updates the disabled DOM.
    // Do not mask that race by rendering synchronously immediately after click.
    expect(reviewButton.disabled).toBe(true);
    await Promise.resolve();
    fixture.detectChanges();
    await fixture.whenStable();
    expect(request.cancelled).toBe(true);
    expect(fixture.nativeElement.textContent).toContain('Cancelling does not return provider quota');
    expect(document.activeElement).toBe(button('Review operations'));
    expect(fixture.nativeElement.querySelector('.review-result')).toBeNull();
    http.expectNone('/api/v1/operations/review');
  });

  it('restores focus after a response removes the focused Cancel control', async () => {
    await setup();
    const request = start();
    const reviewButton = button('Reviewing…');
    button('Cancel review').focus();
    request.flush(result());
    expect(reviewButton.disabled).toBe(true);
    await Promise.resolve();
    fixture.detectChanges();
    await fixture.whenStable();
    expect(document.activeElement).toBe(button('Review again'));
    expect(fixture.nativeElement.querySelector('.review-result')).not.toBeNull();
  });

  it('does not restore old focus after a newer date context has been selected', async () => {
    await setup();
    start();
    button('Cancel review').focus();
    button('Cancel review').click();
    fixture.componentRef.setInput('selectedDate', '2026-03-30');
    const otherControl = document.createElement('button');
    document.body.append(otherControl); otherControl.focus();
    fixture.detectChanges();
    await fixture.whenStable();
    expect(document.activeElement).toBe(otherControl);
    otherControl.remove();
  });

  it('does not run a queued focus restoration after destruction', async () => {
    await setup();
    start();
    const reviewButton = button('Reviewing…');
    button('Cancel review').focus();
    const focus = vi.spyOn(reviewButton, 'focus');
    button('Cancel review').click();
    fixture.destroy();
    await Promise.resolve();
    expect(focus).not.toHaveBeenCalled();
  });

  it('does not accept a late response after a date change, even before the cleanup effect runs', async () => {
    await setup();
    const request = start();
    fixture.componentRef.setInput('selectedDate', '2026-03-30');
    request.flush(result());
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.review-result')).toBeNull();
    expect(fixture.nativeElement.textContent).toContain('30 March 2026');
    http.expectNone('/api/v1/operations/review');
  });

  it('does not accept a late response after local session identity replacement', async () => {
    await setup();
    const request = start();
    session.session.set({ ...currentSession(), replaced_expired: true });
    request.flush(result());
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.review-result')).toBeNull();
    http.expectNone('/api/v1/operations/review');
  });

  for (const resetEvent of ['resetReviewOpened$', 'resetStarted$', 'replaced$'] as const) {
    it(`immediately invalidates active work on ${resetEvent} without replay`, async () => {
      await setup();
      const request = start();
      session[resetEvent].next();
      fixture.detectChanges();
      expect(request.cancelled).toBe(true);
      expect(fixture.nativeElement.querySelector('.review-result')).toBeNull();
      http.expectNone('/api/v1/operations/review');
    });
  }

  it('clears an existing result on Reset and route navigation', async () => {
    await setup();
    start().flush(result()); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.review-result')).not.toBeNull();
    session.resetStarted$.next(); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.review-result')).toBeNull();
    start().flush(result()); fixture.detectChanges();
    await TestBed.inject(Router).navigateByUrl('/elsewhere');
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.review-result')).toBeNull();
  });

  it('aborts active work on destruction', async () => {
    await setup();
    const request = start();
    fixture.destroy();
    expect(request.cancelled).toBe(true);
  });

  it('bounds the browser wait and never repeats a timed-out POST', async () => {
    await setup();
    vi.useFakeTimers();
    const request = start();
    vi.advanceTimersByTime(50_001); fixture.detectChanges();
    expect(request.cancelled).toBe(true);
    expect(fixture.nativeElement.querySelector('[role="alert"]')?.textContent).toContain('review timed out');
    expect(button('Review again').disabled).toBe(false);
    expect(fixture.nativeElement.querySelector('.review-result')).toBeNull();
    http.expectNone('/api/v1/operations/review');
  });

  it('rejects an API response for a different date', async () => {
    await setup();
    start().flush({ ...result(), selected_date: '2026-03-30' });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('did not match this day');
    expect(fixture.nativeElement.querySelector('.review-result')).toBeNull();
  });

  it('renders model text safely, uses local links with query state and explains unknown usage', async () => {
    await setup();
    const response = result();
    response.explanation = '<img src=x onerror="alert(1)"> Untrusted text';
    response.evidence[0].values.push({ name: 'roles', value: 'lead,team,wheel', unit: 'state' });
    response.links.push({ entity: { kind: 'day', id: '2026-03-31' }, label: 'External', path: 'https://untrusted.example' });
    start().flush(response); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.model-explanation img')).toBeNull();
    expect(fixture.nativeElement.querySelector('.model-explanation')?.textContent).toContain('<img');
    const planLink = fixture.nativeElement.querySelector('.review-links a') as HTMLAnchorElement;
    expect(planLink.getAttribute('href')).toBe('/demo/daily?date=2026-03-31');
    expect(fixture.nativeElement.querySelector('.review-links')?.textContent).not.toContain('External');
    expect(fixture.nativeElement.textContent).toContain('Token usage was not reported');
    expect(fixture.nativeElement.textContent).not.toContain('0 input tokens');
    expect(fixture.nativeElement.textContent).toContain('Lead · Team · Wheel');
    expect(fixture.nativeElement.textContent).not.toContain(response.snapshot_id);
  });

  it('shows reserve/tool trace, incomplete known usage and omitted findings honestly', async () => {
    await setup();
    start().flush({ ...result(), fallback: true, provider: 'openrouter', model: 'openai/gpt-oss-20b:free', omitted_findings: 2,
      usage: { known_prompt_tokens: 25, known_completion_tokens: null, incomplete: true } });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Free reserve used');
    expect(fixture.nativeElement.textContent).toContain('same snapshot');
    expect(fixture.nativeElement.textContent).toContain('Validate the selected day');
    expect(fixture.nativeElement.textContent).toContain('totals are incomplete');
    expect(fixture.nativeElement.textContent).toContain('2 additional findings');
    expect(fixture.nativeElement.querySelector('details summary')).not.toBeNull();
  });

  it('keeps the findings summary compact and identifies dog details from trusted links', async () => {
    await setup();
    const response = result();
    const dog = { kind: 'dog' as const, id: '00000000-0000-0000-0000-000000000002' };
    response.findings = [{ ...response.findings[0], rule: 'DOG_STATE', status: 'unverified', entities: [dog], evidence_ids: ['dog-state'] }];
    response.evidence.push({ id: 'dog-state', selected_date: response.selected_date, entities: [dog], values: [{ name: 'availability', value: 'retired', unit: 'state' }] });
    response.status_counts = { passed: 4, violations: 0, attention: 0, unverified: 1 };
    response.omitted_findings = 3;
    start().flush(response); fixture.detectChanges();
    const details = fixture.nativeElement.querySelector('.finding-details') as HTMLDetailsElement;
    expect(details.open).toBe(false);
    expect(details.querySelector('summary')?.textContent).toContain('View 1 detailed finding');
    expect(fixture.nativeElement.querySelector('.findings > header')?.textContent).toContain('0 issues · 0 attention · 1 not verified');
    expect(fixture.nativeElement.querySelector('.checked-facts')?.textContent).toContain('80 km');
    expect(fixture.nativeElement.querySelector('.findings > .review-message')?.textContent).toContain('3 additional findings');
    expect(details.querySelectorAll('.finding').length).toBe(1);
    expect(details.querySelector('h5')?.textContent).toBe('Dog state · Atlas');
    expect(details.querySelector('dd')?.textContent).toContain('retired');
    details.querySelector('summary')?.click();
    expect(details.open).toBe(true);
    http.expectNone('/api/v1/operations/review');
  });

  const failures = [
    ['app_rate_limited', 'Too many reviews'],
    ['ai_quota_exhausted', 'Both free AI routes'],
    ['ai_temporarily_unavailable', 'temporarily unavailable'],
    ['timeout', 'time limit'],
    ['invalid_provider_response', 'could not be validated'],
    ['session_expired', 'session expired'],
    ['provider_payment_required', 'No paid request'],
  ];
  for (const [code, text] of failures) {
    it(`shows a controlled ${code} failure and never retries automatically`, async () => {
      await setup();
      start().flush({ detail: { code, message: '<script>secret provider details</script>' } }, { status: code.includes('limited') || code.includes('quota') ? 429 : 503, statusText: 'Review unavailable' });
      fixture.detectChanges();
      expect(fixture.nativeElement.querySelector('[role="alert"]')?.textContent).toContain(text);
      expect(fixture.nativeElement.textContent).not.toContain('secret provider details');
      expect(fixture.nativeElement.querySelector('.review-result')).toBeNull();
      http.expectNone('/api/v1/operations/review');
    });
  }

  it('keeps Retry-After across date changes and offers only an explicit retry after waiting', async () => {
    await setup();
    vi.useFakeTimers();
    start().flush({ detail: { code: 'ai_quota_exhausted' } }, { status: 429, statusText: 'Too Many Requests', headers: new HttpHeaders({ 'Retry-After': '2' }) });
    fixture.detectChanges();
    expect(button('Review again').disabled).toBe(true);
    fixture.componentRef.setInput('selectedDate', '2026-03-30'); fixture.detectChanges();
    expect(button('Review operations').disabled).toBe(true);
    vi.advanceTimersByTime(2001); fixture.detectChanges();
    expect(button('Review operations').disabled).toBe(false);
    http.expectNone('/api/v1/operations/review');
    button('Review operations').click(); fixture.detectChanges();
    const request = http.expectOne('/api/v1/operations/review');
    expect(request.request.body).toEqual({ selected_date: '2026-03-30' });
    request.flush({ ...result(), selected_date: '2026-03-30' }); fixture.detectChanges();
  });

  it('waits locally after a generic ingress 429 without replay or date/Reset bypass', async () => {
    await setup();
    vi.useFakeTimers();
    start().flush({ detail: 'Too many requests' }, { status: 429, statusText: 'Too Many Requests' });
    fixture.detectChanges();
    expect(button('Review again').disabled).toBe(true);
    expect(fixture.nativeElement.querySelector('[role="alert"]')?.textContent).toContain('Too many reviews');
    fixture.componentRef.setInput('selectedDate', '2026-03-30');
    session.resetStarted$.next(); fixture.detectChanges();
    expect(button('Review operations').disabled).toBe(true);
    vi.advanceTimersByTime(29_999); fixture.detectChanges();
    expect(button('Review operations').disabled).toBe(true);
    vi.advanceTimersByTime(2); fixture.detectChanges();
    expect(button('Review operations').disabled).toBe(false);
    http.expectNone('/api/v1/operations/review');
  });

  it('honors explicit zero Retry-After before a body hint without automatic retry', async () => {
    await setup();
    start().flush({ detail: { code: 'review_busy', retry_after_seconds: 60 } }, {
      status: 429, statusText: 'Too Many Requests', headers: new HttpHeaders({ 'Retry-After': '0' }),
    });
    fixture.detectChanges();
    expect(button('Review again').disabled).toBe(false);
    expect(fixture.nativeElement.textContent).not.toContain('You can start another review after');
    http.expectNone('/api/v1/operations/review');
  });

  it('uses a valid body hint when Retry-After is malformed', async () => {
    await setup();
    vi.useFakeTimers();
    start().flush({ detail: { code: 'review_busy', retry_after_seconds: 2 } }, {
      status: 429, statusText: 'Too Many Requests', headers: new HttpHeaders({ 'Retry-After': 'invalid' }),
    });
    fixture.detectChanges();
    expect(button('Review again').disabled).toBe(true);
    vi.advanceTimersByTime(2001); fixture.detectChanges();
    expect(button('Review again').disabled).toBe(false);
    http.expectNone('/api/v1/operations/review');
  });

  it('invalidates the request and result when the current session expires', async () => {
    await setup();
    vi.useFakeTimers();
    session.session.set({ ...currentSession(), expires_at: new Date(Date.now() + 1000).toISOString() });
    fixture.detectChanges();
    const request = start();
    vi.advanceTimersByTime(1001); fixture.detectChanges();
    expect(request.cancelled).toBe(true);
    expect(button('Review operations').disabled).toBe(true);
    expect(fixture.nativeElement.textContent).toContain('session expired');
  });

  it('prevents a review while a saved-data editor is busy', async () => {
    await setup();
    fixture.componentRef.setInput('blocked', true); fixture.detectChanges();
    expect(button('Review operations').disabled).toBe(true);
    expect(fixture.nativeElement.textContent).toContain('Finish the current edit');
    http.expectNone('/api/v1/operations/review');
  });
});
