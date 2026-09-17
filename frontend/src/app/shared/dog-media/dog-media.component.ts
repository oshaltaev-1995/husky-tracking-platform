import { ChangeDetectionStrategy, Component, computed, input, signal } from '@angular/core';

export const DOG_MEDIA_VERSION = 'dog-media-v1';
const CANONICAL_PHOTO_KEY =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.webp$/i;

@Component({
  selector: 'ht-dog-media',
  template: `
    <div
      class="dog-media"
      [class.profile]="size() === 'profile'"
      [class.compact]="size() === 'compact'"
      [class.has-image]="imageSource()"
    >
      @if (imageSource(); as source) {
        <img
          [src]="source"
          [alt]="altText()"
          [attr.loading]="size() === 'profile' ? 'eager' : 'lazy'"
          [attr.fetchpriority]="size() === 'profile' ? 'high' : 'auto'"
          decoding="async"
          (error)="handleImageError()"
        />
      } @else {
        <div class="dog-media-fallback" role="img" [attr.aria-label]="altText()">
          <span aria-hidden="true">{{ initial() }}</span>
          <small aria-hidden="true">HT</small>
        </div>
      }
    </div>
  `,
  styleUrl: './dog-media.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DogMediaComponent {
  readonly name = input.required<string>();
  readonly photoKey = input<string | null>(null);
  readonly size = input<'card' | 'compact' | 'profile'>('card');
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
    this.failedPhotoKey.set(this.photoKey());
  }
}
