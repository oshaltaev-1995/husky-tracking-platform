import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import { KennelMapLayer } from '../../core/api/kennel-map.models';

interface LegendItem {
  label: string;
  marker: string;
  tone: string;
}

const LEGENDS: Record<KennelMapLayer, LegendItem[]> = {
  default: [
    { label: 'Class and sex · unavailable status marked', marker: 'D', tone: 'default' },
  ],
  gender: [
    { label: 'Female', marker: 'F', tone: 'female' },
    { label: 'Male', marker: 'M', tone: 'male' },
  ],
  neutered: [
    { label: 'Intact', marker: 'I', tone: 'intact' },
    { label: 'Neutered / spayed', marker: 'N', tone: 'neutered' },
  ],
  class: [
    { label: 'Puppy', marker: 'P', tone: 'puppy' },
    { label: 'Junior', marker: 'J', tone: 'junior' },
    { label: 'Training', marker: 'T', tone: 'training' },
    { label: 'Standard', marker: 'S', tone: 'standard' },
  ],
  unavailable: [
    { label: 'Available', marker: 'A', tone: 'available' },
    { label: 'Injured', marker: 'I', tone: 'injured' },
    { label: 'Rest', marker: 'R', tone: 'rest' },
    { label: 'Restricted', marker: 'X', tone: 'restricted' },
    { label: 'Retired', marker: 'T', tone: 'retired' },
  ],
};

@Component({
  selector: 'ht-map-legend',
  template: `
    @if (items().length) {
      <section class="map-legend" [attr.aria-label]="layer() + ' layer legend'">
        <span class="legend-label">Legend</span>
        <div class="legend-items">
          @for (item of items(); track item.label) {
            <span class="legend-item" [attr.data-tone]="item.tone">
              <b aria-hidden="true">{{ item.marker }}</b>{{ item.label }}
            </span>
          }
        </div>
      </section>
    }
  `,
  styleUrl: './map-legend.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MapLegendComponent {
  readonly layer = input.required<KennelMapLayer>();
  protected readonly items = computed(() => LEGENDS[this.layer()]);
}
