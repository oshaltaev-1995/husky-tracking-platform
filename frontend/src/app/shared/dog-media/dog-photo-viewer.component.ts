import { DOCUMENT } from '@angular/common';
import { AfterViewInit, ChangeDetectionStrategy, Component, ElementRef, HostListener, inject, input, OnDestroy, output, signal, viewChild } from '@angular/core';

/** View-only portrait: the caller freezes the existing validated media URL. */
@Component({
  selector: 'ht-dog-photo-viewer',
  template: `
    <section class="photo-viewer" role="dialog" aria-modal="true" aria-labelledby="dog-photo-title">
      <header>
        <h2 id="dog-photo-title">{{ name() }}</h2>
        <button #closeButton class="button secondary" type="button" aria-label="Close portrait" (click)="closed.emit()">
          <span aria-hidden="true">×</span> Close
        </button>
      </header>
      <div class="photo-stage">
        @if (state() !== 'error') {
          <img #portrait [src]="source()" [alt]="'Portrait of ' + name()" [class.loaded]="state() === 'ready'"
            (load)="imageLoaded($event)" (error)="imageFailed($event)" />
        }
        @if (state() === 'loading') { <p class="photo-status" role="status">Loading portrait…</p> }
        @if (state() === 'error') { <p class="photo-status" role="alert">This portrait could not be loaded. Close this view to return to the profile.</p> }
      </div>
      <p class="photo-caption">Full portrait · Press Escape to close</p>
    </section>
  `,
  styleUrl: './dog-photo-viewer.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DogPhotoViewerComponent implements AfterViewInit, OnDestroy {
  readonly name = input.required<string>();
  readonly source = input.required<string>();
  readonly closed = output<void>();
  protected readonly state = signal<'loading' | 'ready' | 'error'>('loading');
  private readonly document = inject(DOCUMENT);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly closeButton = viewChild.required<ElementRef<HTMLButtonElement>>('closeButton');
  private readonly portrait = viewChild<ElementRef<HTMLImageElement>>('portrait');
  private trigger: HTMLElement | null = null;
  private hadPhotoOpen = false;
  private destroyed = false;
  private initialized = false;
  private restoreFocus = true;

  ngAfterViewInit(): void {
    this.trigger = this.document.activeElement as HTMLElement | null;
    this.hadPhotoOpen = this.document.body.classList.contains('ht-dog-photo-open');
    this.document.body.classList.add('ht-dog-photo-open');
    this.initialized = true;
    queueMicrotask(() => {
      if (!this.destroyed && !this.otherModal()) this.closeButton().nativeElement.focus({ preventScroll: true });
    });
  }

  /** Context replacement must not return focus to a superseded profile. */
  dismissForContextChange(): void {
    this.restoreFocus = false;
  }

  ngOnDestroy(): void {
    this.destroyed = true;
    const ownedFocus = this.host.nativeElement.contains(this.document.activeElement) || this.document.activeElement === this.document.body;
    // A Reset/print dialog may replace this view. Its scroll lock has a separate owner.
    if (!this.hadPhotoOpen) this.document.body.classList.remove('ht-dog-photo-open');
    queueMicrotask(() => {
      const current = this.document.activeElement;
      const outsideFocus = current !== this.document.body && current?.isConnected && !this.host.nativeElement.contains(current);
      if (this.restoreFocus && ownedFocus && !outsideFocus && !this.otherModal() &&
        this.trigger?.isConnected && !this.trigger.matches(':disabled') && !this.trigger.closest('[hidden], [inert]')) {
        this.trigger.focus({ preventScroll: true });
      }
    });
  }

  private currentImage(event: Event): event is Event & { target: HTMLImageElement } {
    return !this.destroyed && event.target === this.portrait()?.nativeElement &&
      this.portrait()?.nativeElement.getAttribute('src') === this.source();
  }

  protected imageLoaded(event: Event): void {
    if (this.currentImage(event)) this.state.set(event.target.naturalWidth ? 'ready' : 'error');
  }

  protected imageFailed(event: Event): void {
    if (this.currentImage(event)) this.state.set('error');
  }

  private otherModal(): HTMLElement | undefined {
    return Array.from(this.document.querySelectorAll<HTMLElement>('[role="dialog"][aria-modal="true"]'))
      .find((dialog) => !this.host.nativeElement.contains(dialog) && !dialog.closest('[hidden], [inert], [aria-hidden="true"]'));
  }

  @HostListener('document:keydown', ['$event'])
  protected keydown(event: KeyboardEvent): void {
    if (this.destroyed || this.otherModal()) return;
    if (event.key === 'Escape') { event.preventDefault(); this.closed.emit(); }
    if (event.key === 'Tab' && !event.altKey && !event.ctrlKey && !event.metaKey) {
      // Close is intentionally the only control: no gallery or custom zoom engine.
      event.preventDefault();
      this.closeButton().nativeElement.focus({ preventScroll: true });
    }
  }

  @HostListener('document:focusin', ['$event'])
  protected containFocus(event: FocusEvent): void {
    if (!this.initialized || this.destroyed || this.otherModal()) return;
    if (event.target && !this.host.nativeElement.contains(event.target as Node)) {
      this.closeButton().nativeElement.focus({ preventScroll: true });
    }
  }
}
