import { ChangeDetectionStrategy, Component, computed, DestroyRef, effect, ElementRef, inject, input, signal, untracked, viewChild, ChangeDetectorRef } from '@angular/core';
import { DOCUMENT } from '@angular/common';
import { DogPhotoViewerComponent } from './dog-photo-viewer.component';

export const DOG_MEDIA_VERSION = 'dog-media-v1';
export const DOG_MEDIA_PRINT_TIMEOUT_MS = 8000;
const CANONICAL_PHOTO_KEY =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.webp$/i;

@Component({
  selector: 'ht-dog-media',
  imports: [DogPhotoViewerComponent],
  template: `
    <div
      class="dog-media"
      [class.profile]="size() === 'profile'"
      [class.compact]="size() === 'compact'"
      [class.has-image]="imageSource()"
    >
      @if (imageSource(); as source) {
        <img
          #portrait
          [src]="source"
          [alt]="altText()"
          [attr.loading]="size() === 'profile' ? 'eager' : 'lazy'"
          [attr.fetchpriority]="size() === 'profile' ? 'high' : 'auto'"
          decoding="async"
          (error)="handleImageError()"
        />
        @if (expandable()) {
          <button class="photo-enlarge" type="button" [attr.aria-label]="'Enlarge portrait of ' + name()" (click)="openViewer()">
            <span>Enlarge photo <span aria-hidden="true">↗</span></span>
          </button>
        }
      } @else {
        <div class="dog-media-fallback" role="img" [attr.aria-label]="altText()">
          <span aria-hidden="true">{{ initial() }}</span>
          <small aria-hidden="true">HT</small>
        </div>
      }
    </div>
    @if (viewer(); as photo) {
      <ht-dog-photo-viewer [name]="photo.name" [source]="photo.source" (closed)="closeViewer(true)" />
    }
  `,
  styleUrl: './dog-media.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DogMediaComponent {
  readonly name = input.required<string>();
  readonly photoKey = input<string | null>(null);
  readonly size = input<'card' | 'compact' | 'profile'>('card');
  readonly expandable = input(false);
  protected readonly viewer = signal<{ name: string; source: string } | null>(null);
  private readonly photoViewer = viewChild(DogPhotoViewerComponent);
  private readonly document = inject(DOCUMENT);
  private readonly portrait = viewChild<ElementRef<HTMLImageElement>>('portrait');
  private readonly changeDetector = inject(ChangeDetectorRef);
  private readonly destroyRef = inject(DestroyRef);
  private readonly pending = new Set<() => void>();
  private destroyed = false;

  constructor() {
    effect(() => {
      this.name();
      this.photoKey();
      this.expandable();
      // Identity/media replacement invalidates the frozen view, never retargets it.
      untracked(() => this.closeViewer(false));
    });
    this.destroyRef.onDestroy(() => {
      this.destroyed = true;
      for (const cancel of this.pending) cancel();
    });
  }

  protected openViewer(): void {
    const source = this.imageSource();
    if (!this.expandable() || !source || this.destroyed || this.document.querySelector('[role="dialog"][aria-modal="true"]')) return;
    this.viewer.set({ name: this.name(), source });
  }

  closeViewer(restoreFocus = false): void {
    if (!restoreFocus) this.photoViewer()?.dismissForContextChange();
    this.viewer.set(null);
  }

  /** Opt-in print readiness. Ordinary registry media remains lazy and unchanged. */
  whenReady(): Promise<void> {
    const image = this.portrait()?.nativeElement;
    const key = this.photoKey();
    if (!image || !this.imageSource() || this.destroyed) return Promise.resolve();
    return new Promise<void>((resolve) => {
      let settled = false;
      const finish = (failed = false) => {
        if (settled) return;
        settled = true;
        clearTimeout(timeout);
        image.removeEventListener('load', loaded);
        image.removeEventListener('error', failedLoad);
        this.pending.delete(cancel);
        // A late load/decode belongs only to this component and this exact image.
        if (failed && !this.destroyed && this.photoKey() === key && this.portrait()?.nativeElement === image) {
          this.failedPhotoKey.set(key);
          this.changeDetector.detectChanges();
        }
        resolve();
      };
      const cancel = () => finish();
      const loaded = () => {
        if (!image.naturalWidth) { finish(true); return; }
        if (typeof image.decode === 'function') image.decode().then(() => finish(), () => finish(true));
        else finish();
      };
      const failedLoad = () => finish(true);
      const timeout = setTimeout(() => finish(true), DOG_MEDIA_PRINT_TIMEOUT_MS);
      this.pending.add(cancel);
      image.addEventListener('load', loaded);
      image.addEventListener('error', failedLoad);
      if (image.complete) loaded();
    });
  }

  private readonly failedPhotoKey = signal<string | null>(null);

  protected readonly altText = computed(() => `Portrait of ${this.name()}`);
  protected readonly imageSource = computed(() => {
    const key = this.photoKey();
    if (!key || !CANONICAL_PHOTO_KEY.test(key) || this.failedPhotoKey() === key) {
      return null;
    }
    return `/media/dogs/${encodeURIComponent(key)}?v=${DOG_MEDIA_VERSION}`;
  });

  protected initial() {
    return this.name().slice(0, 1).toUpperCase();
  }

  protected handleImageError() {
    this.closeViewer(false);
    this.failedPhotoKey.set(this.photoKey());
  }
}
