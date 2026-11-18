import { DOCUMENT } from '@angular/common';
import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  HostListener,
  inject,
  input,
  OnDestroy,
  output,
  signal,
  viewChild,
} from '@angular/core';

import { KennelPrintDocumentComponent } from './kennel-print-document.component';
import { KennelPrintProjection } from './kennel-print-projection';

export function kennelPrintTitle(snapshotDate: string): string {
  return `Husky Tracking · Kennel Map · ${snapshotDate}`;
}

@Component({
  selector: 'ht-kennel-print-preview',
  imports: [KennelPrintDocumentComponent],
  templateUrl: './kennel-print-preview.component.html',
  styleUrl: './kennel-print-preview.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KennelPrintPreviewComponent implements AfterViewInit, OnDestroy {
  readonly projection = input.required<KennelPrintProjection>();
  readonly closed = output<void>();
  protected readonly ready = signal(false);
  protected readonly nativePrinting = signal(false);
  protected readonly requestingPrint = signal(false);
  protected readonly printError = signal('');
  protected readonly printStatus = signal('');
  private readonly document = inject(DOCUMENT);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly paper = viewChild.required<ElementRef<HTMLElement>>('paper');
  private destroyed = false;
  private originalTitle = '';
  private ownedTitle = '';
  private windowBlurred = false;
  private printBlurObserved = false;
  private printFocusReturned = false;

  ngAfterViewInit(): void {
    this.originalTitle = this.document.title;
    // The same child document is already rendered; defer focus until this render ends.
    queueMicrotask(() => {
      if (this.destroyed) return;
      this.ready.set(true);
      if (!this.otherModal()) this.paper().nativeElement.focus({ preventScroll: true });
    });
  }

  ngOnDestroy(): void {
    this.destroyed = true;
    this.restoreTitle();
  }

  protected print(): void {
    if (!this.ready() || this.requestingPrint() || this.nativePrinting()) return;
    const window = this.document.defaultView;
    if (!window) return;
    this.printError.set('');
    this.printStatus.set('Use the browser dialog to print or save as PDF.');
    this.printBlurObserved = this.windowBlurred;
    this.printFocusReturned = false;
    this.requestingPrint.set(true);
    this.prepareTitle();
    try {
      window.print();
    } catch {
      this.nativePrinting.set(false);
      this.printError.set('The print dialog could not be opened. Try the browser Print command or try again.');
    } finally {
      // Returning from print is not proof that printing finished or a file was saved.
      // Keep this DOM and its print class until the preview is explicitly closed.
      if (!this.destroyed) {
        this.reconcileReturnedFocus();
        this.requestingPrint.set(false);
        if (!this.nativePrinting()) this.restoreTitle();
      }
    }
  }

  protected close(): void {
    if (!this.requestingPrint() && !this.nativePrinting()) this.closed.emit();
  }

  @HostListener('window:beforeprint')
  protected beforePrint(): void {
    if (this.destroyed) return;
    if (!this.requestingPrint() && !this.nativePrinting()) {
      this.printBlurObserved = this.windowBlurred;
      this.printFocusReturned = false;
    }
    this.prepareTitle();
    this.nativePrinting.set(true);
    this.printError.set('');
  }

  @HostListener('window:afterprint')
  protected afterPrint(): void {
    if (this.destroyed) return;
    this.finishNativePrint('Print dialog closed. You can print again or close this preview.');
  }

  @HostListener('window:blur')
  protected windowBlur(): void {
    if (this.destroyed) return;
    this.windowBlurred = true;
    if (this.nativePrinting() || this.requestingPrint()) {
      this.printBlurObserved = true;
      this.printFocusReturned = false;
    }
  }

  @HostListener('window:focus')
  protected windowFocus(): void {
    if (this.destroyed) return;
    this.windowBlurred = false;
    if (this.printBlurObserved && (this.nativePrinting() || this.requestingPrint())) {
      this.printFocusReturned = true;
      this.reconcileReturnedFocus();
    }
  }

  private reconcileReturnedFocus(): void {
    if (!this.printBlurObserved || !this.printFocusReturned || this.windowBlurred ||
      (!this.nativePrinting() && !this.requestingPrint())) return;
    const window = this.document.defaultView;
    // Some native dialogs return focus without afterprint. A mere focus event or
    // print() returning is insufficient, and active/unknown print media stays locked.
    if (typeof window?.matchMedia !== 'function' || window.matchMedia('print').matches) return;
    this.finishNativePrint('Returned to print preview. You can print again or close this preview.');
  }

  private finishNativePrint(status: string): void {
    this.nativePrinting.set(false);
    this.printBlurObserved = false;
    this.printFocusReturned = false;
    this.restoreTitle();
    this.printStatus.set(status);
    // Both Print and Cancel can produce afterprint; neither proves that a PDF exists.
    queueMicrotask(() => {
      if (!this.destroyed && !this.otherModal() && this.document.activeElement === this.document.body) {
        this.paper().nativeElement.focus({ preventScroll: true });
      }
    });
  }

  @HostListener('document:keydown', ['$event'])
  protected keydown(event: KeyboardEvent): void {
    if (this.destroyed || this.otherModal()) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      this.close();
    }
    if (event.key !== 'Tab' || event.altKey || event.ctrlKey || event.metaKey) return;
    const targets = this.focusableTargets();
    const first = targets[0], last = targets[targets.length - 1];
    if (!first || !last) { event.preventDefault(); return; }
    const current = this.document.activeElement;
    const outside = !targets.some((target) => target === current);
    if (event.shiftKey && (current === first || outside)) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && (current === last || outside)) {
      event.preventDefault();
      first.focus();
    }
  }

  @HostListener('document:focusin', ['$event'])
  protected containFocus(event: FocusEvent): void {
    if (!this.ready() || this.destroyed || this.nativePrinting() || this.otherModal()) return;
    const target = event.target as Node | null;
    if (target && !this.host.nativeElement.contains(target)) this.paper().nativeElement.focus({ preventScroll: true });
  }

  private focusableTargets(): HTMLElement[] {
    return Array.from(this.host.nativeElement.querySelectorAll<HTMLElement>(
      'button, a[href], input, select, textarea, [tabindex]',
    )).filter((target) => {
      const style = this.document.defaultView?.getComputedStyle(target);
      return target.tabIndex >= 0 && !target.matches(':disabled') &&
        !target.closest('[hidden], [inert], [aria-hidden="true"]') &&
        style?.display !== 'none' && style?.visibility !== 'hidden';
    });
  }

  private otherModal(): HTMLElement | undefined {
    return Array.from(this.document.querySelectorAll<HTMLElement>('[role="dialog"][aria-modal="true"]'))
      .find((dialog) => !this.host.nativeElement.contains(dialog) && !dialog.closest('[hidden], [inert], [aria-hidden="true"]'));
  }

  private prepareTitle(): void {
    if (this.document.title !== this.ownedTitle) this.originalTitle = this.document.title;
    this.ownedTitle = kennelPrintTitle(this.projection().snapshotDate);
    this.document.title = this.ownedTitle;
  }

  private restoreTitle(): void {
    if (this.document.title === this.ownedTitle) this.document.title = this.originalTitle;
  }
}
