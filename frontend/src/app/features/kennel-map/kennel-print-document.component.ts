import { DatePipe, NgTemplateOutlet } from '@angular/common';
import { ChangeDetectionStrategy, Component, input } from '@angular/core';

import { CountLabelPipe } from '../../shared/count-label/count-label.pipe';
import { KennelPrintProjection } from './kennel-print-projection';

@Component({
  selector: 'ht-kennel-print-document',
  imports: [CountLabelPipe, DatePipe, NgTemplateOutlet],
  templateUrl: './kennel-print-document.component.html',
  styleUrl: './kennel-print-document.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KennelPrintDocumentComponent {
  readonly projection = input.required<KennelPrintProjection>();
}
