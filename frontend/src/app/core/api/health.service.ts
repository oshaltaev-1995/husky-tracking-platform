import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { HealthStatus } from './health.model';

@Injectable({ providedIn: 'root' })
export class HealthService {
  private readonly http = inject(HttpClient);

  getStatus(): Observable<HealthStatus> {
    return this.http.get<HealthStatus>('/api/v1/health');
  }
}
