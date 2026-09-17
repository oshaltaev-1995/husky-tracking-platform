import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';

import {
  GeneratedTeams,
  SaveTeamsRequest,
  TeamBuilderContext,
} from './team-builder.models';

@Injectable({ providedIn: 'root' })
export class TeamBuilderService {
  private readonly http = inject(HttpClient);

  private base(date: string, activityId: string): string {
    return `/api/v1/daily-plans/${date}/activities/${activityId}`;
  }

  getContext(date: string, activityId: string) {
    return this.http.get<TeamBuilderContext>(`${this.base(date, activityId)}/team-builder`);
  }

  generate(date: string, activityId: string, teamCount: number, teamSize: number) {
    return this.http.post<GeneratedTeams>(`${this.base(date, activityId)}/teams/generate`, {
      team_count: teamCount,
      team_size: teamSize,
    });
  }

  save(date: string, activityId: string, payload: SaveTeamsRequest) {
    return this.http.put<TeamBuilderContext>(`${this.base(date, activityId)}/teams`, payload);
  }
}
