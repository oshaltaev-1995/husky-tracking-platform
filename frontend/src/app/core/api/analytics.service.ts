import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { forkJoin } from 'rxjs';

import {
  AnalyticsDogsResponse,
  AnalyticsOverview,
  AnalyticsQuery,
  PopulationAnalytics,
} from './analytics.models';

@Injectable({ providedIn: 'root' })
export class AnalyticsService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = '/api/v1/analytics';

  getAnalytics(query: AnalyticsQuery) {
    const shared = new HttpParams().set('from', query.from).set('to', query.to);
    let dogParams = shared;
    if (query.search) dogParams = dogParams.set('search', query.search);
    if (query.dogClass) dogParams = dogParams.set('dog_class', query.dogClass);
    if (query.sort) dogParams = dogParams.set('sort', query.sort);
    return forkJoin({
      overview: this.http.get<AnalyticsOverview>(`${this.baseUrl}/overview`, {
        params: shared,
      }),
      dogs: this.http.get<AnalyticsDogsResponse>(`${this.baseUrl}/dogs`, {
        params: dogParams,
      }),
    });
  }

  getPopulation(snapshotDate: string) {
    return this.http.get<PopulationAnalytics>(`${this.baseUrl}/population`, {
      params: new HttpParams().set('date', snapshotDate),
    });
  }
}
