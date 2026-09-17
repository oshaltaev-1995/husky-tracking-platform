import { AsyncPipe, DatePipe, KeyValuePipe, TitleCasePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { BehaviorSubject, catchError, map, of, shareReplay, startWith, switchMap } from 'rxjs';

import { DashboardResponse } from '../../core/api/dashboard.models';
import { DashboardService } from '../../core/api/dashboard.service';
import { WeeklyAnalytics } from '../../core/api/analytics.models';

const DASHBOARD_DATE = '2026-03-31';

@Component({
  selector: 'ht-dashboard-page',
  imports: [AsyncPipe, DatePipe, KeyValuePipe, RouterLink, TitleCasePipe],
  templateUrl: './dashboard-page.component.html',
  styleUrl: './dashboard-page.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DashboardPageComponent {
  private readonly dashboard = inject(DashboardService);
  private readonly refresh = new BehaviorSubject(0);

  protected readonly selectedDate = DASHBOARD_DATE;
  protected readonly state$ = this.refresh.pipe(
    switchMap(() =>
      this.dashboard.getDashboard(DASHBOARD_DATE).pipe(
        map((data) => ({ kind: 'ready' as const, data })),
        startWith({ kind: 'loading' as const }),
        catchError(() => of({ kind: 'error' as const })),
      ),
    ),
    shareReplay({ bufferSize: 1, refCount: true }),
  );

  protected retry(): void {
    this.refresh.next(this.refresh.value + 1);
  }

  protected count(values: Record<string, number>, key: string): number {
    return values[key] ?? 0;
  }

  protected activityLabel(value: string): string {
    return value.replaceAll('_', ' ');
  }

  protected statusLabel(value: string): string {
    const labels: Record<string, string> = {
      matches_plan: 'Matches plan',
      modified: 'Modified actual',
      not_run: 'Not run',
      not_recorded: 'Not recorded',
      context_only: 'Context only',
    };
    return labels[value] ?? this.activityLabel(value);
  }

  protected trendMaximum(data: DashboardResponse): number {
    return Math.max(...data.recent_weekly.map((week) => week.dog_km), 1);
  }

  protected trendHeight(week: WeeklyAnalytics, data: DashboardResponse): number {
    return week.dog_km ? Math.max((week.dog_km / this.trendMaximum(data)) * 100, 6) : 0;
  }
}
