import { DatePipe, DOCUMENT } from '@angular/common';
import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  EventEmitter,
  HostListener,
  Input,
  OnDestroy,
  Output,
  ViewChild,
  inject,
} from '@angular/core';

import { PlannedActivityActual } from '../../core/api/daily-entry.models';
import { CountLabelPipe } from '../../shared/count-label/count-label.pipe';

@Component({
  selector: 'ht-actual-plan-review',
  imports: [CountLabelPipe, DatePipe],
  templateUrl: './actual-plan-review.component.html',
  styleUrl: './actual-plan-review.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ActualPlanReviewComponent implements AfterViewInit, OnDestroy {
  private readonly document = inject(DOCUMENT);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private returnFocus: HTMLElement | null = null;

  @ViewChild('cancelButton') private cancelButton?: ElementRef<HTMLButtonElement>;
  @Input({ required: true }) entryDate!: string;
  @Input({ required: true }) activity!: PlannedActivityActual;
  @Input() saving = false;
  @Input() serverError = '';
  @Output() confirmed = new EventEmitter<void>();
  @Output() closed = new EventEmitter<void>();

  ngAfterViewInit(): void {
    this.returnFocus = this.document.activeElement as HTMLElement | null;
    this.document.body.classList.add('dialog-open');
    queueMicrotask(() => this.cancelButton?.nativeElement.focus());
  }

  ngOnDestroy(): void {
    this.document.body.classList.remove('dialog-open');
    queueMicrotask(() => this.returnFocus?.focus());
  }

  @HostListener('document:keydown.escape', ['$event'])
  protected onEscape(event: Event): void {
    event.preventDefault();
    this.close();
  }

  @HostListener('document:keydown.tab', ['$event'])
  protected trapFocus(event: Event): void {
    const keyboardEvent = event as KeyboardEvent;
    const focusable = Array.from(
      this.host.nativeElement.querySelectorAll<HTMLElement>(
        '.review-dialog button:not([disabled])',
      ),
    ).filter((element) => element.offsetParent !== null);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (keyboardEvent.shiftKey && this.document.activeElement === first) {
      keyboardEvent.preventDefault();
      last.focus();
    } else if (!keyboardEvent.shiftKey && this.document.activeElement === last) {
      keyboardEvent.preventDefault();
      first.focus();
    }
  }

  protected close(): void {
    if (!this.saving) this.closed.emit();
  }

  protected confirm(): void {
    if (!this.saving) this.confirmed.emit();
  }

  protected teamSummary(): string {
    if (!this.activity.team_count) return 'No saved team · selected dogs will be unpositioned';
    const teams = `${this.activity.team_count} saved ${
      this.activity.team_count === 1 ? 'team' : 'teams'
    }`;
    return `${teams} · ${this.activity.arranged_dog_count} arranged`;
  }
}
