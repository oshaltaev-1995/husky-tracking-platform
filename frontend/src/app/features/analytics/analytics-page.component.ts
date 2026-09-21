import { AsyncPipe, DatePipe, DecimalPipe, TitleCasePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import {
  BehaviorSubject,
  catchError,
  combineLatest,
  distinctUntilChanged,
  map,
  of,
  shareReplay,
  startWith,
  switchMap,
} from 'rxjs';

import {
  AnalyticsDog,
  AnalyticsDogSort,
  AnalyticsOverview,
  AnalyticsQuery,
  PopulationBucket,
  PopulationCohort,
  WeeklyAnalytics,
} from '../../core/api/analytics.models';
import { AnalyticsService } from '../../core/api/analytics.service';
import { CountLabelPipe } from '../../shared/count-label/count-label.pipe';

const SEASON_START = '2025-12-01';
const SEASON_END = '2026-03-31';
const SORTS: AnalyticsDogSort[] = [
  'highest_km',
  'lowest_km',
  'most_starts',
  'fewest_starts',
  'name',
];

type TrendMetric = 'dog_km' | 'dog_starts' | 'dogs_worked';
type AnalyticsArea = 'population' | 'workload';

interface QuickRange {
  label: string;
  from: string;
  to: string;
}

@Component({
  selector: 'ht-analytics-page',
  imports: [AsyncPipe, CountLabelPipe, DatePipe, DecimalPipe, FormsModule, RouterLink, TitleCasePipe],
  templateUrl: './analytics-page.component.html',
  styleUrl: './analytics-page.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AnalyticsPageComponent {
  private readonly analytics = inject(AnalyticsService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly query = new BehaviorSubject<AnalyticsQuery>({
    from: SEASON_START,
    to: SEASON_END,
    sort: 'highest_km',
  });
  private readonly populationQuery = new BehaviorSubject(SEASON_END);
  private readonly workloadRefresh = new BehaviorSubject(0);

  protected activeArea: AnalyticsArea = 'workload';
  protected populationDate = SEASON_END;
  protected dateFrom = SEASON_START;
  protected dateTo = SEASON_END;
  protected search = '';
  protected dogClass = '';
  protected sort: AnalyticsDogSort = 'highest_km';
  protected trendMetric: TrendMetric = 'dog_km';
  protected readonly quickRanges: QuickRange[] = [
    { label: 'Full season', from: SEASON_START, to: SEASON_END },
    { label: 'December', from: '2025-12-01', to: '2025-12-31' },
    { label: 'January', from: '2026-01-01', to: '2026-01-31' },
    { label: 'February', from: '2026-02-01', to: '2026-02-28' },
    { label: 'March', from: '2026-03-01', to: '2026-03-31' },
  ];
  protected readonly state$ = combineLatest([
    this.query.pipe(distinctUntilChanged((a, b) => JSON.stringify(a) === JSON.stringify(b))),
    this.workloadRefresh,
  ]).pipe(
    switchMap(([query]) =>
      this.analytics.getAnalytics(query).pipe(
        map((data) => ({ kind: 'ready' as const, data })),
        startWith({ kind: 'loading' as const }),
        catchError(() => of({ kind: 'error' as const })),
      ),
    ),
    shareReplay({ bufferSize: 1, refCount: true }),
  );
  protected readonly populationState$ = this.populationQuery.pipe(
    switchMap((snapshotDate) =>
      this.analytics.getPopulation(snapshotDate).pipe(
        map((data) => ({ kind: 'ready' as const, data })),
        startWith({ kind: 'loading' as const }),
        catchError(() => of({ kind: 'error' as const })),
      ),
    ),
    shareReplay({ bufferSize: 1, refCount: true }),
  );

  constructor() {
    this.route.queryParamMap.subscribe((params) => {
      const rawFrom = params.get('from');
      const rawTo = params.get('to');
      const nextArea: AnalyticsArea = params.get('view') === 'population' ? 'population' : 'workload';
      const rawPopulationDate = params.get('date');
      const nextPopulationDate = this.validDate(rawPopulationDate) ? rawPopulationDate : SEASON_END;
      const nextFrom = this.validDate(rawFrom) ? rawFrom : SEASON_START;
      const nextTo = this.validDate(rawTo) && rawTo >= nextFrom ? rawTo : SEASON_END;
      const nextSort = SORTS.includes(params.get('sort') as AnalyticsDogSort)
        ? (params.get('sort') as AnalyticsDogSort)
        : 'highest_km';
      const nextClass = ['puppy', 'junior', 'training', 'standard'].includes(
        params.get('class') ?? '',
      )
        ? (params.get('class') ?? '')
        : '';
      const nextSearch = params.get('search')?.slice(0, 80) ?? '';
      this.dateFrom = nextFrom;
      this.dateTo = nextTo;
      this.sort = nextSort;
      this.dogClass = nextClass;
      this.search = nextSearch;
      this.activeArea = nextArea;
      this.populationDate = nextPopulationDate;
      if (this.populationQuery.value !== nextPopulationDate) {
        this.populationQuery.next(nextPopulationDate);
      }
      const nextQuery: AnalyticsQuery = {
        from: nextFrom,
        to: nextTo,
        sort: nextSort,
        dogClass: nextClass || undefined,
        search: nextSearch || undefined,
      };
      if (JSON.stringify(this.query.value) !== JSON.stringify(nextQuery)) {
        this.query.next(nextQuery);
      }
      const invalid =
        (rawFrom !== null && rawFrom !== nextFrom) ||
        (rawTo !== null && rawTo !== nextTo) ||
        (params.has('view') && !['population', 'workload'].includes(params.get('view') ?? '')) ||
        (rawPopulationDate !== null && rawPopulationDate !== nextPopulationDate) ||
        (params.has('sort') && params.get('sort') !== nextSort) ||
        (params.has('class') && params.get('class') !== nextClass);
      if (invalid) this.updateUrl(true);
    });
  }

  protected selectArea(area: AnalyticsArea): void {
    this.activeArea = area;
    this.updateUrl();
  }

  protected applyPopulationDate(): void {
    if (!this.validDate(this.populationDate)) return;
    if (this.populationQuery.value === this.populationDate) {
      this.populationQuery.next(this.populationDate);
    }
    this.updateUrl();
  }

  protected applyRange(): void {
    if (!this.validDate(this.dateFrom) || !this.validDate(this.dateTo)) return;
    if (this.dateFrom > this.dateTo) return;
    this.updateUrl();
  }

  protected chooseRange(range: QuickRange): void {
    this.dateFrom = range.from;
    this.dateTo = range.to;
    this.updateUrl();
  }

  protected applyDogFilters(): void {
    this.updateUrl();
  }

  protected clearDogFilters(): void {
    this.search = '';
    this.dogClass = '';
    this.sort = 'highest_km';
    this.updateUrl();
  }

  protected retry(): void {
    this.workloadRefresh.next(this.workloadRefresh.value + 1);
  }

  protected retryPopulation(): void {
    this.populationQuery.next(this.populationDate);
  }

  protected isQuickRange(range: QuickRange): boolean {
    return range.from === this.dateFrom && range.to === this.dateTo;
  }

  protected selectTrend(metric: TrendMetric): void {
    this.trendMetric = metric;
  }

  protected trendValue(week: WeeklyAnalytics): number {
    return week[this.trendMetric];
  }

  protected trendMaximum(overview: AnalyticsOverview): number {
    return Math.max(...overview.weekly.map((week) => this.trendValue(week)), 1);
  }

  protected trendHeight(week: WeeklyAnalytics, overview: AnalyticsOverview): number {
    const value = this.trendValue(week);
    return value ? Math.max((value / this.trendMaximum(overview)) * 100, 4) : 0;
  }

  protected trendLabel(): string {
    if (this.trendMetric === 'dog_starts') return 'Dog starts';
    if (this.trendMetric === 'dogs_worked') return 'Dogs worked';
    return 'Dog-km';
  }

  protected workloadBar(dog: AnalyticsDog, dogs: AnalyticsDog[]): number {
    const maximum = Math.max(...dogs.map((item) => item.dog_km), 1);
    return (dog.dog_km / maximum) * 100;
  }

  protected statusLabel(status: AnalyticsDog['workload_status']): string {
    if (status === 'not_applicable') return 'Not compared';
    if (status === 'higher') return 'Higher workload';
    return status[0].toUpperCase() + status.slice(1);
  }

  protected distributionWidth(item: PopulationBucket, items: PopulationBucket[]): number {
    const maximum = Math.max(...items.map((value) => value.count), 1);
    return (item.count / maximum) * 100;
  }

  protected cohortHeight(item: PopulationCohort, items: PopulationCohort[]): number {
    const maximum = Math.max(...items.map((value) => value.total), 1);
    return Math.max((item.total / maximum) * 100, 4);
  }

  private updateUrl(replaceUrl = false): void {
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: {
        view: this.activeArea === 'population' ? 'population' : null,
        date: this.activeArea === 'population' ? this.populationDate : null,
        from: this.dateFrom,
        to: this.dateTo,
        search: this.search || null,
        class: this.dogClass || null,
        sort: this.sort === 'highest_km' ? null : this.sort,
      },
      replaceUrl,
    });
  }

  private validDate(value: string | null): value is string {
    if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
    const [year, month, day] = value.split('-').map(Number);
    const parsed = new Date(Date.UTC(year, month - 1, day));
    return (
      parsed.getUTCFullYear() === year &&
      parsed.getUTCMonth() === month - 1 &&
      parsed.getUTCDate() === day &&
      value >= SEASON_START &&
      value <= SEASON_END
    );
  }
}
