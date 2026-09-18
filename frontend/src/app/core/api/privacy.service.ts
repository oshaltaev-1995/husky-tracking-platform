import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';

export interface PrivacyMetadata {
  controller_name: string;
  contact_email: string;
  controller_country: string;
  hosting_region: string;
  effective_date: string;
  mail_provider_name: string | null;
  mail_provider_region: string | null;
  demo_workspace_ttl_hours: number;
}

@Injectable({ providedIn: 'root' })
export class PrivacyService {
  private readonly http = inject(HttpClient);

  getMetadata() {
    return this.http.get<PrivacyMetadata>('/api/v1/public/privacy');
  }
}
