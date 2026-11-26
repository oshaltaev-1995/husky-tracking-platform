import { DatePipe, DOCUMENT } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, DestroyRef, ElementRef, Injector, afterNextRender, computed, effect, inject, input, signal, viewChild } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NavigationStart, Router, RouterLink } from '@angular/router';
import { Subscription, filter, timeout } from 'rxjs';

import { DemoSession, DemoSessionService } from '../../core/api/demo-session.service';
import { OperationsCapabilities, OperationsReview, ReviewCheck, ReviewEvidence, ReviewLink, ReviewPresentationSegment, ReviewProvider, ReviewStatus } from '../../core/api/operations.models';
import { OperationsService } from '../../core/api/operations.service';

interface LocalLink { label: string; route: string; query: Record<string, string>; newTab: boolean }
interface DisplaySegment { text: string; link: Omit<LocalLink, 'label'> | null }
type ReviewActivity = OperationsReview['summary']['activities'][number];

// Detection only: the server resolves identities from its frozen snapshot. Keep
// the same bounded dash family as that boundary, including mixed separators.
// Invisible/bidi characters inside a near-UUID are rejected, never stripped from
// prose or names. Count alphanumerics so interleaved controls cannot hide an ID.
const UUID_CONTROLS = '\\u00ad\\u034f\\u061c\\u180e\\u200b-\\u200f\\u202a-\\u202e\\u2060-\\u206f\\ufeff';
const UUID_DASH = '[-\\u2010-\\u2015\\u2212\\ufe63\\uff0d]';
const uuidGroup = (min: number, max: number): string =>
  `[a-z0-9](?:[${UUID_CONTROLS}]*[a-z0-9]){${min - 1},${max - 1}}[${UUID_CONTROLS}]*`;
const UUID_TEXT = new RegExp(`${uuidGroup(7, 9)}(?:${UUID_DASH}[${UUID_CONTROLS}]*${uuidGroup(3, 5)}){3}${UUID_DASH}[${UUID_CONTROLS}]*${uuidGroup(10, 14)}`, 'i');

const ROLE_LABELS: Record<string, string> = { lead: 'Lead', team: 'Team', wheel: 'Wheel' };
// A local courtesy for the ingress 2/minute policy, not account/global quota state.
const DEFAULT_RATE_LIMIT_WAIT_SECONDS = 30;

const RULE_LABELS: Record<string, string> = {
  PLAN_PRESENCE: 'Saved plan', ACTIVITY_DISTANCE: 'Activity distance',
  PARTICIPANT_ELIGIBILITY: 'Participant eligibility', SAVED_LINEUP: 'Saved teams',
  ACTUAL_RECORDING: 'Actual recording', PLANNED_DAILY_KM: 'Planned workload',
  ACTUAL_DAILY_KM: 'Recorded workload', DATED_STATE_MISSING: 'Dated information',
  DOG_STATE: 'Dog state', WORKLOAD_BEFORE: 'Previous actual workload',
  HOUSING_INFORMATION: 'Housing', ACTUAL_LEDGER: 'Actual work recorded',
};
const VALUE_LABELS: Record<string, string> = {
  activities: 'Activities', distance: 'Distance', ineligible_participants: 'Ineligible participants',
  selected_participants: 'Selected dogs', saved_teams: 'Saved teams', validator_code: 'Lineup check',
  recording_status: 'Recording state', total: 'Total', starts_or_activities: 'Starts or activities',
  sessions: 'Sessions', dog_starts: 'Dog starts', dog_km: 'Dog-km', residents: 'Residents',
  nominal_capacity: 'Nominal capacity', class: 'Class', availability: 'Availability',
  housing: 'Housing', lifecycle: 'Lifecycle', born: 'Born by selected date', roles: 'Recorded roles',
  housing_source: 'Housing source', km_7d_before: 'Previous 7 days', km_14d_before: 'Previous 14 days',
  season_km_before: 'Season before date', starts_14d_before: 'Previous 14-day starts',
  days_since_work_before: 'Days since previous work', actual_km_on_date: 'Actual on this date',
  starts_on_date: 'Starts on this date',
};

