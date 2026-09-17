import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';

import {
  ActivityWrite,
  DailyPlan,
  Eligibility,
  PlannedActivityType,
} from './daily-plans.models';

@Injectable({ providedIn: 'root' })
export class DailyPlansService {
  private readonly http = inject(HttpClient);

  getPlan(date: string) {
    return this.http.get<DailyPlan>(`/api/v1/daily-plans/${date}`);
  }

  updateNotes(date: string, notes: string | null, expectedRevision: number | null) {
    return this.http.put<DailyPlan>(`/api/v1/daily-plans/${date}`, {
      notes,
      expected_revision: expectedRevision,
    });
  }

  createActivity(date: string, payload: ActivityWrite) {
    return this.http.post<DailyPlan>(`/api/v1/daily-plans/${date}/activities`, payload);
  }

  updateActivity(date: string, activityId: string, payload: ActivityWrite) {
    return this.http.patch<DailyPlan>(
      `/api/v1/daily-plans/${date}/activities/${activityId}`,
      payload,
    );
  }

  moveActivity(date: string, activityId: string, direction: 'up' | 'down', revision: number) {
    return this.http.post<DailyPlan>(
      `/api/v1/daily-plans/${date}/activities/${activityId}/move`,
      { direction, expected_revision: revision },
    );
  }

  deleteActivity(date: string, activityId: string, revision: number) {
    return this.http.delete<DailyPlan>(`/api/v1/daily-plans/${date}/activities/${activityId}`, {
      params: new HttpParams().set('expected_revision', revision),
    });
  }

  getEligibility(
    date: string,
    activityType: PlannedActivityType,
    distanceKm: number | null,
    excludeActivityId?: string,
  ) {
    let params = new HttpParams().set('activity_type', activityType);
    if (distanceKm !== null) params = params.set('distance_km', distanceKm);
    if (excludeActivityId) params = params.set('exclude_activity_id', excludeActivityId);
    return this.http.get<Eligibility>(`/api/v1/daily-plans/${date}/eligible-dogs`, {
      params,
    });
  }
}
