import { AsyncPipe, DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  ElementRef,
  inject,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
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
} from '../../core/api/kennel-map.models';
import { KennelMapService } from '../../core/api/kennel-map.service';
import { GroundMapComponent } from './ground-map.component';
import { KennelLocationCardComponent } from './kennel-location-card.component';
import { kennelMapLayout } from './kennel-map-layout';
import { MapLegendComponent } from './map-legend.component';

const DEFAULT_DATE = '2026-03-31';
const SEASON_START = '2025-12-01';
const SEASON_END = '2026-03-31';
const LAYERS: KennelMapLayer[] = ['default', 'gender', 'neutered', 'class', 'unavailable'];

type MapView = 'overview' | 'ground';

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
    GroundMapComponent,
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
  private readonly changeDetector = inject(ChangeDetectorRef);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly ground = viewChild(GroundMapComponent);
  private readonly requestedDate = new BehaviorSubject(DEFAULT_DATE);

  protected selectedDate = DEFAULT_DATE;
  protected activeLayer: KennelMapLayer = 'default';
  protected activeView: MapView = 'overview';
  protected searchTerm = '';
  protected highlightedDogId: string | null = null;
  protected searchNotFound = false;
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
        map((data) => ({ kind: 'ready' as const, data, layout: kennelMapLayout(data) })),
        startWith({ kind: 'loading' as const }),
        catchError(() => {
          this.invalidateSearch();
          return of({ kind: 'error' as const });
        }),
      ),
    ),
    shareReplay({ bufferSize: 1, refCount: true }),
  );

  constructor() {
    this.route.queryParamMap.pipe(takeUntilDestroyed()).subscribe((params) => {
      const rawDate = params.get('date');
      const rawLayer = params.get('layer');
      const rawView = params.get('view');
      const nextDate = this.validDate(rawDate) ? rawDate : DEFAULT_DATE;
      const nextLayer = LAYERS.includes(rawLayer as KennelMapLayer)
        ? (rawLayer as KennelMapLayer)
        : 'default';
      const nextView = rawView === 'ground' ? 'ground' : 'overview';
      const invalidDateOrLayer =
        (rawDate !== null && rawDate !== nextDate) || (rawLayer !== null && rawLayer !== nextLayer);
      const invalidView = rawView !== null && rawView !== nextView;

      this.activeLayer = nextLayer;
      this.activeView = nextView;
      this.selectedDate = nextDate;
      this.changeDetector.markForCheck();
      if (this.requestedDate.value !== nextDate) {
        this.invalidateSearch();
        this.requestedDate.next(nextDate);
      }
      if (invalidDateOrLayer || invalidView) {
        void this.router.navigate([], {
          relativeTo: this.route,
          queryParams: {
            ...(invalidDateOrLayer ? { date: nextDate, layer: nextLayer } : {}),
            ...(invalidView ? { view: null } : {}),
          },
          queryParamsHandling: 'merge',
          replaceUrl: true,
        });
      }
    });
  }

  protected changeDate(input: HTMLInputElement): void {
    this.invalidateSearch();
    const date = this.validDate(input.value) ? input.value : DEFAULT_DATE;
    if (input.value !== date) input.value = date;
    this.updateUrl({ date });
  }

  protected selectLayer(layer: KennelMapLayer): void {
    this.updateUrl({ layer });
  }

  protected selectView(view: MapView): void {
    if (view !== this.activeView) this.updateUrl({ view });
  }

  protected retry(): void {
    this.invalidateSearch();
    this.requestedDate.next(this.selectedDate);
  }

  protected invalidateSearch(): void {
    this.highlightedDogId = null;
    this.searchNotFound = false;
  }

  protected residents(snapshot: KennelMapSnapshot): KennelMapResident[] {
    return snapshot.locations.flatMap((location) => location.residents);
  }

  protected findDog(snapshot: KennelMapSnapshot): void {
    const query = this.searchTerm.trim().toLocaleLowerCase();
    if (!query) {
      this.invalidateSearch();
      return;
    }
    const residents = this.residents(snapshot);
    const dog =
      residents.find((resident) => resident.name.toLocaleLowerCase() === query) ??
      residents.find((resident) => resident.name.toLocaleLowerCase().startsWith(query)) ??
      residents.find((resident) => resident.name.toLocaleLowerCase().includes(query));
    this.highlightedDogId = dog?.id ?? null;
    this.searchNotFound = !dog;
    if (dog) {
      this.searchTerm = dog.name;
      const ground = this.ground();
      if (this.activeView === 'ground') {
        ground?.revealDog(dog.id);
      } else {
        const element = this.host.nativeElement;
        const link = element.ownerDocument.getElementById(`map-dog-${dog.id}`);
        if (link && element.contains(link)) {
          link.scrollIntoView?.({ block: 'center', inline: 'nearest' });
          link.focus({ preventScroll: true });
        }
      }
    }
  }

  protected clearSearch(): void {
    this.searchTerm = '';
    this.invalidateSearch();
  }

  protected highlightedDog(snapshot: KennelMapSnapshot): HighlightedDog | null {
    if (!this.highlightedDogId) return null;
    for (const location of snapshot.locations) {
      const dog = location.residents.find((resident) => resident.id === this.highlightedDogId);
      if (dog) return { dog, location };
    }
    return null;
  }

  private updateUrl(params: { date?: string; layer?: KennelMapLayer; view?: MapView }): void {
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: params,
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
