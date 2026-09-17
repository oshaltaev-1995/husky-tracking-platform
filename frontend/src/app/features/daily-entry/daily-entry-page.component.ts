import { DatePipe, DOCUMENT } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import {
  ActualSession,
  ActualSessionWrite,
  DailyDog,
  DailyEntry,
  PlannedActivityActual,
} from '../../core/api/daily-entry.models';
import { DailyEntryService } from '../../core/api/daily-entry.service';
import { ActualSessionEditorComponent } from './actual-session-editor.component';

const DEFAULT_DATE = '2026-03-31';
const SEASON_START = '2025-12-01';
const SEASON_END = '2026-03-31';

@Component({
  selector: 'ht-daily-entry-page',
  imports: [ActualSessionEditorComponent, DatePipe, FormsModule, RouterLink],
  templateUrl: './daily-entry-page.component.html',
  styleUrl: './daily-entry-page.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DailyEntryPageComponent {
  private readonly entries = inject(DailyEntryService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly document = inject(DOCUMENT);

  protected selectedDate = DEFAULT_DATE;
  protected findTerm = '';
  protected readonly entry = signal<DailyEntry | null>(null);
  protected readonly loading = signal(true);
  protected readonly pageError = signal('');
  protected readonly successMessage = signal('');
  protected readonly busyActivityId = signal<string | null>(null);
  protected readonly pendingDeleteId = signal<string | null>(null);
  protected readonly editorOpen = signal(false);
  protected readonly editingSession = signal<ActualSession | null>(null);
  protected readonly savingEditor = signal(false);
  protected readonly editorError = signal('');
  protected readonly highlightedDogId = signal<string | null>(null);

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
    return offset < 0 ? this.selectedDate > SEASON_START : this.selectedDate < SEASON_END;
  }

  protected openCreate(): void {
    this.editingSession.set(null);
    this.editorError.set('');
    this.editorOpen.set(true);
  }

  protected openEdit(session: ActualSession): void {
    this.editingSession.set(session);
    this.editorError.set('');
    this.editorOpen.set(true);
  }

  protected closeEditor(): void {
    this.editorOpen.set(false);
    this.editingSession.set(null);
    this.editorError.set('');
  }

  protected saveSession(payload: ActualSessionWrite): void {
    const current = this.editingSession();
    this.savingEditor.set(true);
    this.editorError.set('');
    const request = current
      ? this.entries.updateSession(this.selectedDate, current.id, {
          ...payload,
          expected_revision: current.revision,
        })
      : this.entries.createSession(this.selectedDate, payload);
    request.subscribe({
      next: (entry) => {
        this.acceptEntry(entry);
        this.savingEditor.set(false);
        this.closeEditor();
        this.successMessage.set(current ? 'Actual session updated.' : 'Actual session recorded.');
      },
      error: (error: HttpErrorResponse) => {
        this.savingEditor.set(false);
        this.editorError.set(this.errorMessage(error));
      },
    });
  }

  protected confirmPlan(activity: PlannedActivityActual): void {
    this.busyActivityId.set(activity.id);
    this.pageError.set('');
    this.entries.confirmPlan(this.selectedDate, activity.id).subscribe({
      next: (entry) => {
        this.acceptEntry(entry);
        this.busyActivityId.set(null);
        this.successMessage.set('Planned training recorded as actual work.');
      },
      error: (error: HttpErrorResponse) => {
        this.busyActivityId.set(null);
        this.pageError.set(this.errorMessage(error));
      },
    });
  }

  protected markNotRun(activity: PlannedActivityActual): void {
    this.busyActivityId.set(activity.id);
    this.entries.markNotRun(this.selectedDate, activity.id).subscribe({
      next: (entry) => {
        this.acceptEntry(entry);
        this.busyActivityId.set(null);
        this.successMessage.set('Planned training marked not run.');
      },
      error: (error: HttpErrorResponse) => {
        this.busyActivityId.set(null);
        this.pageError.set(this.errorMessage(error));
      },
    });
  }

  protected restorePlan(activity: PlannedActivityActual): void {
    this.busyActivityId.set(activity.id);
    this.entries.clearNotRun(this.selectedDate, activity.id).subscribe({
      next: (entry) => {
        this.acceptEntry(entry);
        this.busyActivityId.set(null);
      },
      error: (error: HttpErrorResponse) => {
        this.busyActivityId.set(null);
        this.pageError.set(this.errorMessage(error));
      },
    });
  }

  protected linkedSession(activity: PlannedActivityActual): ActualSession | undefined {
    return this.entry()?.sessions.find((session) => session.id === activity.actual_session_id);
  }

  protected askDelete(sessionId: string): void {
    this.pendingDeleteId.set(sessionId);
  }

  protected cancelDelete(): void {
    this.pendingDeleteId.set(null);
  }

  protected deleteSession(session: ActualSession): void {
    this.entries.deleteSession(this.selectedDate, session.id, session.revision).subscribe({
      next: (entry) => {
        this.acceptEntry(entry);
        this.pendingDeleteId.set(null);
        this.successMessage.set('Actual session removed; planning records were preserved.');
      },
      error: (error: HttpErrorResponse) => {
        this.pendingDeleteId.set(null);
        this.pageError.set(this.errorMessage(error));
      },
    });
  }

  protected findDog(): void {
    const term = this.findTerm.trim().toLocaleLowerCase();
    if (!term) return;
    const dogs = this.entry()?.housing_groups.flatMap((group) => group.dogs) ?? [];
    const match =
      dogs.find((dog) => dog.name.toLocaleLowerCase() === term) ??
      dogs.find((dog) => dog.name.toLocaleLowerCase().startsWith(term)) ??
      dogs.find((dog) => dog.name.toLocaleLowerCase().includes(term));
    if (!match) {
      this.pageError.set(`No resident dog matches “${this.findTerm.trim()}” on this date.`);
      return;
    }
    this.pageError.set('');
    this.highlightedDogId.set(match.id);
    this.document.defaultView?.setTimeout(() => {
      const target = this.document.getElementById(`daily-dog-${match.id}`);
      if (typeof target?.scrollIntoView === 'function') {
        target.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
      target?.focus({ preventScroll: true });
    }, 0);
  }

  protected dogSuggestions(): DailyDog[] {
    return this.entry()?.housing_groups.flatMap((group) => group.dogs) ?? [];
  }

  protected statusLabel(value: string): string {
    const labels: Record<string, string> = {
      not_recorded: 'Not recorded',
      matches_plan: 'Matches plan',
      modified: 'Modified from plan',
      not_run: 'Not run',
      context_only: 'Plan context',
    };
    return labels[value] ?? value;
  }

  protected sourceLabel(value: string): string {
    const labels: Record<string, string> = {
      planned: 'Planned',
      manual: 'Manual',
      seeded: 'Existing actual',
      unlinked: 'Actual · plan removed',
    };
    return labels[value] ?? value;
  }

  protected activityLabel(value: string): string {
    return value.replaceAll('_', ' ').replace(/^./, (character) => character.toUpperCase());
  }

  protected retry(): void {
    this.load(this.selectedDate);
  }

  private load(date: string): void {
    this.loading.set(true);
    this.pageError.set('');
    this.successMessage.set('');
    this.pendingDeleteId.set(null);
    this.highlightedDogId.set(null);
    this.entries.getEntry(date).subscribe({
      next: (entry) => {
        this.acceptEntry(entry);
        this.loading.set(false);
      },
      error: () => {
        this.loading.set(false);
        this.pageError.set('Daily Entry could not be loaded. Check the demo API and try again.');
      },
    });
  }

  private acceptEntry(entry: DailyEntry): void {
    this.entry.set(entry);
    this.successMessage.set('');
  }

  private validDate(value: string | null): value is string {
    return !!value && /^\d{4}-\d{2}-\d{2}$/.test(value) && value >= SEASON_START && value <= SEASON_END;
  }

  private errorMessage(error: HttpErrorResponse): string {
    return error.error?.detail?.message ?? 'The actual-work change could not be saved.';
  }
}
