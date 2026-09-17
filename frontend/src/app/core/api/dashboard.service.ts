import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';

import { DashboardResponse } from './dashboard.models';

@Injectable({ providedIn: 'root' })
export class DashboardService {
  private readonly http = inject(HttpClient);

  getDashboard(selectedDate: string) {
    return this.http.get<DashboardResponse>('/api/v1/dashboard', {
      params: new HttpParams().set('date', selectedDate),
    });
  }
}
