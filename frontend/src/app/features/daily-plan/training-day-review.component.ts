import { DatePipe, DOCUMENT } from '@angular/common';
import { AfterViewInit, ChangeDetectionStrategy, Component, ElementRef, EventEmitter, HostListener, Input, OnDestroy, Output, ViewChild, inject } from '@angular/core';

import { TrainingDayProposal } from '../../core/api/daily-plans.models';

export type TrainingDayReviewPhase = 'loading' | 'ready' | 'applying' | 'rejected' | 'unknown' | 'reconciling' | 'unavailable' | 'error';

/** Review is local UI only: the parent owns the one explicit apply request. */
@Component({
  selector: 'ht-training-day-review',
  imports: [DatePipe],
  templateUrl: './training-day-review.component.html',
  styleUrl: './training-day-review.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TrainingDayReviewComponent implements AfterViewInit, OnDestroy {
  private readonly document = inject(DOCUMENT);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private returnFocus: HTMLElement | null = null;
  private destroyed = false;
  private initialized = false;
  private hadDialogOpen = false;
  @ViewChild('content') private content?: ElementRef<HTMLElement>;
  @Input() proposal: TrainingDayProposal | null = null;
  @Input() phase: TrainingDayReviewPhase = 'loading';
  @Input() error = '';
  @Input() reconciledEmpty = false;
  @Input() returnFocusAllowed: () => boolean = () => true;
  @Output() closed = new EventEmitter<void>();
  @Output() applied = new EventEmitter<void>();
  @Output() reviewedAgain = new EventEmitter<void>();
  @Output() checkedCurrentDay = new EventEmitter<void>();
  @Output() openedCurrentDay = new EventEmitter<void>();

  protected get pending(): boolean {
    return this.phase === 'applying' || this.phase === 'reconciling';
  }

  ngAfterViewInit(): void {
    this.returnFocus = this.document.activeElement as HTMLElement | null;
    this.hadDialogOpen = this.document.body.classList.contains('dialog-open');
    this.document.body.classList.add('dialog-open');
    this.initialized = true;
    queueMicrotask(() => {
      if (!this.destroyed && !this.otherModal()) this.content?.nativeElement.focus({ preventScroll: true });
    });
  }

  ngOnDestroy(): void {
    this.destroyed = true;
    const current = this.document.activeElement;
    const ownedFocus = this.host.nativeElement.contains(current) || current === this.document.body;
    if (!this.hadDialogOpen && !this.otherModal()) this.document.body.classList.remove('dialog-open');
    queueMicrotask(() => {
      const focused = this.document.activeElement;
      const outsideFocus = focused !== this.document.body && focused?.isConnected && !this.host.nativeElement.contains(focused);
      if (ownedFocus && this.returnFocusAllowed() && !outsideFocus && !this.otherModal() &&
        !this.document.body.classList.contains('dialog-open') && this.returnFocus?.isConnected &&
        !this.returnFocus.matches(':disabled') && !this.returnFocus.closest('[hidden], [inert]')) {
        this.returnFocus.focus({ preventScroll: true });
      }
    });
  }

  protected close(): void {
    if (!this.pending) this.closed.emit();
  }

  protected apply(): void {
    if (this.phase === 'ready' && this.proposal?.available && this.proposal.precondition) this.applied.emit();
  }

  protected label(value: string | null): string {
    return value ? value.replaceAll('_', ' ').replace(/^./, (character) => character.toUpperCase()) : 'Not recorded';
  }

  protected roles(values: string[]): string {
    return values.map((value) => this.label(value)).join(' · ') || 'None recorded';
  }

  private otherModal(): HTMLElement | undefined {
    return Array.from(this.document.querySelectorAll<HTMLElement>('[role="dialog"][aria-modal="true"]'))
      .find((dialog) => !this.host.nativeElement.contains(dialog) && !dialog.closest('[hidden], [inert], [aria-hidden="true"]'));
  }

  private focusableTargets(): HTMLElement[] {
    return Array.from(this.host.nativeElement.querySelectorAll<HTMLElement>('button, a[href], [tabindex]'))
      .filter((target) => target.tabIndex >= 0 && !target.matches(':disabled') &&
        !target.closest('[hidden], [inert], [aria-hidden="true"]'));
  }

  @HostListener('document:focusin', ['$event'])
  protected containFocus(event: FocusEvent): void {
    if (!this.initialized || this.destroyed || this.otherModal()) return;
    const target = event.target as Node | null;
    if (target && !this.host.nativeElement.contains(target)) this.content?.nativeElement.focus({ preventScroll: true });
  }

  @HostListener('document:keydown', ['$event'])
  protected keydown(event: KeyboardEvent): void {
    if (this.destroyed || this.otherModal()) return;
    if (event.key === 'Escape') { event.preventDefault(); this.close(); }
    if (event.key !== 'Tab' || event.altKey || event.ctrlKey || event.metaKey) return;
    const targets = this.focusableTargets();
    const first = targets[0], last = targets[targets.length - 1];
    if (!first || !last) { event.preventDefault(); return; }
    const current = this.document.activeElement;
    const outside = !targets.some((target) => target === current);
    if (event.shiftKey && (current === first || outside)) { event.preventDefault(); last.focus(); }
    if (!event.shiftKey && (current === last || outside)) { event.preventDefault(); first.focus(); }
  }
}
