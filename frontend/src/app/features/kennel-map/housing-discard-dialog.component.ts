import { DOCUMENT } from '@angular/common';
import { AfterViewInit, ChangeDetectionStrategy, Component, ElementRef, EventEmitter, HostListener, Input, OnDestroy, Output, ViewChild, inject } from '@angular/core';

@Component({
  selector: 'ht-housing-discard-dialog',
  template: `
    <div class="dialog-backdrop">
      <section class="surface discard-dialog" role="dialog" aria-modal="true" aria-labelledby="housing-discard-title" aria-describedby="housing-discard-description">
        <h2 id="housing-discard-title">Discard housing changes?</h2>
        <p id="housing-discard-description">{{ uncertain ? 'A save may already have reached the server. Leaving cannot cancel or roll it back. Reload housing before making further changes.' : 'Your unsaved housing preview will be discarded. No housing moves will be sent.' }}</p>
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
  @ViewChild('keep') private keep?: ElementRef<HTMLButtonElement>;
  @Input() uncertain = false;
  @Output() decided = new EventEmitter<boolean>();

  ngAfterViewInit(): void {
    this.returnFocus = this.document.activeElement as HTMLElement | null;
    this.document.body.classList.add('dialog-open');
    queueMicrotask(() => this.keep?.nativeElement.focus());
  }
  ngOnDestroy(): void {
    this.document.body.classList.remove('dialog-open');
    queueMicrotask(() => { if (this.returnFocus?.isConnected) this.returnFocus.focus(); });
  }
  @HostListener('document:keydown', ['$event'])
  protected keydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') { event.preventDefault(); this.decided.emit(false); }
    if (event.key !== 'Tab') return;
    const buttons = this.host.nativeElement.querySelectorAll<HTMLButtonElement>('button');
    const first = buttons[0], last = buttons[buttons.length - 1];
    if (event.shiftKey && this.document.activeElement === first) { event.preventDefault(); last.focus(); }
    if (!event.shiftKey && this.document.activeElement === last) { event.preventDefault(); first.focus(); }
  }
}
