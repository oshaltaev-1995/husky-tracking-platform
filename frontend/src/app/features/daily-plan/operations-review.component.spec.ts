import { provideHttpClient } from '@angular/common/http';
import { HttpHeaders } from '@angular/common/http';
import { HttpTestingController } from '@angular/common/http/testing';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { Component, signal, WritableSignal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { vi } from 'vitest';

import { DemoSession, DemoSessionService } from '../../core/api/demo-session.service';
import { OperationsCapabilities, OperationsReview, ReviewCheck } from '../../core/api/operations.models';
import { OperationsReviewComponent } from './operations-review.component';

@Component({ template: '' })
class OtherPageComponent {}

const capabilities: OperationsCapabilities = {
  enabled: true, external_processing: true, providers: ['groq'],
  selected_scenario: 'review_operations', season_start: '2025-12-01', season_end: '2026-03-31',
};

function currentSession(): DemoSession {
  return {
    active: true, expires_at: new Date(Date.now() + 3_600_000).toISOString(),
    ttl_hours: 1, ttl_seconds: 3600, created: false, replaced_expired: false,
  };
}

const dogs = ['Atlas', 'Aurora', 'Clover', 'Cosmo'].map((label, index) => ({
  entity: { kind: 'dog' as const, id: `00000000-0000-0000-0000-${String(index + 2).padStart(12, '0')}` },
  label,
  path: `/demo/dogs/00000000-0000-0000-0000-${String(index + 2).padStart(12, '0')}?tab=work`,
}));

function result(): OperationsReview {
  const fact: ReviewCheck = {
    rule: 'ACTUAL_LEDGER', status: 'pass', explanation: 'Actual work only.',
    selected_date: '2026-03-31', entities: [{ kind: 'day', id: '2026-03-31' }], evidence_ids: ['e-actual'],
  };
  return {
    snapshot_id: '00000000-0000-0000-0000-000000000001', selected_date: '2026-03-31',
    captured_at: '2026-11-22T06:00:00Z', explanation: 'No saved teams exist for the selected day.',
    presentation: { status: 'ready', message: null, segments: [{ text: 'No saved teams exist for the selected day.', entity: null, path: null }] },
    summary: { plan_exists: true, activity_count: 1, selected_unique_dogs: 4, selected_participations: 4,
      activities: [{ entity: { kind: 'activity', id: '00000000-0000-0000-0000-000000000010' }, kind: 'training', distance_km: 5, selected_pool_count: 4, selected_dogs: dogs, omitted_selected_dogs: 0, saved_teams: 0, actual_status: 'not_recorded' }],
      omitted_activities: 0, actual: { sessions: 1, dogs_worked: 8, dog_starts: 8, dog_km: 80 } },
    finding_groups: [{ scope: 'plan', findings: [{ ...fact, rule: 'SAVED_LINEUP', status: 'attention', explanation: 'No saved teams; a selected pool is not an arranged harness.' }], status_counts: { passed: 4, violations: 0, attention: 1, unverified: 0 }, omitted_findings: 0, links: [] },
      { scope: 'other_dogs', findings: [], status_counts: { passed: 0, violations: 0, attention: 0, unverified: 0 }, omitted_findings: 0, links: [] }],
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
    expect(fixture.nativeElement.textContent).toContain('processed by Groq');
    expect(fixture.nativeElement.textContent).not.toContain('OpenRouter');
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

  it('shows the counted internal quota retry without starting another review', async () => {
    await setup();
    const request = start();
    request.flush({ ...result(), http_calls: 3, quota_retries: 1 });
    fixture.detectChanges();
    const details = fixture.nativeElement.querySelector('.review-trace') as HTMLDetailsElement;
    expect(details.open).toBe(false);
    expect(details.textContent).toContain('3 model requests');
    expect(details.textContent).toContain('One short rate-limit response was retried');
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
    expect(fixture.nativeElement.textContent).toContain('one brief pause and retry');
    request.flush(result());
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Operations review ready');
    expect(fixture.nativeElement.textContent).toContain('Snapshot');
    expect(fixture.nativeElement.textContent).toContain('AI explanation');
    expect(fixture.nativeElement.textContent).toContain('Saved-day facts');
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

  it('clears completed facts and ready after a saved change, then reviews only on an explicit action', async () => {
    await setup();
    const savedVersion = signal(1);
    fixture.componentRef.setInput('savedContextVersion', savedVersion);
    fixture.detectChanges();
    const empty = result();
    empty.summary = { ...empty.summary, plan_exists: false, activity_count: 0,
      selected_unique_dogs: 0, selected_participations: 0, activities: [],
      actual: { sessions: 0, dogs_worked: 0, dog_starts: 0, dog_km: 0 } };
    start().flush(empty); fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Operations review ready.');
    expect(fixture.nativeElement.textContent).toContain('No saved plan for this date.');
    expect(fixture.nativeElement.textContent).toContain('Later changes are not included.');

    savedVersion.set(2); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.review-result')).toBeNull();
    expect(fixture.nativeElement.textContent).not.toContain('Operations review ready.');
    expect(fixture.nativeElement.textContent).not.toContain('No saved plan for this date.');
    expect(fixture.nativeElement.textContent).toContain('The saved day changed after this review. Review again to include your latest changes.');
    expect(button('Review again').disabled).toBe(false);
    savedVersion.set(3); fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('The saved day changed after this review.');
    http.expectNone('/api/v1/operations/review');

    button('Review again').click(); fixture.detectChanges();
    const fresh = http.expectOne('/api/v1/operations/review');
    expect(fresh.request.body).toEqual({ selected_date: '2026-03-31' });
    expect(fixture.nativeElement.textContent).not.toContain('The saved day changed after this review.');
    fresh.flush(result()); fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('4 selected dogs');
    expect(fixture.nativeElement.textContent).toContain('Operations review ready.');
    http.expectNone('/api/v1/operations/review');
  });

  it('rejects a stale saved-day response synchronously before the cleanup effect runs', async () => {
    await setup();
    const savedVersion = signal(1);
    fixture.componentRef.setInput('savedContextVersion', savedVersion);
    fixture.detectChanges();
    const request = start();
    savedVersion.set(2);
    request.flush(result());
    // Observe the acceptance boundary before rendering/effects can mask a late
    // acceptance by clearing it again. The parent signal is already current.
    const state = fixture.componentInstance as unknown as {
      result: WritableSignal<OperationsReview | null>; notice: WritableSignal<string>;
    };
    expect(state.result()).toBeNull();
    expect(state.notice()).not.toContain('ready');
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.review-result')).toBeNull();
    expect(fixture.nativeElement.textContent).toContain('The saved day changed after this review.');
    expect(button('Review again').disabled).toBe(false);
    http.expectNone('/api/v1/operations/review');
  });

  it('cancels a pending generation on a saved change without accepting or replaying it', async () => {
    await setup();
    const savedVersion = signal(1);
    fixture.componentRef.setInput('savedContextVersion', savedVersion);
    fixture.detectChanges();
    const request = start();
    savedVersion.set(2); fixture.detectChanges();
    expect(request.cancelled).toBe(true);
    expect(fixture.nativeElement.textContent).not.toContain('Reviewing…');
    expect(fixture.nativeElement.textContent).toContain('The saved day changed after this review.');
    http.expectNone('/api/v1/operations/review');
  });

  it('preserves known Retry-After across saved changes and waits for manual Review again', async () => {
    await setup();
    const savedVersion = signal(1);
    fixture.componentRef.setInput('savedContextVersion', savedVersion);
    fixture.detectChanges();
    vi.useFakeTimers();
    start().flush({ detail: { code: 'ai_quota_exhausted' } }, {
      status: 429, statusText: 'Too Many Requests', headers: new HttpHeaders({ 'Retry-After': '2' }),
    });
    fixture.detectChanges();
    savedVersion.set(2); fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('The saved day changed after this review.');
    expect(fixture.nativeElement.textContent).toContain('You can start another review after');
    expect(button('Review again').disabled).toBe(true);
    vi.advanceTimersByTime(1500);
    savedVersion.set(3); fixture.detectChanges();
    expect(button('Review again').disabled).toBe(true);
    vi.advanceTimersByTime(501); fixture.detectChanges();
    expect(button('Review again').disabled).toBe(false);
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
    response.explanation = 'This raw model field must not be rendered';
    response.presentation.segments = [{ text: '<img src=x onerror="alert(1)"> Untrusted text', entity: null, path: null }];
    response.evidence[0].values.push({ name: 'roles', value: 'lead,team,wheel', unit: 'state' });
    response.links.push({ entity: { kind: 'day', id: '2026-03-31' }, label: 'External', path: 'https://untrusted.example' });
    start().flush(response); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.model-explanation img')).toBeNull();
    expect(fixture.nativeElement.querySelector('.model-explanation')?.textContent).toContain('<img');
    const planLink = fixture.nativeElement.querySelector('.review-links a') as HTMLAnchorElement;
    expect(planLink.getAttribute('href')).toBe('/demo/daily?date=2026-03-31');
    expect(fixture.nativeElement.querySelector('[aria-label="Related operational screens"]')?.textContent).not.toContain('External');
    expect(fixture.nativeElement.textContent).toContain('Token usage was not reported');
    expect(fixture.nativeElement.textContent).not.toContain('0 input tokens');
    expect(fixture.nativeElement.textContent).toContain('Lead · Team · Wheel');
    expect(fixture.nativeElement.textContent).not.toContain(response.snapshot_id);
  });

  it('shows reserve/tool trace, incomplete known usage and omitted findings honestly', async () => {
    await setup();
    const response = result(); response.finding_groups[0].omitted_findings = 2;
    start().flush({ ...response, fallback: true, provider: 'openrouter', model: 'particle-ai/particle-1:free', omitted_findings: 2,
      usage: { known_prompt_tokens: 25, known_completion_tokens: null, incomplete: true } });
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.review-trace')?.textContent).toContain('OpenRouter');
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
    response.finding_groups[0] = { scope: 'plan', findings: response.findings, status_counts: response.status_counts, omitted_findings: 3, links: [] };
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
    ['ai_quota_exhausted', 'AI review is currently rate or quota limited'],
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
  it('shows four linked names and saved pool, teams and actual facts without raw UUID prose', async () => {
    await setup();
    const response = result();
    response.explanation = `Four eligible dogs (IDs ${dogs.map((dog) => dog.entity.id).join(', ')}).`;
    response.presentation.segments = [
      { text: 'Four eligible dogs (', entity: null, path: null },
      ...dogs.flatMap((dog, index) => [
        { text: dog.label, entity: dog.entity, path: dog.path },
        { text: index === dogs.length - 1 ? '). ' : ', ', entity: null, path: null },
      ]),
      { text: 'Atlas', entity: dogs[0].entity, path: dogs[0].path },
      { text: ' is selected.', entity: null, path: null },
    ];
    response.summary.actual = { sessions: 0, dogs_worked: 0, dog_starts: 0, dog_km: 0 };
    start().flush(response); fixture.detectChanges();
    const content = fixture.nativeElement as HTMLElement;
    expect(content.textContent).toContain('Training · 5 km');
    expect(content.textContent).toContain('4 selected dogs');
    expect(content.textContent).toContain('Not saved');
    expect(content.textContent).toContain('Not recorded');
    expect(content.textContent).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i);
    expect(content.querySelector('.model-explanation')?.textContent).not.toContain('IDs Atlas');
    expect(content.querySelector('.model-explanation > p')?.textContent).toBe(response.presentation.segments.map((segment) => segment.text).join(''));
    for (const [index, dog] of dogs.entries()) {
      const links = [...content.querySelectorAll<HTMLAnchorElement>('.selected-dogs a, .model-explanation a')].filter((link) => link.textContent?.trim() === dog.label);
      expect(links.length).toBe(index === 0 ? 3 : 2);
      expect(links.every((link) => link.getAttribute('href') === dog.path)).toBe(true);
      expect(links.every((link) => !link.hasAttribute('aria-label'))).toBe(true);
    }
    expect(content.querySelector('.review-links')?.textContent).not.toContain('Atlas');
    expect(content.querySelector('.review-trace')?.hasAttribute('open')).toBe(false);
    http.expectNone('/api/v1/operations/review');
  });

  it('retains saved facts but does not claim an unresolved AI explanation is ready', async () => {
    await setup();
    const response = result();
    response.explanation = 'Do not display this raw provider value';
    response.presentation = { status: 'unresolved', message: 'untrusted detail must not be rendered', segments: [] };
    start().flush(response); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.model-explanation')?.textContent).toContain('unresolved reference');
    expect(fixture.nativeElement.textContent).toContain('Saved-day facts are ready');
    expect(fixture.nativeElement.textContent).not.toContain('Operations review ready.');
    expect(fixture.nativeElement.textContent).not.toContain(response.explanation);
    expect(fixture.nativeElement.textContent).not.toContain(response.presentation.message);
    expect(fixture.nativeElement.querySelector('.checked-facts')?.textContent).toContain('Training');
    http.expectNone('/api/v1/operations/review');
  });

  for (const malformed of ['unknown_uuid', 'unsafe_path', 'wrong_identity']) {
    it(`rejects a malformed ${malformed} presentation without exposing raw prose or retrying`, async () => {
      await setup();
      const response = result();
      response.presentation.segments = malformed === 'unknown_uuid'
        ? [{ text: 'Unknown 11111111-1111-1111-1111-111111111111', entity: null, path: null }]
        : [{ text: 'Atlas', entity: dogs[0].entity, path: malformed === 'unsafe_path' ? 'https://untrusted.example/dog' : dogs[1].path }];
      start().flush(response); fixture.detectChanges();
      expect(fixture.nativeElement.querySelector('.model-explanation')?.textContent).toContain('unresolved reference');
      expect(fixture.nativeElement.textContent).not.toContain('11111111-1111-1111-1111-111111111111');
      http.expectNone('/api/v1/operations/review');
    });
  }

  it('keeps duplicate, long Cyrillic and HTML-like labels escaped with distinct identity links', async () => {
    await setup();
    const response = result();
    const names = ['Atlas · A1-01', 'Atlas · B1-01', 'Снежный ветер из северной долины', '<b>Bright snow</b>'];
    const links = dogs.map((dog, index) => ({ ...dog, label: names[index] }));
    response.summary.activities[0].selected_dogs = links;
    response.presentation.segments = links.flatMap((dog) => [{ text: dog.label, entity: dog.entity, path: dog.path }, { text: ' ', entity: null, path: null }]);
    start().flush(response); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.model-explanation b')).toBeNull();
    expect(fixture.nativeElement.querySelector('.selected-dogs b')).toBeNull();
    for (const [index, name] of names.entries()) {
      const link = fixture.nativeElement.querySelectorAll('.selected-dogs a')[index] as HTMLAnchorElement;
      expect(link.textContent?.trim()).toBe(name); expect(link.getAttribute('href')).toBe(dogs[index].path);
    }
    expect(fixture.nativeElement.querySelector('.model-explanation')?.textContent).toContain('<b>Bright snow</b>');
    http.expectNone('/api/v1/operations/review');
  });

  it('separates unrelated archive findings and preserves full scoped counts and omissions', async () => {
    await setup();
    const response = result();
    const archived = { entity: { kind: 'dog' as const, id: '00000000-0000-0000-0000-000000000060' }, label: 'Coast', path: '/demo/dogs/00000000-0000-0000-0000-000000000060?tab=work' };
    response.finding_groups[1] = { scope: 'other_dogs', findings: [{ ...response.findings[0], rule: 'DOG_STATE', status: 'unverified', entities: [archived.entity] }], status_counts: { passed: 0, violations: 0, attention: 0, unverified: 10 }, omitted_findings: 9, links: [archived] };
    start().flush(response); fixture.detectChanges();
    const main = fixture.nativeElement.querySelector('.findings:not(.other-dog-findings)');
    const other = fixture.nativeElement.querySelector('.other-dog-findings');
    expect(main.textContent).not.toContain('Coast');
    expect(other.textContent).toContain('Other dogs in this snapshot');
    expect(other.textContent).toContain('10 not verified');
    expect(other.textContent).toContain('9 additional findings');
    expect(other.querySelector('details').open).toBe(false);
    expect(other.querySelector('a').getAttribute('href')).toBe(archived.path);
    expect(fixture.nativeElement.querySelector('[aria-label="Related operational screens"]')?.textContent).not.toContain('Coast');
    http.expectNone('/api/v1/operations/review');
  });

  it('distinguishes an empty plan, repeated participants, saved teams and recorded actual truth', async () => {
    await setup();
    const response = result();
    response.summary = { ...response.summary, plan_exists: false, activities: [], activity_count: 0, selected_unique_dogs: 0, selected_participations: 0, actual: { sessions: 2, dogs_worked: 16, dog_starts: 16, dog_km: 120 } };
    start().flush(response); fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No saved plan for this date.');
    expect(fixture.nativeElement.querySelector('.actual-summary')?.textContent).toContain('120 km');
    button('Review again').click(); fixture.detectChanges();
    const request = http.expectOne('/api/v1/operations/review');
    const next = result();
    const activity = next.summary.activities[0];
    next.summary.activities = [{ ...activity, saved_teams: 1, actual_status: 'matches_plan' }, { ...activity, entity: { kind: 'activity', id: '00000000-0000-0000-0000-000000000011' } }];
    next.summary.activity_count = 2; next.summary.selected_participations = 8;
    request.flush(next); fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('4 unique dogs · 8 planned participations across 2 activities');
    expect(fixture.nativeElement.textContent).toContain('Recorded · matches plan');
    expect(fixture.nativeElement.querySelectorAll('.activity-summary').length).toBe(2);
    http.expectNone('/api/v1/operations/review');
  });

});
