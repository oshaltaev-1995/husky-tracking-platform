import { ChangeDetectionStrategy, Component, input } from '@angular/core';

@Component({
  selector: 'ht-dog-media',
  template: `
    <div class="dog-media" [class.profile]="size() === 'profile'" [class.compact]="size() === 'compact'" role="img" [attr.aria-label]="name() + ' image placeholder'">
      <span aria-hidden="true">{{ initial() }}</span>
      <small aria-hidden="true">HT</small>
    </div>
  `,
  styleUrl: './dog-media.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DogMediaComponent {
  readonly name = input.required<string>();
  readonly size = input<'card' | 'compact' | 'profile'>('card');

  protected initial() {
    return this.name().slice(0, 1).toUpperCase();
  }
}
