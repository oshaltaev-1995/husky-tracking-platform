import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';

import {
  ActivityWrite,
  DailyPlan,
  PlannedActivity,
  PlannedActivityType,
} from '../../core/api/daily-plans.models';
import { DailyPlansService } from '../../core/api/daily-plans.service';
import { ActivityEditorComponent } from './activity-editor.component';

const DEFAULT_DATE = '2026-03-31';
const SEASON_START = '2025-12-01';
const SEASON_END = '2026-03-31';

@Component({
  selector: 'ht-daily-plan-page',
  imports: [ActivityEditorComponent, DatePipe, FormsModule],
  templateUrl: './daily-plan-page.component.html',
  styleUrl: './daily-plan-page.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DailyPlanPageComponent {
  private readonly plans = inject(DailyPlansService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  protected selectedDate = DEFAULT_DATE;
  protected notes = '';
  protected readonly plan = signal<DailyPlan | null>(null);
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

  constructor() {
    this.route.queryParamMap.subscribe((params) => {
      const requested = params.get('date');
      const date = this.validDate(requested) ? requested : DEFAULT_DATE;
      this.selectedDate = date;
      if (requested !== null && requested !== date) {
        void this.router.navigate([], {
          relativeTo: this.route,
          queryParams: { date },
          replaceUrl: true,
        });
      }
      this.load(date);
    });
  }

  protected changeDate(value: string): void {
    if (this.noteDirty()) {
      this.selectedDate = this.plan()?.selected_date ?? DEFAULT_DATE;
      this.pageError.set('Save or discard the daily note before changing date.');
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
    if (offset < 0) return this.selectedDate > SEASON_START;
    return this.selectedDate < SEASON_END;
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
  }

  protected saveActivity(payload: ActivityWrite): void {
    const activity = this.editingActivity();
    this.savingEditor.set(true);
    this.editorError.set('');
    const request = activity
      ? this.plans.updateActivity(this.selectedDate, activity.id, payload)
      : this.plans.createActivity(this.selectedDate, payload);
    request.subscribe({
      next: (plan) => {
        this.acceptPlan(plan);
        this.savingEditor.set(false);
        this.closeEditor();
        this.successMessage.set(activity ? 'Activity updated.' : 'Activity added.');
      },
      error: (error: HttpErrorResponse) => {
        this.savingEditor.set(false);
        this.editorError.set(this.errorMessage(error));
      },
    });
  }

  protected saveNotes(): void {
    const plan = this.plan();
    this.savingNotes.set(true);
    this.pageError.set('');
    this.plans
      .updateNotes(this.selectedDate, this.notes.trim() || null, plan?.revision ?? null)
      .subscribe({
        next: (updated) => {
          this.acceptPlan(updated);
          this.savingNotes.set(false);
          this.successMessage.set('Daily note saved.');
        },
        error: (error: HttpErrorResponse) => {
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
    this.pageError.set('');
    this.plans.moveActivity(this.selectedDate, activity.id, direction, revision).subscribe({
      next: (plan) => this.acceptPlan(plan),
      error: (error: HttpErrorResponse) => this.pageError.set(this.errorMessage(error)),
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
    this.plans.deleteActivity(this.selectedDate, activity.id, revision).subscribe({
      next: (plan) => {
        this.acceptPlan(plan);
        this.pendingDeleteId.set(null);
        this.successMessage.set('Activity removed.');
      },
      error: (error: HttpErrorResponse) => {
        this.pendingDeleteId.set(null);
        this.pageError.set(this.errorMessage(error));
      },
    });
  }

  protected retry(): void {
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
    this.loading.set(true);
    this.pageError.set('');
    this.successMessage.set('');
    this.pendingDeleteId.set(null);
    this.plans.getPlan(date).subscribe({
      next: (plan) => {
        this.acceptPlan(plan);
        this.loading.set(false);
      },
      error: () => {
        this.loading.set(false);
        this.pageError.set('The daily plan could not be loaded. Check the demo API and try again.');
      },
    });
  }

  private acceptPlan(plan: DailyPlan): void {
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
