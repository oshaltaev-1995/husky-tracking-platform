import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';

export interface ContactPayload {
  name: string;
  email: string;
  company: string;
  subject: string;
  message: string;
  website: string;
}

export interface ContactResponse {
  accepted: boolean;
  message: string;
}

@Injectable({ providedIn: 'root' })
export class ContactService {
  private readonly http = inject(HttpClient);

  submit(payload: ContactPayload) {
    return this.http.post<ContactResponse>('/api/v1/contact', payload);
  }
}
