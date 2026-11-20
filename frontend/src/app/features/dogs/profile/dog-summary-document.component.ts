import { DatePipe, DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, input, viewChild } from '@angular/core';

import { DogMediaComponent } from '../../../shared/dog-media/dog-media.component';
import { DogSummaryProjection } from './dog-summary-projection';

/** The same read-only document is used for preview and browser printing. */
@Component({
  selector: 'ht-dog-summary-document',
  imports: [DatePipe, DecimalPipe, DogMediaComponent],
  templateUrl: './dog-summary-document.component.html',
  styleUrl: './dog-summary-document.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DogSummaryDocumentComponent {
  readonly projection = input.required<DogSummaryProjection>();
  private readonly media = viewChild.required(DogMediaComponent);

  whenMediaReady(): Promise<void> {
    return this.media().whenReady();
  }

  protected calendarInstant(value: string | null): string | null {
    // DatePipe parses a date-only value at local midnight. Anchor domain calendar
    // dates in UTC before formatting so a viewer's timezone cannot change the day.
    return value ? `${value}T00:00:00Z` : null;
  }
}
