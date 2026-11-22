import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';

import { OperationsCapabilities, OperationsReview } from './operations.models';

@Injectable({ providedIn: 'root' })
export class OperationsService {
  private readonly http = inject(HttpClient);

  getCapabilities() {
    return this.http.get<OperationsCapabilities>('/api/v1/operations/capabilities');
  }

  review(selectedDate: string) {
    return this.http.post<OperationsReview>('/api/v1/operations/review', {
      selected_date: selectedDate,
    });
  }
}