@Component({
  selector: 'ht-operations-review',
  imports: [DatePipe, RouterLink],
  templateUrl: './operations-review.component.html',
  styleUrl: './operations-review.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class OperationsReviewComponent {
  readonly selectedDate = input.required<string>();
  readonly blocked = input(false);
  // Read the parent's signal directly at acceptance, including before the next
  // input-binding/effect pass. This is local saved-state fencing, not polling.
  readonly savedContextVersion = input<() => number>(() => 0);
  private readonly api = inject(OperationsService);
  private readonly session = inject(DemoSessionService);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);
  private readonly injector = inject(Injector);
  private readonly document = inject(DOCUMENT);
  private readonly reviewButton = viewChild<ElementRef<HTMLButtonElement>>('reviewButton');
  private readonly cancelButton = viewChild<ElementRef<HTMLButtonElement>>('cancelButton');
  private request: Subscription | null = null;
  private capabilitiesRequest: Subscription | null = null;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private epoch = 0;
  private destroyed = false;
  private contextDate: string | null = null;
  private contextSession: DemoSession | null | undefined;
  private contextSavedVersion: number | null = null;

  protected readonly capabilities = signal<OperationsCapabilities | null>(null);
  protected readonly capabilitiesFailed = signal(false);
  protected readonly pending = signal(false);
  protected readonly result = signal<OperationsReview | null>(null);
  protected readonly error = signal('');
  protected readonly notice = signal('');
  protected readonly retryAt = signal<number | null>(null);
  protected readonly sessionExpired = signal(false);
  protected readonly savedDayChanged = signal(false);
  protected readonly safePresentation = computed(() => this.presentationFor(this.result()));
  protected readonly safeLinks = computed(() => this.localLinks(this.result()?.links.filter((link) => link.entity.kind !== 'dog') ?? []));

  constructor() {
    this.loadCapabilities();
    for (const event of [this.session.resetReviewOpened$, this.session.resetStarted$, this.session.replaced$]) {
      event.pipe(takeUntilDestroyed()).subscribe(() => this.invalidate());
    }
    this.router.events.pipe(filter((event) => event instanceof NavigationStart), takeUntilDestroyed())
      .subscribe(() => this.invalidate());
    effect((onCleanup) => {
      const date = this.selectedDate(), currentSession = this.session.session();
      this.synchronize(date, currentSession, this.savedContextVersion()());
      let timer: ReturnType<typeof setTimeout> | null = null;
      const checkExpiry = () => {
        const remaining = currentSession ? new Date(currentSession.expires_at).getTime() - Date.now() : 0;
        const expired = !Number.isFinite(remaining) || remaining <= 0;
        this.sessionExpired.set(expired);
        if (expired) {
          this.invalidate();
          return;
        }
        timer = setTimeout(checkExpiry, Math.min(remaining, 2_147_483_647));
      };
      checkExpiry();
      onCleanup(() => { if (timer) clearTimeout(timer); });
    });
    this.destroyRef.onDestroy(() => {
      this.destroyed = true;
      this.invalidate();
      this.capabilitiesRequest?.unsubscribe();
      if (this.retryTimer) clearTimeout(this.retryTimer);
    });
  }

  protected loadCapabilities(): void {
    this.capabilitiesRequest?.unsubscribe();
    this.capabilitiesFailed.set(false);
    this.capabilitiesRequest = this.api.getCapabilities().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (capabilities) => this.capabilities.set(capabilities),
      error: () => { this.capabilities.set(null); this.capabilitiesFailed.set(true); },
    });
  }

  protected review(): void {
    const currentSession = this.session.session();
    const savedVersion = this.savedContextVersion()();
    this.synchronize(this.selectedDate(), currentSession, savedVersion);
    if (!this.capabilities()?.enabled || this.pending() || this.blocked() || this.retryAt() || !this.validSession(currentSession)) return;
    const date = this.selectedDate(), epoch = ++this.epoch;
    this.result.set(null);
    this.error.set('');
    this.notice.set('');
    this.savedDayChanged.set(false);
    this.pending.set(true);
    this.request = this.api.review(date).pipe(timeout(50_000), takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (response) => {
        if (!this.isCurrent(epoch, date, currentSession, savedVersion)) return;
        const restoreFocus = this.document.activeElement === this.cancelButton()?.nativeElement;
        this.pending.set(false);
        if (response.selected_date !== date) {
          this.error.set('The review response did not match this day. No result was accepted.');
        } else {
          this.result.set(response);
          this.notice.set(this.presentationFor(response) ? 'AI-assisted review ready.' : 'Saved-day facts are ready. The selected observations could not be verified and are not shown.');
        }
        if (restoreFocus) this.restoreReviewFocus(epoch);
      },
      error: (failure: unknown) => {
        if (!this.isCurrent(epoch, date, currentSession, savedVersion)) return;
        const restoreFocus = this.document.activeElement === this.cancelButton()?.nativeElement;
        this.pending.set(false);
        this.error.set(this.failureMessage(failure));
        const wait = this.retrySeconds(failure);
        if (wait > 0) {
          this.retryAt.set(Date.now() + wait * 1000);
          this.retryTimer = setTimeout(() => { this.retryAt.set(null); this.retryTimer = null; }, wait * 1000);
        }
        if (restoreFocus) this.restoreReviewFocus(epoch);
      },
    });
  }

  protected cancel(): void {
    this.invalidate();
    this.notice.set('Review cancelled here. A request already sent may still finish with the provider; no result will be shown. Cancelling does not return provider quota.');
    this.restoreReviewFocus(this.epoch);
  }

  protected ruleLabel(rule: string): string { return RULE_LABELS[rule] ?? 'Operational check'; }
  protected findingTitle(check: ReviewCheck): string {
    const current = this.result();
    const activities = [...new Set(check.entities.filter((entity) => entity.kind === 'activity').map((entity) => entity.id))]
      .flatMap((id) => {
        const activity = current?.summary?.activities.find((item) => item.entity.id === id);
        return activity ? [this.savedActivityLabel(activity)] : [];
      });
    const links = [...(current?.links ?? []), ...(current?.summary?.activities.flatMap((activity) => activity.selected_dogs) ?? []), ...(current?.finding_groups?.flatMap((group) => group.links) ?? [])];
    const names = [...new Set(check.entities.filter((entity) => entity.kind === 'dog').map((entity) => entity.id))]
      .flatMap((id) => {
        const link = links.find((item) => item.entity.kind === 'dog' && item.entity.id === id && this.localLink(item.path));
        return link && typeof link.label === 'string' && !UUID_TEXT.test(link.label) ? [link.label] : [];
      });
    const context = [...activities, ...names];
    return context.length ? `${this.ruleLabel(check.rule)} · ${context.join(' · ')}` : this.ruleLabel(check.rule);
  }
  protected localLinks(links: ReviewLink[]): LocalLink[] {
    return links.flatMap((link) => {
      if (typeof link.label !== 'string' || UUID_TEXT.test(link.label)) return [];
      const parsed = this.localLink(link.path);
      if (!parsed || (link.entity.kind === 'dog' && parsed.route !== `/demo/dogs/${link.entity.id}`)) return [];
      const activity = link.entity.kind === 'activity' ? this.result()?.summary?.activities.find((item) => item.entity.id === link.entity.id) : null;
      // Compatible older responses used an ambiguous label; only replace that
      // exact server label, from the already accepted frozen activity summary.
      const label = activity && link.label === 'Saved teams' ? `Teams for ${this.savedActivityLabel(activity)}` : link.label;
      return [{ ...parsed, label }];
    });
  }
  protected activityLabel(kind: string): string {
    return ({ training: 'Training', open_space_walk: 'Open-space walk', individual_exercise: 'Individual exercise', rest: 'Rest' } as Record<string, string>)[kind] ?? 'Activity';
  }
  protected savedActivityLabel(activity: ReviewActivity): string {
    if (typeof activity.label === 'string' && activity.label.trim() && !UUID_TEXT.test(activity.label)) return activity.label;
    const order = this.result()?.summary?.activities.findIndex((item) => item.entity.id === activity.entity.id) ?? -1;
    const distance = activity.distance_km === null ? '' : ` · ${activity.distance_km} km`;
    return `${this.activityLabel(activity.kind)}${distance}${order < 0 ? '' : ` — activity ${order + 1}`}`;
  }
  protected linkDescription(label: string, link: Omit<LocalLink, 'label'>): string | null {
    return link.newTab ? `${label} (opens in a new tab)` : null;
  }
  protected actualLabel(status: string): string {
    return ({ not_recorded: 'Not recorded', matches_plan: 'Recorded · matches plan', modified: 'Recorded · modified', not_run: 'Not run', context_only: 'Context only' } as Record<string, string>)[status] ?? 'Not verified';
  }
  private presentationFor(response: OperationsReview | null): DisplaySegment[][] | null {
    // Only the server-written selection contract is a factual review surface.
    if (response?.provenance !== 'ai_selected_server_observations' || typeof response.explanation !== 'string') return null;
    const presentation = response.presentation;
    if (!presentation || presentation.status !== 'ready' || !Array.isArray(presentation.segments) || !presentation.segments.length || presentation.segments.length > 64) return null;
    const flat = this.displaySegments(presentation.segments);
    if (!flat) return null;
    // Segments render adjacently. Preserve the whole-result guard, including
    // identifiers split across plain/link segments and structured boundaries.
    const visibleText = flat.map((segment) => segment.text).join('');
    if (!visibleText.trim() || visibleText !== response.explanation || UUID_TEXT.test(visibleText)) return null;
    const observations = presentation.observations;
    if (observations === undefined || Array.isArray(observations) && !observations.length) return [flat];
    if (!Array.isArray(observations) || observations.length > 6) return null;
    const groups: DisplaySegment[][] = [];
    const expected: ReviewPresentationSegment[] = [];
    for (const observation of observations) {
      if (!observation || !Array.isArray(observation.segments) || !observation.segments.length || observation.segments.length > 64) return null;
      const group = this.displaySegments(observation.segments);
      if (!group || !group.map((segment) => segment.text).join('').trim()) return null;
      if (expected.length) expected.push({ text: ' ', entity: null, path: null });
      expected.push(...observation.segments);
      groups.push(group);
    }
    if (expected.length !== presentation.segments.length || expected.some((segment, index) => {
      const original = presentation.segments[index];
      return segment.text !== original.text || segment.path !== original.path || segment.entity?.kind !== original.entity?.kind || segment.entity?.id !== original.entity?.id;
    })) return null;
    if (UUID_TEXT.test(groups.map((group) => group.map((segment) => segment.text).join('')).join(''))) return null;
    return groups;
  }
  private displaySegments(segments: ReviewPresentationSegment[]): DisplaySegment[] | null {
    const output: DisplaySegment[] = [];
    for (const segment of segments) {
      if (!segment || typeof segment.text !== 'string' || UUID_TEXT.test(segment.text)) return null;
      if (segment.entity === null && segment.path === null) { output.push({ text: segment.text, link: null }); continue; }
      if (!segment.entity || typeof segment.path !== 'string') return null;
      const link = this.localLink(segment.path);
      if (!link || (segment.entity.kind === 'dog' && link.route !== `/demo/dogs/${segment.entity.id}`)) return null;
      output.push({ text: segment.text, link });
    }
    return output;
  }
  protected valueLabel(name: string): string { return VALUE_LABELS[name] ?? name.replaceAll('_', ' '); }
  protected statusLabel(status: ReviewStatus): string {
    return { pass: 'Checked', violation: 'Issue', attention: 'Attention', unverified: 'Not verified' }[status];
  }
  protected providerLabel(provider: ReviewProvider): string { return provider === 'groq' ? 'Groq' : 'OpenRouter'; }
  protected toolLabel(name: string): string {
    return ({ get_day_plan: 'Read saved day plan', get_saved_teams: 'Read saved teams', get_dog_states: 'Read dated dog states', get_workload: 'Read actual workload', get_housing: 'Read dated housing', validate_day: 'Validate the selected day' } as Record<string, string>)[name] ?? 'Read operational facts';
  }
  protected evidenceFor(check: ReviewCheck): ReviewEvidence[] {
    return this.result()?.evidence.filter((item) => check.evidence_ids.includes(item.id)) ?? [];
  }
  protected displayValue(value: ReviewEvidence['values'][number]): string {
    const data = value.value;
    if (data === null) return 'Not recorded';
    if (typeof data === 'boolean') return data ? 'Yes' : 'No';
    if (value.unit === 'km') return `${data} km`;
    if (value.unit === 'days') return `${data} days`;
    if (value.name === 'roles' && typeof data === 'string') {
      if (!data.trim()) return 'No recorded roles';
      return data.split(',').map((role) => ROLE_LABELS[role.trim()] ?? role.trim()).join(' · ');
    }
    if (value.name === 'lifecycle' && data === 'archived') return 'Archived';
    if (value.name === 'lifecycle' && data === 'active') return 'Active';
    if (value.name === 'housing_source' && data === 'unhoused') return 'No housing assignment for this date';
    return typeof data === 'string' ? data.replaceAll('_', ' ') : String(data);
  }

  private synchronize(date: string, currentSession: DemoSession | null, savedVersion: number): void {
    if (this.contextDate !== date || this.contextSession !== currentSession) {
      this.invalidate();
      this.contextDate = date;
      this.contextSession = currentSession;
      this.contextSavedVersion = savedVersion;
    } else if (this.contextSavedVersion !== savedVersion) {
      const hadReview = this.pending() || this.result() !== null || Boolean(this.error()) || this.savedDayChanged();
      const restoreFocus = this.document.activeElement === this.cancelButton()?.nativeElement;
      this.invalidate();
      this.contextSavedVersion = savedVersion;
      if (hadReview) {
        this.savedDayChanged.set(true);
        this.notice.set('The saved day changed after this review. Start a new review to include your latest changes.');
        if (restoreFocus) this.restoreReviewFocus(this.epoch);
      }
    }
  }

  private invalidate(): void {
    this.epoch++;
    this.request?.unsubscribe();
    this.request = null;
    this.pending.set(false);
    this.result.set(null);
    this.error.set('');
    this.notice.set('');
    this.savedDayChanged.set(false);
    // Retry-After belongs to this connection/provider, not the selected demo date.
    // A date change or Reset must not make that waiting hint disappear.
  }

  private validSession(current: DemoSession | null): current is DemoSession {
    return Boolean(current?.active && new Date(current.expires_at).getTime() > Date.now());
  }
  private isCurrent(epoch: number, date: string, currentSession: DemoSession, savedVersion: number): boolean {
    return !this.destroyed && this.epoch === epoch && this.selectedDate() === date && this.session.session() === currentSession && this.validSession(currentSession) && this.savedContextVersion()() === savedVersion;
  }
  private restoreReviewFocus(epoch: number): void {
    // Signals change before Angular removes Cancel and re-enables this button.
    // Restore focus after that render, not in an earlier microtask.
    afterNextRender(() => {
      if (!this.destroyed && epoch === this.epoch) {
        const button = this.reviewButton()?.nativeElement;
        if (button?.isConnected && !button.disabled) button.focus({ preventScroll: true });
      }
    }, { injector: this.injector });
  }

  private failureMessage(failure: unknown): string {
    if (!(failure instanceof HttpErrorResponse)) return 'The review timed out. No result was accepted. Start another review only when you choose.';
    const detail: unknown = failure.error?.detail;
    const code = typeof detail === 'object' && detail !== null && 'code' in detail && typeof detail.code === 'string' ? detail.code : failure.status === 429 ? 'app_rate_limited' : '';
    const messages: Record<string, string> = {
      app_rate_limited: 'Too many reviews from this connection. Wait before starting another review.',
      review_busy: 'Another review is already running. Wait for it to finish before starting another.',
      ai_quota_exhausted: 'AI review is currently rate or quota limited. Wait before explicitly trying again.',
      ai_temporarily_unavailable: 'The free AI service is temporarily unavailable. Your saved plan is unchanged.',
      agent_disabled: 'AI review is not enabled in this environment. You can continue using Daily Plan.',
      timeout: 'The review reached its time limit. No result was accepted.',
      provider_timeout: 'The AI service did not respond in time. No result was accepted.',
      run_budget_exhausted: 'This review reached its request or response budget. No result was accepted.',
      invalid_provider_response: 'The AI response could not be validated. No result was accepted.',
      invalid_evidence: 'The AI response did not match the checked evidence. No result was accepted.',
      forbidden_tool: 'The AI requested an unsupported action. The review was stopped.',
      policy_refusal: 'The AI service declined this review. No alternative route was used to bypass that decision.',
      session_required: 'Open a current demo session before reviewing this day.',
      session_expired: 'Your demo session expired. Reload the demo before starting a new review.',
      context_changed: 'Your demo context changed. Start a new review of the current saved day.',
      date_out_of_range: 'Choose a date within the demo season before reviewing.',
      snapshot_too_large: 'This saved day has more detail than one compact review can read. Use the operational screens to inspect it.',
      invalid_review_request: 'The review request could not be accepted. Reload the current day before trying again.',
      origin_not_allowed: 'Start this review from the current Husky Tracking application.',
      provider_configuration: 'AI review is unavailable because its provider configuration needs attention.',
      provider_authentication: 'AI review is unavailable because its provider configuration needs attention.',
      provider_access_denied: 'The AI provider did not permit this review. No bypass was attempted.',
      provider_payment_required: 'A free AI route was not available. No paid request was attempted.',
      cancelled: 'The review was cancelled. No result was accepted.',
    };
    return messages[code] ?? 'The review could not be completed. Your saved day is unchanged; no result was accepted.';
  }

  private retrySeconds(failure: unknown): number {
    if (!(failure instanceof HttpErrorResponse)) return 0;
    const header = failure.headers.get('Retry-After')?.trim();
    const detail: unknown = failure.error?.detail;
    const supplied = typeof detail === 'object' && detail !== null && 'retry_after_seconds' in detail && typeof detail.retry_after_seconds === 'number' ? detail.retry_after_seconds : null;
    const parsed = header && /^\d+$/.test(header) ? Number(header)
      : header && /GMT$/i.test(header) ? Math.max(0, Math.ceil((Date.parse(header) - Date.now()) / 1000)) : null;
    // A valid explicit zero means no additional waiting hint. Invalid/missing
    // headers may use the typed body hint, then the local generic-429 courtesy.
    const wait = parsed !== null && Number.isFinite(parsed) ? parsed
      : supplied !== null && Number.isFinite(supplied) && supplied >= 0 ? supplied
      : failure.status === 429 ? DEFAULT_RATE_LIMIT_WAIT_SECONDS : 0;
    return Math.min(86400, Math.ceil(wait));
  }

  private localLink(path: string): Omit<LocalLink, 'label'> | null {
    if (!path.startsWith('/demo/') || path.includes('\\')) return null;
    try {
      const url = new URL(path, 'https://huskytracking.invalid');
      if (url.origin !== 'https://huskytracking.invalid' || url.hash || !/^\/demo\/(?:daily(?:\/\d{4}-\d{2}-\d{2}\/activities\/[0-9a-f-]{32,36}\/teams)?|daily-entry|kennel|dogs\/[0-9a-f-]{32,36}|analytics|dashboard)\/?$/i.test(url.pathname)) return null;
      const query: Record<string, string> = {};
      for (const key of ['date', 'tab', 'layer', 'view', 'from', 'to']) {
        const value = url.searchParams.get(key);
        if (value !== null) query[key] = value;
      }
      const current = new URL(this.router.url, 'https://huskytracking.invalid');
      const normalized = (entries: URLSearchParams) => { const sorted = new URLSearchParams(entries); sorted.sort(); return sorted.toString(); };
      const newTab = url.pathname !== current.pathname || normalized(new URLSearchParams(query)) !== normalized(current.searchParams);
      return { route: url.pathname, query, newTab };
    } catch { return null; }
  }
}
