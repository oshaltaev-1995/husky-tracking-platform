import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';

import {
  ActualEligibility,
  ActualSessionUpdate,
  ActualSessionWrite,
  DailyEntry,
} from './daily-entry.models';

@Injectable({ providedIn: 'root' })
export class DailyEntryService {
  private readonly http = inject(HttpClient);

  getEntry(date: string) {
    return this.http.get<DailyEntry>(`/api/v1/daily-entry/${date}`);
  }

  getEligibility(date: string, distanceKm: 5 | 10, excludeSessionId?: string) {
    let params = new HttpParams().set('distance_km', distanceKm);
    if (excludeSessionId) params = params.set('exclude_session_id', excludeSessionId);
    return this.http.get<ActualEligibility>(`/api/v1/daily-entry/${date}/eligible-dogs`, {
      params,
    });
  }

  createSession(date: string, payload: ActualSessionWrite) {
    return this.http.post<DailyEntry>(`/api/v1/daily-entry/${date}/sessions`, payload);
  }

  updateSession(date: string, sessionId: string, payload: ActualSessionUpdate) {
    return this.http.patch<DailyEntry>(
      `/api/v1/daily-entry/${date}/sessions/${sessionId}`,
      payload,
    );
  }

  deleteSession(date: string, sessionId: string, revision: number) {
    return this.http.delete<DailyEntry>(`/api/v1/daily-entry/${date}/sessions/${sessionId}`, {
      params: new HttpParams().set('expected_revision', revision),
    });
  }

  confirmPlan(date: string, activityId: string) {
    return this.http.post<DailyEntry>(
      `/api/v1/daily-entry/${date}/planned-activities/${activityId}/confirm`,
      {},
    );
  }

  markNotRun(date: string, activityId: string) {
    return this.http.post<DailyEntry>(
      `/api/v1/daily-entry/${date}/planned-activities/${activityId}/not-run`,
      {},
    );
  }

  clearNotRun(date: string, activityId: string) {
    return this.http.delete<DailyEntry>(
      `/api/v1/daily-entry/${date}/planned-activities/${activityId}/not-run`,
    );
  }
}
