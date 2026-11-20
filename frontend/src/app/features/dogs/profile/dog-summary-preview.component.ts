import { ChangeDetectionStrategy, Component, input, viewChild } from '@angular/core';

import { PrintPreviewLifecycle } from '../../../shared/print-preview-lifecycle';
import { DogSummaryDocumentComponent } from './dog-summary-document.component';
import { DogSummaryProjection } from './dog-summary-projection';

export function dogSummaryTitle(name: string, snapshotDate: string): string {
  return `Husky Tracking · Dog Summary · ${name} · ${snapshotDate}`;
}

@Component({
  selector: 'ht-dog-summary-preview',
  imports: [DogSummaryDocumentComponent],
  templateUrl: './dog-summary-preview.component.html',
  styleUrl: './dog-summary-preview.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DogSummaryPreviewComponent extends PrintPreviewLifecycle {
  readonly projection = input.required<DogSummaryProjection>();
  private readonly summaryDocument = viewChild.required(DogSummaryDocumentComponent);

  protected override printDocumentTitle(): string {
    return dogSummaryTitle(this.projection().name, this.projection().snapshotDate);
  }

  protected override prepareContent(): Promise<void> {
    return this.summaryDocument().whenMediaReady();
  }
}
