import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, DestroyRef, effect, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Subscription, timeout } from 'rxjs';

import {
  ActivityWrite,
  DailyPlan,
  PlannedActivity,
  PlannedActivityType,
  TrainingDayProposal,
} from '../../core/api/daily-plans.models';
import { DailyPlansService } from '../../core/api/daily-plans.service';
import { DemoSessionService } from '../../core/api/demo-session.service';
import { ActivityEditorComponent } from './activity-editor.component';
import { OperationsReviewComponent } from './operations-review.component';
import { TrainingDayReviewComponent, TrainingDayReviewPhase } from './training-day-review.component';

const DEFAULT_DATE = '2026-03-31';
const SEASON_START = '2025-12-01';
const SEASON_END = '2026-03-31';

@Component({
  selector: 'ht-daily-plan-page',
  imports: [ActivityEditorComponent, DatePipe, FormsModule, RouterLink, TrainingDayReviewComponent, OperationsReviewComponent],
  templateUrl: './daily-plan-page.component.html',
  styleUrl: './daily-plan-page.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DailyPlanPageComponent {
  private readonly plans = inject(DailyPlansService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly session = inject(DemoSessionService);
  private readonly destroyRef = inject(DestroyRef);
  private contextDate = DEFAULT_DATE;
  private contextEpoch = 0;
  private loadEpoch = 0;
  private trainingEpoch = 0;
  private destroyed = false;
  private trainingRequest: Subscription | null = null;
  private acceptedReviewContext: string | null = null;

  protected selectedDate = DEFAULT_DATE;
  protected notes = '';
  protected readonly plan = signal<DailyPlan | null>(null);
  // Pass the signal itself so response guards can read saves before another render.
  protected readonly savedDayVersion = signal(0);
  protected readonly loading = signal(true);
  protected readonly pageError = signal('');
  protected readonly successMessage = signal('');
  protected readonly editorOpen = signal(false);
  protected readonly editingActivity = signal<PlannedActivity | null>(null);
  protected readonly savingEditor = signal(false);
  protected readonly editorError = signal('');
  protected readonly savingNotes = signal(false);
  protected readonly noteDirty = signal(false);
  protected readonly pendingDeleteId = signal<string | null>(null);
  protected readonly lineupClearRequired = signal(false);
  protected readonly mutatingPlan = signal(false);
  protected readonly trainingDayOpen = signal(false);
  protected readonly trainingDayPhase = signal<TrainingDayReviewPhase>('loading');
  protected readonly trainingDayProposal = signal<TrainingDayProposal | null>(null);
  protected readonly trainingDayError = signal('');
  protected readonly trainingDayReconciledEmpty = signal(false);
  protected trainingDayReturnFocusAllowed: () => boolean = () => false;
  private pendingLineupChange: ActivityWrite | null = null;

  constructor() {
    this.destroyRef.onDestroy(() => {
      this.destroyed = true;
      this.contextEpoch++;
      this.invalidateTrainingDay();
    });
    this.session.resetReviewOpened$.pipe(takeUntilDestroyed()).subscribe(() => {
      const uncertain = this.trainingDayPhase() === 'applying' || this.trainingDayPhase() === 'unknown';
      this.invalidateTrainingDay();
      if (uncertain) this.pageError.set('A training-day save may already have reached the server. Check the example date if you cancel Reset.');
    });
    this.session.resetStarted$.pipe(takeUntilDestroyed()).subscribe(() => this.invalidateContext('Resetting your demo. The training day review was closed.'));
    this.session.resetCompleted$.pipe(takeUntilDestroyed()).subscribe(() => this.load(this.contextDate));
    this.session.resetFailed$.pipe(takeUntilDestroyed()).subscribe(() => this.pageError.set('Reset could not be confirmed. Reload the plan before editing.'));
    this.session.replaced$.pipe(takeUntilDestroyed()).subscribe(() => this.invalidateContext('Your demo session changed. Reload the plan and open a new training day review.'));
    effect((onCleanup) => {
      const expiresAt = this.session.session()?.expires_at;
      if (!expiresAt) return;
      // Wall-clock time checks cookie expiry only, never the example/domain date.
      const remaining = new Date(expiresAt).getTime() - Date.now();
      if (!Number.isFinite(remaining)) return;
      if (remaining <= 0) { this.invalidateContext('Your demo session expired. Reload this page before continuing.'); return; }
      const timer = setTimeout(() => this.invalidateContext('Your demo session expired. Reload this page before continuing.'), remaining);
      onCleanup(() => clearTimeout(timer));
    });
    this.route.queryParamMap.pipe(takeUntilDestroyed()).subscribe((params) => {
      const requested = params.get('date');
      const date = this.validDate(requested) ? requested : DEFAULT_DATE;
      if (date !== this.contextDate && (this.noteDirty() || this.editorOpen() || this.manualBusy())) {
        this.selectedDate = this.contextDate;
        this.pageError.set('Save or discard the current note or activity before changing date.');
        void this.router.navigate([], { relativeTo: this.route, queryParams: { date: this.contextDate }, replaceUrl: true });
        return;
      }
      this.selectedDate = date;
      if (requested !== null && requested !== date) {
        void this.router.navigate([], {
          relativeTo: this.route,
          queryParams: { date },
          replaceUrl: true,
        });
      }
      if (date === this.contextDate && this.plan()?.selected_date === date && !this.loading()) return;
      const uncertain = this.trainingDayPhase() === 'applying' || this.trainingDayPhase() === 'unknown';
      this.invalidateContext();
      this.contextDate = date;
      this.load(date);
      if (uncertain) this.pageError.set('A training-day save may still complete on its proposed date. Changing the view cannot cancel it.');
    });
  }

  protected changeDate(value: string): void {
    if (this.noteDirty() || this.editorOpen() || this.manualBusy() || this.trainingDayOpen()) {
      this.selectedDate = this.contextDate;
      this.pageError.set('Save or discard the current note or activity before changing date.');
      return;
    }
    const date = this.validDate(value) ? value : DEFAULT_DATE;
    void this.router.navigate([], { relativeTo: this.route, queryParams: { date } });
  }

  protected moveDay(offset: number): void {
    const date = new Date(`${this.selectedDate}T12:00:00Z`);
    date.setUTCDate(date.getUTCDate() + offset);
    const next = date.toISOString().slice(0, 10);
    if (this.validDate(next)) this.changeDate(next);
  }

  protected canMove(offset: number): boolean {
    if (this.trainingDayOpen() || this.manualBusy()) return false;
    if (offset < 0) return this.selectedDate > SEASON_START;
    return this.selectedDate < SEASON_END;
  }

  protected openTrainingDay(): void {
    if (this.trainingDayOpen()) return;
    const session = this.session.session();
    if (session && new Date(session.expires_at).getTime() <= Date.now()) {
      this.pageError.set('Your demo session expired. Reload this page before continuing.');
      return;
    }
    if (this.noteDirty() || this.editorOpen() || this.manualBusy() || this.loading() || !this.plan()) {
      this.pageError.set('Save or discard the current note or activity before trying the training day.');
      return;
    }
    const epoch = this.contextEpoch, date = this.contextDate;
    this.trainingDayReturnFocusAllowed = () => this.isCurrent(epoch, date);
    this.pageError.set('');
    this.trainingDayOpen.set(true);
    this.reviewTrainingDayAgain();
  }

  protected closeTrainingDay(): void {
    if (this.trainingDayPhase() === 'applying' || this.trainingDayPhase() === 'reconciling') return;
    if (this.trainingDayPhase() === 'unknown') this.pageError.set('The training-day result is still unknown. Check the example date before planning again.');
    this.invalidateTrainingDay();
  }

  protected reviewTrainingDayAgain(): void {
    if (!this.trainingDayOpen() || this.trainingDayPhase() === 'applying' || this.trainingDayPhase() === 'reconciling') return;
    this.trainingRequest?.unsubscribe();
    const attempt = ++this.trainingEpoch, epoch = this.contextEpoch, date = this.contextDate;
    this.trainingDayPhase.set('loading');
    this.trainingDayProposal.set(null);
    this.trainingDayError.set('');
    this.trainingDayReconciledEmpty.set(false);
    this.trainingRequest = this.plans.getTrainingDayProposal().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (proposal) => {
        if (!this.isTrainingCurrent(attempt, epoch, date)) return;
        this.trainingDayProposal.set(structuredClone(proposal));
        this.trainingDayPhase.set(proposal.available && proposal.precondition ? 'ready' : 'unavailable');
      },
      error: (error: HttpErrorResponse) => {
        if (!this.isTrainingCurrent(attempt, epoch, date)) return;
        this.trainingDayPhase.set('error');
        this.trainingDayError.set(error.status === 429
          ? 'Too many training-day requests. Please wait a moment, then choose Review again. No plan was submitted.'
          : error.status === 401 || error.status === 403
          ? 'Your demo session is no longer valid. Reload this page, then review again.'
          : 'The training day could not be prepared. No plan was submitted. Try reviewing again.');
      },
    });
  }

  protected applyTrainingDay(): void {
    const proposal = this.trainingDayProposal();
    if (!this.trainingDayOpen() || this.trainingDayPhase() !== 'ready' || !proposal?.available || !proposal.precondition) return;
    if (this.noteDirty() || this.editorOpen() || this.manualBusy()) {
      this.trainingDayError.set('Save or discard the current note or activity before applying the example.');
      return;
    }
    const attempt = ++this.trainingEpoch, epoch = this.contextEpoch, date = this.contextDate;
    this.trainingDayPhase.set('applying');
    this.trainingDayError.set('');
    this.trainingDayReconciledEmpty.set(false);
    this.trainingRequest = this.plans.applyTrainingDay({
      date: proposal.date,
      preset_version: proposal.preset_version,
      participant_ids: proposal.participants.map((dog) => dog.id),
      precondition: proposal.precondition,
    }).pipe(timeout({ first: 20_000 }), takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (plan) => {
        if (!this.isTrainingCurrent(attempt, epoch, date)) return;
        this.acceptTrainingDayPlan(plan, 'Training day added. Teams and actual work are still separate next steps.');
      },
      error: (error: unknown) => {
        if (!this.isTrainingCurrent(attempt, epoch, date)) return;
        if (error instanceof HttpErrorResponse && error.status >= 400 && error.status < 500 && error.status !== 408) {
          this.trainingDayPhase.set('rejected');
          this.trainingDayError.set(error.status === 429
            ? 'Too many training-day requests. Please wait a moment, then review again before applying. Nothing will be retried automatically.'
            : this.errorMessage(error));
        } else {
          // A failed response does not prove that the server transaction failed.
          this.trainingDayPhase.set('unknown');
          this.trainingDayError.set('');
        }
      },
    });
  }

  protected checkTrainingDay(): void {
    if (this.trainingDayPhase() !== 'unknown') return;
    this.readTrainingDay(false);
  }

  protected openTrainingDayDate(): void {
    if (this.trainingDayPhase() !== 'unavailable' && this.trainingDayPhase() !== 'rejected') return;
    this.readTrainingDay(true);
  }

  private readTrainingDay(openEmptyDay: boolean): void {
    const proposal = this.trainingDayProposal();
    if (!proposal) return;
    const previousPhase = this.trainingDayPhase();
    const attempt = ++this.trainingEpoch, epoch = this.contextEpoch, date = this.contextDate;
    this.trainingDayPhase.set('reconciling');
    this.trainingDayError.set('');
    this.trainingRequest = this.plans.getPlan(proposal.date).pipe(timeout({ first: 20_000 }), takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (plan) => {
        if (!this.isTrainingCurrent(attempt, epoch, date)) return;
        if (openEmptyDay || plan.exists) {
          this.acceptTrainingDayPlan(plan, 'Current day opened. Check its saved activities; no save request was repeated.');
        } else {
          this.trainingDayPhase.set('unknown');
          this.trainingDayReconciledEmpty.set(true);
        }
      },
      error: () => {
        if (!this.isTrainingCurrent(attempt, epoch, date)) return;
        this.trainingDayPhase.set(previousPhase === 'unknown' ? 'unknown' : 'rejected');
        this.trainingDayError.set('The current day could not be read. No save request was repeated.');
      },
    });
  }

  private acceptTrainingDayPlan(plan: DailyPlan, feedback: string): void {
    this.contextEpoch++;
    this.loadEpoch++;
    this.invalidateTrainingDay();
    this.contextDate = plan.selected_date;
    this.selectedDate = plan.selected_date;
    this.acceptPlan(plan);
    this.loading.set(false);
    this.pageError.set('');
    this.successMessage.set(feedback);
    void this.router.navigate([], { relativeTo: this.route, queryParams: { date: plan.selected_date } });
  }

  private invalidateTrainingDay(): void {
    this.trainingEpoch++;
    // Unsubscribing only detaches this UI; it cannot roll back a server save.
    this.trainingRequest?.unsubscribe();
    this.trainingRequest = null;
    this.trainingDayOpen.set(false);
    this.trainingDayPhase.set('loading');
    this.trainingDayProposal.set(null);
    this.trainingDayError.set('');
    this.trainingDayReconciledEmpty.set(false);
  }

  private invalidateContext(message = ''): void {
    this.contextEpoch++;
    this.loadEpoch++;
    this.invalidateTrainingDay();
    if (message) {
      this.closeEditor();
      this.savingEditor.set(false);
      this.savingNotes.set(false);
      this.mutatingPlan.set(false);
      this.plan.set(null);
      this.loading.set(false);
      this.notes = '';
      this.noteDirty.set(false);
      this.pageError.set(message);
    }
  }

  private isCurrent(epoch: number, date: string): boolean {
    return !this.destroyed && epoch === this.contextEpoch && date === this.contextDate;
  }

  private isTrainingCurrent(attempt: number, epoch: number, date: string): boolean {
    return this.trainingDayOpen() && attempt === this.trainingEpoch && this.isCurrent(epoch, date);
  }

  private manualBusy(): boolean {
    return this.savingEditor() || this.savingNotes() || this.mutatingPlan();
  }

  protected openCreate(): void {
    this.editingActivity.set(null);
    this.editorError.set('');
    this.editorOpen.set(true);
  }

  protected openEdit(activity: PlannedActivity): void {
    this.editingActivity.set(activity);
    this.editorError.set('');
    this.editorOpen.set(true);
  }

  protected closeEditor(): void {
    this.editorOpen.set(false);
    this.editingActivity.set(null);
    this.editorError.set('');
    this.lineupClearRequired.set(false);
    this.pendingLineupChange = null;
  }

  protected saveActivity(payload: ActivityWrite): void {
    const activity = this.editingActivity();
    const epoch = this.contextEpoch, date = this.contextDate;
    this.savingEditor.set(true);
    this.editorError.set('');
    this.lineupClearRequired.set(false);
    const request = activity
      ? this.plans.updateActivity(this.selectedDate, activity.id, payload)
      : this.plans.createActivity(this.selectedDate, payload);
    request.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (plan) => {
        if (!this.isCurrent(epoch, date)) return;
        this.acceptPlan(plan);
        this.savingEditor.set(false);
        this.closeEditor();
        this.successMessage.set(activity ? 'Activity updated.' : 'Activity added.');
      },
      error: (error: HttpErrorResponse) => {
        if (!this.isCurrent(epoch, date)) return;
        this.savingEditor.set(false);
        if (error.error?.detail?.code === 'saved_teams_require_clear') {
          this.pendingLineupChange = payload;
          this.lineupClearRequired.set(true);
        } else {
          this.editorError.set(this.errorMessage(error));
        }
      },
    });
  }

  protected confirmLineupClear(): void {
    const activity = this.editingActivity();
    const payload = this.pendingLineupChange;
    if (!activity || !payload) return;
    const epoch = this.contextEpoch, date = this.contextDate;
    this.savingEditor.set(true);
    this.lineupClearRequired.set(false);
    this.plans
      .updateActivity(this.selectedDate, activity.id, { ...payload, clear_saved_teams: true })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (plan) => {
          if (!this.isCurrent(epoch, date)) return;
          this.acceptPlan(plan);
          this.savingEditor.set(false);
          this.closeEditor();
          this.successMessage.set('Activity updated and saved teams cleared.');
        },
        error: (error: HttpErrorResponse) => {
          if (!this.isCurrent(epoch, date)) return;
          this.savingEditor.set(false);
          this.editorError.set(this.errorMessage(error));
        },
      });
  }

  protected keepLineup(): void {
    this.lineupClearRequired.set(false);
    this.pendingLineupChange = null;
  }

  protected saveNotes(): void {
    const plan = this.plan();
    const epoch = this.contextEpoch, date = this.contextDate;
    this.savingNotes.set(true);
    this.pageError.set('');
    this.plans
      .updateNotes(this.selectedDate, this.notes.trim() || null, plan?.revision ?? null)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (updated) => {
          if (!this.isCurrent(epoch, date)) return;
          this.acceptPlan(updated);
          this.savingNotes.set(false);
          this.successMessage.set('Daily note saved.');
        },
        error: (error: HttpErrorResponse) => {
          if (!this.isCurrent(epoch, date)) return;
          this.savingNotes.set(false);
          this.pageError.set(this.errorMessage(error));
        },
      });
  }

  protected noteChanged(value: string): void {
    this.notes = value;
    this.noteDirty.set(value !== (this.plan()?.notes ?? ''));
  }

  protected discardNotes(): void {
    this.notes = this.plan()?.notes ?? '';
    this.noteDirty.set(false);
    this.pageError.set('');
  }

  protected moveActivity(activity: PlannedActivity, direction: 'up' | 'down'): void {
    const revision = this.plan()?.revision;
    if (revision === null || revision === undefined) return;
    if (this.mutatingPlan()) return;
    const epoch = this.contextEpoch, date = this.contextDate;
    this.mutatingPlan.set(true);
    this.pageError.set('');
    this.plans.moveActivity(this.selectedDate, activity.id, direction, revision).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (plan) => {
        if (!this.isCurrent(epoch, date)) return;
        this.mutatingPlan.set(false);
        this.acceptPlan(plan);
      },
      error: (error: HttpErrorResponse) => {
        if (!this.isCurrent(epoch, date)) return;
        this.mutatingPlan.set(false);
        this.pageError.set(this.errorMessage(error));
      },
    });
  }

  protected askDelete(activityId: string): void {
    this.pendingDeleteId.set(activityId);
  }

  protected cancelDelete(): void {
    this.pendingDeleteId.set(null);
  }

  protected deleteActivity(activity: PlannedActivity): void {
    const revision = this.plan()?.revision;
    if (revision === null || revision === undefined) return;
    if (this.mutatingPlan()) return;
    const epoch = this.contextEpoch, date = this.contextDate;
    this.mutatingPlan.set(true);
    this.plans.deleteActivity(this.selectedDate, activity.id, revision).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (plan) => {
        if (!this.isCurrent(epoch, date)) return;
        this.mutatingPlan.set(false);
        this.acceptPlan(plan);
        this.pendingDeleteId.set(null);
        this.successMessage.set('Activity removed.');
      },
      error: (error: HttpErrorResponse) => {
        if (!this.isCurrent(epoch, date)) return;
        this.mutatingPlan.set(false);
        this.pendingDeleteId.set(null);
        this.pageError.set(this.errorMessage(error));
      },
    });
  }

  protected retry(): void {
    if (this.noteDirty() || this.editorOpen() || this.manualBusy()) {
      this.pageError.set('Save or discard the current note or activity before reloading the plan.');
      return;
    }
    this.load(this.selectedDate);
  }

  protected activityLabel(type: PlannedActivityType): string {
    const labels: Record<PlannedActivityType, string> = {
      training: 'Training',
      open_space_walk: 'Open-space walk',
      individual_exercise: 'Individual exercise',
      rest: 'Rest',
    };
    return labels[type];
  }

  protected classLabel(value: string | null): string {
    return value ? value.replace(/^./, (character) => character.toUpperCase()) : '';
  }

  private load(date: string): void {
    const epoch = this.contextEpoch, request = ++this.loadEpoch;
    this.loading.set(true);
    this.plan.set(null);
    this.pageError.set('');
    this.successMessage.set('');
    this.pendingDeleteId.set(null);
    this.plans.getPlan(date).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (plan) => {
        if (!this.isCurrent(epoch, date) || request !== this.loadEpoch) return;
        this.acceptPlan(plan);
        this.loading.set(false);
      },
      error: () => {
        if (!this.isCurrent(epoch, date) || request !== this.loadEpoch) return;
        this.loading.set(false);
        this.pageError.set('The daily plan could not be loaded. Check the demo API and try again.');
      },
    });
  }

  private acceptPlan(plan: DailyPlan): void {
    // Keep the last accepted identity/revision across a loading placeholder. Opening
    // or cancelling an editor, failed saves and an unchanged reload are not saves.
    const context = JSON.stringify([plan.selected_date, plan.exists, plan.id, plan.revision]);
    if (context !== this.acceptedReviewContext) {
      this.acceptedReviewContext = context;
      this.savedDayVersion.update((version) => version + 1);
    }
    this.plan.set(plan);
    this.notes = plan.notes ?? '';
    this.noteDirty.set(false);
  }

  private validDate(value: string | null): value is string {
    if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
    const parsed = new Date(`${value}T12:00:00Z`);
    return !Number.isNaN(parsed.valueOf()) && value >= SEASON_START && value <= SEASON_END;
  }

  private errorMessage(error: HttpErrorResponse): string {
    const detail = error.error?.detail;
    if (typeof detail === 'object' && typeof detail?.message === 'string') return detail.message;
    if (typeof detail === 'string') return detail;
    return 'The plan could not be saved. Try again.';
  }
}
