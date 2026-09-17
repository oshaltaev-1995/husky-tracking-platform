import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import {
  KennelMapLayer,
  KennelMapLocation,
} from '../../core/api/kennel-map.models';
import { ResidentDogComponent } from './resident-dog.component';

@Component({
  selector: 'ht-kennel-location-card',
  imports: [ResidentDogComponent],
  template: `
    <article
      class="location-card"
      [class.puppy-area]="location().location_type === 'puppy_area'"
      [class.highlighted]="containsHighlight()"
      [attr.aria-label]="location().display_name + ', ' + occupancyLabel()"
    >
      <header>
        <div>
          <p>{{ location().location_type === 'puppy_area' ? 'Puppy area' : 'Enclosure' }}</p>
          <h3>{{ location().code }}</h3>
        </div>
        <span>{{ occupancyLabel() }}</span>
      </header>
      @if (location().location_type === 'puppy_area') {
        <p class="area-detail">{{ litterLabel() }}</p>
      }
      <div class="resident-list">
        @for (dog of location().residents; track dog.id) {
          <ht-resident-dog
            [resident]="dog"
            [layer]="layer()"
            [highlighted]="dog.id === highlightedDogId()"
          />
        } @empty {
          <p class="vacant">No residents on this date</p>
        }
      </div>
    </article>
  `,
  styleUrl: './kennel-location-card.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KennelLocationCardComponent {
  readonly location = input.required<KennelMapLocation>();
  readonly layer = input.required<KennelMapLayer>();
  readonly highlightedDogId = input<string | null>(null);

  protected readonly containsHighlight = computed(() =>
    this.location().residents.some((dog) => dog.id === this.highlightedDogId()),
  );

  protected occupancyLabel(): string {
    return `${this.location().residents.length} / ${this.location().capacity}`;
  }

  protected litterLabel(): string {
    const litters = [...new Set(this.location().residents.map((dog) => dog.litter_code).filter(Boolean))];
    return litters.length ? `${litters.join(' + ')}-litter residents` : this.location().display_name;
  }
}
