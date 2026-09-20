import { DatePipe, DecimalPipe, TitleCasePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input, linkedSignal } from '@angular/core';

import { DogProfile, DogWork } from '../../../core/api/dogs.models';

@Component({
  selector: 'ht-dog-work',
  imports: [DatePipe, DecimalPipe, TitleCasePipe],
  template: `
    <section class="work-heading"><div><p class="eyebrow">Winter 2025–2026</p><h2>Season workload</h2></div><p>Every kilometre and start derives from canonical session participation.</p></section>
    @if (work().summary.starts) {
      <section class="work-summary" aria-label="Season work summary">
        <div class="primary"><strong>{{ work().summary.total_km }}</strong><span>Total km</span></div>
        <div><strong>{{ work().summary.starts }}</strong><span>Starts</span></div>
        <div><strong>{{ work().summary.starts_5km }}</strong><span>5 km starts</span></div>
        <div><strong>{{ work().summary.starts_10km }}</strong><span>10 km starts</span></div>
        <div><strong>{{ work().summary.average_km_per_start | number: '1.1-1' }}</strong><span>Average km</span></div>
        <div><strong>{{ work().summary.last_work_date | date: 'MMM d' }}</strong><span>Last work</span></div>
      </section>
      <section class="work-panel"><div class="section-heading"><div><p class="eyebrow">Weekly rhythm</p><h2>Distance by week</h2></div><span>Maximum {{ maxWeeklyKm() }} km</span></div><div class="week-chart" aria-label="Weekly work distance">
        @for (week of chronologicalWeeks(); track week.week_start) { <div class="week-bar"><div class="bar-track"><span [style.height.%]="week.total_km / maxWeeklyKm() * 100"></span></div><small>{{ week.week_start | date: 'MMM d' }}</small><strong>{{ week.total_km }} km</strong></div> }
      </div></section>
      <section class="work-panel"><div class="section-heading"><div><p class="eyebrow">Ledger</p><h2>Work history</h2></div><span>{{ work().season_start | date: 'mediumDate' }} – {{ work().season_end | date: 'mediumDate' }}</span></div><div id="work-history-list" class="work-list">
        @for (entry of visibleEntries(); track $index) { <article><time [attr.datetime]="entry.date"><strong>{{ entry.date | date: 'MMM d' }}</strong><small>{{ entry.date | date: 'yyyy' }}</small></time><div><strong>{{ entry.label || 'Sled training' }}</strong><small>{{ entry.activity_type.replace('_', ' ') | titlecase }}</small></div><span>{{ entry.role ? (entry.role | titlecase) : 'Participant' }}</span><b>{{ entry.distance_km }} km</b></article> }
      </div>@if (work().entries.length > 5) { <button class="work-disclosure" type="button" [attr.aria-expanded]="showAll()" aria-controls="work-history-list" (click)="showAll.set(!showAll())">{{ showAll() ? 'Show fewer' : 'Show all ' + work().entries.length + ' records' }}</button> }</section>
    } @else {
      <section class="zero-work"><div class="zero-mark" aria-hidden="true">0</div><div><p class="eyebrow">No starts recorded</p><h2>No regular sled work during this demo season.</h2><p>{{ zeroWorkExplanation() }}</p></div></section>
    }
  `,
  styleUrl: './work.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class WorkComponent {
  readonly dog = input.required<DogProfile>();
  readonly work = input.required<DogWork>();
  protected readonly showAll = linkedSignal({ source: this.work, computation: () => false });
  protected readonly visibleEntries = computed(() => this.showAll() ? this.work().entries : this.work().entries.slice(0, 5));
  protected readonly chronologicalWeeks = computed(() => [...this.work().weekly].reverse());
  protected readonly maxWeeklyKm = computed(() => Math.max(...this.work().weekly.map((week) => week.total_km), 1));

  protected zeroWorkExplanation() {
    const dog = this.dog();
    if (dog.state.dog_class === 'puppy') return 'Puppies are not eligible for regular 5 or 10 km sled sessions.';
    if (dog.state.dog_class === 'junior') return 'Junior dogs are intentionally kept out of regular sled workload in this demo season.';
    if (dog.state.availability === 'retired') return 'This dog is operationally retired and remains an active kennel resident.';
    return 'This historical record has no canonical work participation in the selected season.';
  }
}
