import { ChangeDetectionStrategy, Component, input } from '@angular/core';

import { PrintPreviewLifecycle } from '../../shared/print-preview-lifecycle';
import { KennelPrintDocumentComponent } from './kennel-print-document.component';
import { KennelPrintProjection } from './kennel-print-projection';

export function kennelPrintTitle(snapshotDate: string): string {
  return `Husky Tracking · Kennel Map · ${snapshotDate}`;
}

@Component({
  selector: 'ht-kennel-print-preview',
  imports: [KennelPrintDocumentComponent],
  templateUrl: './kennel-print-preview.component.html',
  styleUrl: './kennel-print-preview.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KennelPrintPreviewComponent extends PrintPreviewLifecycle {
  readonly projection = input.required<KennelPrintProjection>();

  protected override printDocumentTitle(): string {
    return kennelPrintTitle(this.projection().snapshotDate);
  }
}
