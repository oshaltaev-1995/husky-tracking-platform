import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';

import { KennelMapSnapshot } from './kennel-map.models';

@Injectable({ providedIn: 'root' })
export class KennelMapService {
  private readonly http = inject(HttpClient);

  getSnapshot(date: string) {
    return this.http.get<KennelMapSnapshot>('/api/v1/kennel-map', {
      params: new HttpParams().set('date', date),
    });
  }
}
