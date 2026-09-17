import { DatePipe, NgTemplateOutlet, TitleCasePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, input } from '@angular/core';

import { DogHistory } from '../../../core/api/dogs.models';

@Component({
  selector: 'ht-dog-history',
  imports: [DatePipe, NgTemplateOutlet, TitleCasePipe],
  template: `
    <section class="history-heading"><div><p class="eyebrow">Effective-dated record</p><h2>Domain history</h2></div><p>State is resolved against the fixed reference date, {{ history().reference_date | date: 'longDate' }}.</p></section>
    <div class="history-grid">
      <section class="timeline-panel"><div class="panel-title"><span>A</span><div><p class="eyebrow">Availability</p><h3>Operational status</h3></div></div><div class="timeline">@for (item of reversed(history().availability); track item.valid_from + item.value) { <ng-container [ngTemplateOutlet]="period" [ngTemplateOutletContext]="{ item }" /> }</div></section>
      <section class="timeline-panel"><div class="panel-title"><span>C</span><div><p class="eyebrow">Class</p><h3>Operational class</h3></div></div><div class="timeline">@for (item of reversed(history().classes); track item.valid_from + item.value) { <ng-container [ngTemplateOutlet]="period" [ngTemplateOutletContext]="{ item }" /> }</div></section>
      <section class="timeline-panel"><div class="panel-title"><span>H</span><div><p class="eyebrow">Housing</p><h3>Kennel moves</h3></div></div><div class="timeline">@for (item of reversed(history().housing); track item.valid_from + item.location.code) { <article [class.current]="item.is_current"><div class="timeline-dot" aria-hidden="true"></div><div><strong>{{ item.location.code }}</strong><small>{{ item.location.display_name }}</small>@if (item.note) { <p>{{ item.note }}</p> }<time>{{ item.valid_from | date: 'mediumDate' }} – {{ item.valid_to ? (item.valid_to | date: 'mediumDate') : 'Current' }}</time></div></article> } @empty { <p class="empty-copy">No housing history recorded.</p> }</div></section>
      <section class="timeline-panel"><div class="panel-title"><span>L</span><div><p class="eyebrow">Lifecycle</p><h3>Active and archive record</h3></div></div><div class="timeline">@for (item of reversed(history().lifecycle); track item.valid_from + item.value) { <ng-container [ngTemplateOutlet]="period" [ngTemplateOutletContext]="{ item }" /> } @if (history().archive; as archive) { <article class="archive-event"><div class="timeline-dot" aria-hidden="true"></div><div><strong>Archive: {{ reasonLabel(archive.reason) }}</strong>@if (archive.note) { <p>{{ archive.note }}</p> }<time>Effective {{ archive.archive_date | date: 'mediumDate' }}</time></div></article> }</div></section>
    </div>
    <ng-template #period let-item="item"><article [class.current]="item.is_current"><div class="timeline-dot" aria-hidden="true"></div><div><strong>{{ item.value | titlecase }}</strong>@if (item.note) { <p>{{ item.note }}</p> }<time>{{ item.valid_from | date: 'mediumDate' }} – {{ item.valid_to ? (item.valid_to | date: 'mediumDate') : 'Current' }}</time></div></article></ng-template>
  `,
  styleUrl: './history.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HistoryComponent {
  readonly history = input.required<DogHistory>();
  protected reversed<T>(items: T[]) {
    return [...items].reverse();
  }
  protected reasonLabel(reason: string) {
    return ({ euthanized: 'Euthanized', deceased: 'Died naturally', rehomed_to_guide: 'Rehomed to guide' } as Record<string, string>)[reason] ?? reason;
  }
}
