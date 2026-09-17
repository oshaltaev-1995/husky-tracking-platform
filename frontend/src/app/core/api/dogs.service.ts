import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, forkJoin } from 'rxjs';

import {
  ArchiveRegistryResponse,
  DogHistory,
  DogPedigree,
  DogProfile,
  DogProfileBundle,
  DogsRegistryResponse,
  DogWork,
} from './dogs.models';

export interface DogsQuery {
  search?: string;
  dogClass?: string;
  sex?: string;
  availability?: string;
  neutered?: string;
  housing?: string;
  capability?: string;
  sort?: string;
}

export interface ArchiveQuery {
  search?: string;
  reason?: string;
  sort?: string;
}

@Injectable({ providedIn: 'root' })
export class DogsService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = '/api/v1';

  getDogs(query: DogsQuery = {}) {
    return this.http.get<DogsRegistryResponse>(`${this.baseUrl}/dogs`, {
      params: this.params({
        search: query.search,
        dog_class: query.dogClass,
        sex: query.sex,
        availability: query.availability,
        neutered: query.neutered,
        housing: query.housing,
        capability: query.capability,
        sort: query.sort,
      }),
    });
  }

  getArchive(query: ArchiveQuery = {}) {
    return this.http.get<ArchiveRegistryResponse>(`${this.baseUrl}/archive`, {
      params: this.params({
        search: query.search,
        reason: query.reason,
        sort: query.sort,
      }),
    });
  }

  getProfile(id: string) {
    return this.http.get<DogProfile>(`${this.baseUrl}/dogs/${id}`);
  }

  getPedigree(id: string) {
    return this.http.get<DogPedigree>(`${this.baseUrl}/dogs/${id}/pedigree`);
  }

  getWork(id: string) {
    return this.http.get<DogWork>(`${this.baseUrl}/dogs/${id}/work`);
  }

  getHistory(id: string) {
    return this.http.get<DogHistory>(`${this.baseUrl}/dogs/${id}/history`);
  }

  getProfileBundle(id: string): Observable<DogProfileBundle> {
    return forkJoin({
      profile: this.getProfile(id),
      pedigree: this.getPedigree(id),
      work: this.getWork(id),
      history: this.getHistory(id),
    });
  }

  private params(values: Record<string, string | undefined>) {
    let params = new HttpParams();
    for (const [key, value] of Object.entries(values)) {
      if (value !== undefined && value !== '') {
        params = params.set(key, value);
      }
    }
    return params;
  }
}
