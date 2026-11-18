import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import { KennelMapLayer } from '../../core/api/kennel-map.models';
import { mapLayerLegend } from './kennel-map-presentation';

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
  protected readonly items = computed(() => mapLayerLegend(this.layer()));
}
