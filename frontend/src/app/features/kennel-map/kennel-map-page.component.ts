import { AsyncPipe, DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import {
  BehaviorSubject,
  catchError,
  map,
  of,
  shareReplay,
  startWith,
  switchMap,
} from 'rxjs';

import {
  KennelMapLayer,
  KennelMapLocation,
  KennelMapResident,
  KennelMapSnapshot,
  KennelRowView,
} from '../../core/api/kennel-map.models';
import { KennelMapService } from '../../core/api/kennel-map.service';
import { KennelLocationCardComponent } from './kennel-location-card.component';
import { MapLegendComponent } from './map-legend.component';

const DEFAULT_DATE = '2026-03-31';
const SEASON_START = '2025-12-01';
const SEASON_END = '2026-03-31';
const LAYERS: KennelMapLayer[] = ['default', 'gender', 'neutered', 'class', 'unavailable'];

interface KennelBlockView {
  zone: string;
  label: string;
  rows: KennelRowView[];
}

interface HighlightedDog {
  dog: KennelMapResident;
  location: KennelMapLocation;
}

@Component({
  selector: 'ht-kennel-map-page',
  imports: [
    AsyncPipe,
    DatePipe,
    FormsModule,
    KennelLocationCardComponent,
    MapLegendComponent,
  ],
  templateUrl: './kennel-map-page.component.html',
  styleUrl: './kennel-map-page.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KennelMapPageComponent {
  private readonly mapService = inject(KennelMapService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly requestedDate = new BehaviorSubject(DEFAULT_DATE);

  protected selectedDate = DEFAULT_DATE;
  protected activeLayer: KennelMapLayer = 'default';
  protected searchTerm = '';
  protected highlightedDogId: string | null = null;
  protected readonly layers: { value: KennelMapLayer; label: string }[] = [
    { value: 'default', label: 'Default' },
    { value: 'gender', label: 'Gender' },
    { value: 'neutered', label: 'Neutered' },
    { value: 'class', label: 'Class' },
    { value: 'unavailable', label: 'Unavailable' },
  ];
  protected readonly state$ = this.requestedDate.pipe(
    switchMap((date) =>
      this.mapService.getSnapshot(date).pipe(
        map((data) => ({ kind: 'ready' as const, data })),
        startWith({ kind: 'loading' as const }),
        catchError(() => of({ kind: 'error' as const })),
      ),
    ),
    shareReplay({ bufferSize: 1, refCount: true }),
  );

  constructor() {
    this.route.queryParamMap.subscribe((params) => {
      const rawDate = params.get('date');
      const rawLayer = params.get('layer');
      const nextDate = this.validDate(rawDate) ? rawDate : DEFAULT_DATE;
      const nextLayer = LAYERS.includes(rawLayer as KennelMapLayer)
        ? (rawLayer as KennelMapLayer)
        : 'default';
      const shouldNormalize =
        (rawDate !== null && rawDate !== nextDate) ||
        (rawLayer !== null && rawLayer !== nextLayer);

      this.activeLayer = nextLayer;
      if (this.selectedDate !== nextDate || this.requestedDate.value !== nextDate) {
        this.selectedDate = nextDate;
        this.highlightedDogId = null;
        this.requestedDate.next(nextDate);
      }
      if (shouldNormalize) {
        void this.router.navigate([], {
          relativeTo: this.route,
          queryParams: { date: nextDate, layer: nextLayer },
          replaceUrl: true,
        });
      }
    });
  }

  protected changeDate(value: string): void {
    this.selectedDate = value;
    const date = this.validDate(value) ? value : DEFAULT_DATE;
    this.updateUrl(date, this.activeLayer);
  }

  protected selectLayer(layer: KennelMapLayer): void {
    this.activeLayer = layer;
    this.updateUrl(this.selectedDate, layer);
  }

  protected retry(): void {
    this.requestedDate.next(this.selectedDate);
  }

  protected blocks(snapshot: KennelMapSnapshot): KennelBlockView[] {
    return ['A', 'B'].map((zone) => ({
      zone,
      label: `Zone ${zone}`,
      rows: ['1', '2'].map((row) => ({
        code: `${zone}${row}`,
        label: `Row ${zone}${row}`,
        locations: snapshot.locations.filter(
          (location) =>
            location.location_type === 'adult_enclosure' &&
            location.zone === zone &&
            location.row === row,
        ),
      })),
    }));
  }

  protected puppyAreas(snapshot: KennelMapSnapshot): KennelMapLocation[] {
    return snapshot.locations.filter((location) => location.location_type === 'puppy_area');
  }

  protected residents(snapshot: KennelMapSnapshot): KennelMapResident[] {
    return snapshot.locations.flatMap((location) => location.residents);
  }

  protected findDog(snapshot: KennelMapSnapshot): void {
    const query = this.searchTerm.trim().toLocaleLowerCase();
    if (!query) {
      this.highlightedDogId = null;
      return;
    }
    const residents = this.residents(snapshot);
    const dog =
      residents.find((resident) => resident.name.toLocaleLowerCase() === query) ??
      residents.find((resident) => resident.name.toLocaleLowerCase().startsWith(query)) ??
      residents.find((resident) => resident.name.toLocaleLowerCase().includes(query));
    this.highlightedDogId = dog?.id ?? null;
    if (dog) {
      this.searchTerm = dog.name;
      window.setTimeout(() => {
        const link = document.getElementById(`map-dog-${dog.id}`);
        link?.scrollIntoView?.({ block: 'center', behavior: 'smooth' });
        link?.focus({ preventScroll: true });
      }, 0);
    }
  }

  protected clearSearch(): void {
    this.searchTerm = '';
    this.highlightedDogId = null;
  }

  protected highlightedDog(snapshot: KennelMapSnapshot): HighlightedDog | null {
    if (!this.highlightedDogId) return null;
    for (const location of snapshot.locations) {
      const dog = location.residents.find((resident) => resident.id === this.highlightedDogId);
      if (dog) return { dog, location };
    }
    return null;
  }

  private updateUrl(date: string, layer: KennelMapLayer): void {
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { date, layer },
      queryParamsHandling: 'merge',
    });
  }

  private validDate(value: string | null): value is string {
    if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
    const [year, month, day] = value.split('-').map(Number);
    const parsed = new Date(Date.UTC(year, month - 1, day));
    const isCalendarDate =
      parsed.getUTCFullYear() === year &&
      parsed.getUTCMonth() === month - 1 &&
      parsed.getUTCDate() === day;
    return isCalendarDate && value >= SEASON_START && value <= SEASON_END;
  }
}
