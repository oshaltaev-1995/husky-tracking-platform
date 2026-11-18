import { DOCUMENT } from '@angular/common';
import { AfterViewInit, ChangeDetectionStrategy, Component, ElementRef, EventEmitter, HostListener, Input, OnDestroy, Output, ViewChild, inject } from '@angular/core';

@Component({
  selector: 'ht-housing-discard-dialog',
  template: `
    <div class="dialog-backdrop">
      <section class="surface discard-dialog" role="dialog" aria-modal="true" aria-labelledby="housing-discard-title" aria-describedby="housing-discard-description">
        <h2 id="housing-discard-title">Discard housing changes?</h2>
        <p id="housing-discard-description">{{ uncertain ? 'A save may already have reached the server. Leaving cannot cancel or roll it back. Reload housing before making further changes.' : 'Discard the local preview and continue. This action does not submit housing moves.' }}</p>
        <div class="actions">
          <button #keep class="button secondary" type="button" (click)="decided.emit(false)">Keep editing</button>
          <button class="button primary" type="button" (click)="decided.emit(true)">Discard changes</button>
        </div>
      </section>
    </div>
  `,
  styles: `
    .dialog-backdrop { position: fixed; inset: 0; z-index: 110; display: grid; place-items: center; padding: var(--space-4); background: rgb(15 35 33 / 45%); }
    .discard-dialog { width: min(100%, 30rem); padding: var(--space-6); max-height: 90dvh; overflow: auto; }
    h2 { margin-top: 0; } p { line-height: 1.6; } .actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: var(--space-3); }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HousingDiscardDialogComponent implements AfterViewInit, OnDestroy {
  private readonly document = inject(DOCUMENT);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private returnFocus: HTMLElement | null = null;
  private destroyed = false;
  private initialized = false;
  private hadDialogOpen = false;
  @ViewChild('keep') private keep?: ElementRef<HTMLButtonElement>;
  @Input() uncertain = false;
  @Output() decided = new EventEmitter<boolean>();

  ngAfterViewInit(): void {
    this.returnFocus = this.document.activeElement as HTMLElement | null;
    this.hadDialogOpen = this.document.body.classList.contains('dialog-open');
    this.document.body.classList.add('dialog-open');
    this.initialized = true;
    queueMicrotask(() => { if (!this.destroyed && !this.otherModal()) this.keep?.nativeElement.focus(); });
  }
  ngOnDestroy(): void {
    this.destroyed = true;
    const current = this.document.activeElement;
    const ownedFocus = this.host.nativeElement.contains(current) || current === this.document.body;
    if (!this.hadDialogOpen && !this.otherModal()) this.document.body.classList.remove('dialog-open');
    queueMicrotask(() => {
      const focused = this.document.activeElement;
      const outsideFocus = focused !== this.document.body && focused?.isConnected && !this.host.nativeElement.contains(focused);
      if (ownedFocus && !outsideFocus && !this.otherModal() &&
        !this.document.body.classList.contains('dialog-open') && this.returnFocus?.isConnected &&
        !this.returnFocus.matches(':disabled') && !this.returnFocus.closest('[hidden], [inert]')) {
        this.returnFocus.focus({ preventScroll: true });
      }
    });
  }

  private focusableTargets(): HTMLElement[] {
    return Array.from(this.host.nativeElement.querySelectorAll<HTMLElement>(
      'button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]',
    )).filter((target) => target.tabIndex >= 0 && !target.matches(':disabled') && !target.closest('[hidden], [inert], [aria-hidden="true"]'));
  }

  private otherModal(): HTMLElement | undefined {
    return Array.from(this.document.querySelectorAll<HTMLElement>('[role="dialog"][aria-modal="true"]'))
      .find((dialog) => !this.host.nativeElement.contains(dialog) && !dialog.closest('[hidden], [inert], [aria-hidden="true"]'));
  }

  @HostListener('document:focusin', ['$event'])
  protected containFocus(event: FocusEvent): void {
    if (!this.initialized || this.destroyed || this.otherModal()) return;
    const target = event.target as Node | null;
    if (target && !this.host.nativeElement.contains(target)) this.focusableTargets()[0]?.focus({ preventScroll: true });
  }

  @HostListener('document:keydown', ['$event'])
  protected keydown(event: KeyboardEvent): void {
    if (this.destroyed || this.otherModal()) return;
    if (event.key === 'Escape') { event.preventDefault(); this.decided.emit(false); }
    if (event.key !== 'Tab') return;
    const targets = this.focusableTargets();
    const first = targets[0], last = targets[targets.length - 1];
    if (!first || !last) { event.preventDefault(); return; }
    const current = this.document.activeElement;
    const outside = !targets.some((target) => target === current);
    if (event.shiftKey && (current === first || outside)) { event.preventDefault(); last.focus(); }
    if (!event.shiftKey && (current === last || outside)) { event.preventDefault(); first.focus(); }
  }
}
