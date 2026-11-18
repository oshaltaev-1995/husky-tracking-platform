import { DatePipe, DOCUMENT } from '@angular/common';
import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  effect,
  ElementRef,
  HostListener,
  inject,
  input,
  OnDestroy,
  output,
  signal,
  viewChild,
} from '@angular/core';

import { KennelMapLocation } from '../../core/api/kennel-map.models';
import { CountLabelPipe } from '../../shared/count-label/count-label.pipe';
import { PendingHousingMove } from './housing-move-draft';

@Component({
  selector: 'ht-housing-move-review',
  imports: [CountLabelPipe, DatePipe],
  templateUrl: './housing-move-review.component.html',
  styleUrl: './housing-move-review.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HousingMoveReviewComponent implements AfterViewInit, OnDestroy {
  readonly effectiveDate = input.required<string>();
  readonly changes = input.required<PendingHousingMove[]>();
  readonly locations = input.required<KennelMapLocation[]>();
  readonly saving = input(false);
  readonly serverError = input('');
  readonly confirmed = output<void>();
  readonly cancelled = output<void>();

  private readonly document = inject(DOCUMENT);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly reviewBody = viewChild.required<ElementRef<HTMLElement>>('reviewBody');
  private returnFocus: HTMLElement | null = null;
  private destroyed = false;
  private hadDialogOpen = false;
  protected readonly submitted = signal(false);

  constructor() {
    effect(() => {
      if (!this.saving()) this.submitted.set(false);
    });
  }

  ngAfterViewInit(): void {
    this.returnFocus = this.document.activeElement as HTMLElement | null;
    this.hadDialogOpen = this.document.body.classList.contains('dialog-open');
    this.document.body.classList.add('dialog-open');
    queueMicrotask(() => {
      if (!this.destroyed) this.reviewBody().nativeElement.focus({ preventScroll: true });
    });
  }

  ngOnDestroy(): void {
    this.destroyed = true;
    // Browsers may already have blurred the removed dialog to body before this hook.
    const hadFocus = this.host.nativeElement.contains(this.document.activeElement) || this.document.activeElement === this.document.body;
    if (!this.hadDialogOpen) this.document.body.classList.remove('dialog-open');
    queueMicrotask(() => {
      if (hadFocus && this.returnFocus?.isConnected && !this.document.body.classList.contains('dialog-open')) {
        this.returnFocus.focus();
      }
    });
  }

  @HostListener('document:keydown.escape', ['$event'])
  protected onEscape(event: Event): void {
    event.preventDefault();
    this.cancel();
  }

  @HostListener('document:keydown', ['$event'])
  protected trapFocus(event: Event): void {
    const keyboardEvent = event as KeyboardEvent;
    if (keyboardEvent.key !== 'Tab' || keyboardEvent.altKey || keyboardEvent.ctrlKey || keyboardEvent.metaKey) return;
    const dialog = this.host.nativeElement.querySelector<HTMLElement>('.review-dialog');
    if (!dialog) return;
    const focusable = Array.from(dialog.querySelectorAll<HTMLElement>(
      'button, a[href], input, select, textarea, [tabindex]',
    )).filter((element) => {
      const style = this.document.defaultView?.getComputedStyle(element);
      return element.tabIndex >= 0 && !element.matches(':disabled') &&
        !element.closest('[hidden], [inert]') &&
        style?.display !== 'none' && style?.visibility !== 'hidden';
    });
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (!first || !last) {
      keyboardEvent.preventDefault();
      return;
    }
    const current = this.document.activeElement;
    if (keyboardEvent.shiftKey && (current === first || !dialog.contains(current))) {
      keyboardEvent.preventDefault();
      last.focus();
    } else if (!keyboardEvent.shiftKey && (current === last || !dialog.contains(current))) {
      keyboardEvent.preventDefault();
      first.focus();
    }
  }

  protected cancel(): void {
    if (this.saving() || !this.submitted()) this.cancelled.emit();
  }

  protected confirm(): void {
    if (this.saving() || this.submitted() || this.changes().length === 0) return;
    this.submitted.set(true);
    this.confirmed.emit();
  }
}
