import { AsyncPipe, DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import {
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  afterNextRender,
  AfterRenderRef,
  DestroyRef,
  ElementRef,
  Injector,
  inject,
  viewChild,
  computed,
  signal,
  HostListener,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, NavigationStart, Router, RouterLink } from '@angular/router';
import {
  BehaviorSubject,
  EMPTY,
  catchError,
  map,
  of,
  shareReplay,
  startWith,
  switchMap,
  tap,
  timeout,
} from 'rxjs';

import {
  KennelMapLayer,
  KennelMapLocation,
  KennelMapResident,
  KennelMapSnapshot,
} from '../../core/api/kennel-map.models';
import { KennelMapService } from '../../core/api/kennel-map.service';
import { DemoSessionService } from '../../core/api/demo-session.service';
import { GroundMapComponent } from './ground-map.component';
import { KennelLocationCardComponent } from './kennel-location-card.component';
import { kennelMapLayout } from './kennel-map-layout';
import { MapLegendComponent } from './map-legend.component';
import { HousingMoveDraft, affectedHousing, pendingMoves, previewHousing, stageMove } from './housing-move-draft';
import { HousingNavigationGuardState } from './housing-navigation.guard';
import { HousingDiscardDialogComponent } from './housing-discard-dialog.component';
import { HousingMoveReviewComponent } from './housing-move-review.component';
import { KennelMapPrintService } from './kennel-map-print.service';
import { projectKennelPrint } from './kennel-print-projection';

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
    RouterLink,
    HousingDiscardDialogComponent,
    HousingMoveReviewComponent,
  ],
  templateUrl: './kennel-map-page.component.html',
  styleUrl: './kennel-map-page.component.scss',
  host: { '[class.ground-view]': "activeView === 'ground'" },
  providers: [KennelMapPrintService],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KennelMapPageComponent {
  private readonly mapService = inject(KennelMapService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly changeDetector = inject(ChangeDetectorRef);
  private readonly injector = inject(Injector);
  private readonly destroyRef = inject(DestroyRef);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly ground = viewChild(GroundMapComponent);
  private readonly requestedDate = new BehaviorSubject(DEFAULT_DATE);
  private readonly printService = inject(KennelMapPrintService);
  private readonly snapshotLoading = signal(true);
  private readonly session = inject(DemoSessionService);
  private readonly navigation = inject(HousingNavigationGuardState);
  private contextEpoch = 0;
  private sessionInitializationEpoch: number | null = null;
  private undoStack: HousingMoveDraft[] = [];
  private discardResolver: ((discard: boolean) => void) | null = null;
  private destroyed = false;
  protected readonly committed = signal<KennelMapSnapshot | null>(null);
  protected readonly draft = signal<HousingMoveDraft>(new Map());
  protected readonly preview = computed(() => {
    const snapshot = this.committed();
    return snapshot ? previewHousing(snapshot, this.draft()) : null;
  });
  protected readonly layout = computed(() => { const data = this.preview(); return data ? kennelMapLayout(data) : null; });
  protected readonly changes = computed(() => { const data = this.committed(); return data ? pendingMoves(data, this.draft()) : []; });
  protected readonly affectedLocations = computed(() => { const data = this.preview(); return data ? affectedHousing(data, this.changes()) : []; });
  protected readonly pendingDogIds = computed(() => new Set(this.changes().map((move) => move.dog_id)));
  protected readonly affectedLocationCodes = computed(() => new Set(this.affectedLocations().map((location) => location.code)));
  protected readonly moveMode = signal(false);
  protected readonly hasUndo = signal(false);
  protected readonly selectedDogId = signal<string | null>(null);
  protected destinationCode = '';
  protected readonly reviewOpen = signal(false);
  protected readonly discardOpen = signal(false);
  protected readonly phase = signal<'idle' | 'saving' | 'conflict' | 'session' | 'unknown' | 'reloading' | 'resetting'>('idle');
  protected readonly feedback = signal('');
  protected readonly errorMessage = signal('');
  protected readonly printUnavailableReason = computed(() => {
    if (this.snapshotLoading() || !this.committed() || this.committed()?.selected_date !== this.selectedDate) {
      return 'Wait for the selected housing snapshot to load before printing.';
    }
    if (this.phase() !== 'idle') return 'Resolve the current housing operation or reload housing before printing.';
    if (this.draft().size) return 'Save or discard the pending housing moves before printing.';
    if (this.reviewOpen() || this.discardOpen() || this.printService.isOpen()) return 'Close the current dialog before opening print preview.';
    return null;
  });
  protected readonly canEdit = computed(() => {
    const snapshot = this.committed();
    const edit = snapshot?.housing_edit;
    return !!snapshot && snapshot.selected_date === this.selectedDate && edit?.editable === true && !!edit.precondition && typeof edit.revision === 'number' &&
      edit.effective_date === snapshot.selected_date;
  });
  protected readonly interactionsDisabled = computed(() => this.phase() !== 'idle' || this.reviewOpen() || this.discardOpen());
  protected readonly sortedResidents = computed(() => this.preview()?.locations.flatMap((location) => location.residents)
    .sort((a, b) => a.name.localeCompare(b.name) || a.id.localeCompare(b.id)) ?? []);
  private pendingReveal: AfterRenderRef | null = null;

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
    switchMap((date) => {
      const epoch = this.contextEpoch;
      this.snapshotLoading.set(true);
      return this.mapService.getSnapshot(date).pipe(
        tap((data) => {
          if (this.isCurrent(epoch) && date === this.selectedDate) {
            this.acceptSnapshot(data);
          }
        }),
        map((data) => ({ kind: 'ready' as const, data, layout: kennelMapLayout(data) })),
        startWith({ kind: 'loading' as const }),
        catchError(() => {
          if (this.isCurrent(epoch)) { this.committed.set(null); this.snapshotLoading.set(false); }
          this.invalidateSearch();
          return of({ kind: 'error' as const });
        }),
      );
    }),
    shareReplay({ bufferSize: 1, refCount: true }),
  );

  constructor() {
    const registration = { date: () => this.selectedDate, leave: () => this.canLeave() };
    this.navigation.current = registration;
    this.destroyRef.onDestroy(() => {
      this.printService.close(false);
      this.destroyed = true;
      this.contextEpoch++;
      this.cancelReveal();
      this.discardResolver?.(false);
      if (this.navigation.current === registration) this.navigation.current = null;
    });
    this.session.resetReviewOpened$.pipe(takeUntilDestroyed()).subscribe(() => {
      this.printService.close(false);
      this.reviewOpen.set(false);
      this.resolveDiscard(false);
    });
    this.session.resetStarted$.pipe(takeUntilDestroyed()).subscribe(() => {
      this.invalidateEditing();
      this.phase.set('resetting');
      this.errorMessage.set('');
      this.feedback.set('Resetting your demo. Pending housing previews have been discarded.');
    });
    this.session.resetCompleted$.pipe(takeUntilDestroyed()).subscribe(() => this.reloadHousing());
    this.session.resetFailed$.pipe(takeUntilDestroyed()).subscribe(() => {
      this.phase.set('unknown');
      this.feedback.set('');
      this.errorMessage.set('Reset could not be confirmed. Reload housing before editing.');
    });
    this.session.replaced$.pipe(takeUntilDestroyed()).subscribe(() => {
      // Only our own session-initialization response may replace its expired cookie here.
      if (this.sessionInitializationEpoch === this.contextEpoch) return;
      this.invalidateEditing();
      this.phase.set('session');
      this.errorMessage.set('Your demo session changed. Restore the demo session and reload housing before editing.');
    });
    this.router.events.pipe(takeUntilDestroyed()).subscribe((event) => {
      if (event instanceof NavigationStart) this.cancelReveal();
    });
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
        this.invalidateEditing();
        this.committed.set(null);
        this.moveMode.set(false);
        this.phase.set('idle');
        this.errorMessage.set('');
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
    const date = this.validDate(input.value) ? input.value : DEFAULT_DATE;
    input.value = this.selectedDate;
    void this.router.navigate([], { relativeTo: this.route, queryParams: { date }, queryParamsHandling: 'merge' }).then(() => {
      input.value = this.selectedDate;
    });
  }

  protected openPrint(): void {
    const snapshot = this.committed();
    if (!snapshot || this.printUnavailableReason()) return;
    this.cancelReveal();
    this.printService.open(projectKennelPrint(snapshot, this.activeLayer));
  }

  /** Both router leave and same-component date guards use this one application dialog. */
  public canLeave(): boolean | Promise<boolean> {
    if (!this.draft().size && this.phase() !== 'saving') return true;
    this.reviewOpen.set(false);
    if (this.discardResolver) return false;
    this.discardOpen.set(true);
    return new Promise<boolean>((resolve) => { this.discardResolver = resolve; });
  }

  protected resolveDiscard(discard: boolean): void {
    this.discardOpen.set(false);
    const resolve = this.discardResolver;
    this.discardResolver = null;
    if (discard) this.invalidateEditing();
    resolve?.(discard);
  }

  @HostListener('window:beforeunload', ['$event'])
  protected beforeUnload(event: BeforeUnloadEvent): void {
    if (this.draft().size || this.phase() === 'saving') { event.preventDefault(); event.returnValue = ''; }
  }

  protected enterMove(): void {
    if (this.canEdit() && this.phase() === 'idle') { this.moveMode.set(true); this.feedback.set('Select a dog, then a destination. Changes stay in a local preview until you confirm.'); }
  }

  protected async doneMoving(): Promise<void> {
    if (await this.canLeave()) {
      this.moveMode.set(false);
      this.selectedDogId.set(null);
      if (this.phase() === 'saving') {
        this.phase.set('unknown');
        this.errorMessage.set('The save may still complete. Reload housing before editing again.');
      }
      if (this.phase() === 'unknown' || this.phase() === 'session' || this.phase() === 'conflict') {
        // Done moving replaces the dialog's original trigger; recovery is now the available target.
        this.focusControl('[data-housing-recovery]');
      }
    }
  }

  protected selectDog(id: string): void {
    if (!this.interactionsDisabled() && this.moveMode()) { this.selectedDogId.set(id); this.destinationCode = ''; }
  }

  protected stageSelected(): void {
    const id = this.selectedDogId();
    if (id) this.stage({ dogId: id, destinationCode: this.destinationCode });
  }

  protected stage(move: { dogId: string; destinationCode: string }): void {
    const snapshot = this.committed();
    if (!snapshot || !this.canEdit() || !this.moveMode() || this.interactionsDisabled()) return;
    const current = this.draft();
    const next = stageMove(snapshot, current, move.dogId, move.destinationCode);
    if (current === next) return;
    this.undoStack.push(current);
    this.hasUndo.set(true);
    this.draft.set(next);
    this.selectedDogId.set(move.dogId);
    this.destinationCode = '';
    this.feedback.set('Preview updated. Housing has not been saved.');
    this.errorMessage.set('');
    this.cancelReveal();
  }

  protected undo(): void {
    if (this.interactionsDisabled()) return;
    const previous = this.undoStack.pop();
    this.hasUndo.set(this.undoStack.length > 0);
    if (previous) { this.draft.set(previous); this.feedback.set('Last preview step undone.'); this.cancelReveal(); }
  }

  protected discardDraft(): void {
    if (this.interactionsDisabled()) return;
    this.clearDraft();
    this.errorMessage.set('');
    this.feedback.set('Preview discarded.');
  }

  protected openReview(): void {
    if (this.changes().length && this.canEdit() && !this.interactionsDisabled()) this.reviewOpen.set(true);
  }

  protected confirmMoves(): void {
    const snapshot = this.committed();
    if (!snapshot || !this.reviewOpen() || this.phase() !== 'idle' || !this.canEdit() || !this.changes().length) return;
    const payload = { effective_date: snapshot.selected_date, precondition: snapshot.housing_edit.precondition!,
      moves: this.changes().map((move) => ({ dog_id: move.dog_id, destination_code: move.destination_code })) };
    const epoch = this.contextEpoch;
    this.phase.set('saving');
    this.feedback.set('Saving housing moves…');
    this.errorMessage.set('');
    this.mapService.moveDogs(payload).pipe(timeout(20000), takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (data) => {
        if (!this.isCurrent(epoch)) return;
        this.acceptSnapshot(data);
        this.clearDraft();
        this.reviewOpen.set(false);
        this.phase.set('idle');
        this.feedback.set('Housing moves saved in your demo workspace.');
        this.focusControl('select[name="move-dog"]');
      },
      error: (error: unknown) => {
        if (!this.isCurrent(epoch)) return;
        this.reviewOpen.set(false);
        this.feedback.set('');
        const status = error instanceof HttpErrorResponse ? error.status : 0;
        if (status === 401) {
          this.phase.set('session');
          this.errorMessage.set('Your demo session is no longer valid. Restore the demo session, then review a new housing draft. Nothing will be replayed.');
        } else if (status === 409) {
          this.phase.set('conflict');
          this.errorMessage.set('Housing changed since this preview. Reload housing to discard the stale draft, then review your moves again.');
        } else if (status === 422 || status === 403) {
          this.phase.set('idle');
          const detail = error instanceof HttpErrorResponse ? error.error?.detail : null;
          const message = typeof detail?.message === 'string' ? detail.message.slice(0, 240) : '';
          this.errorMessage.set(status === 403 ? 'This request was not allowed. Use the same-origin demo and try again.' : message || 'These moves could not be validated. Check the dogs and destinations, then review again.');
        } else {
          this.phase.set('unknown');
          this.errorMessage.set('The save result could not be confirmed. It may have reached the server. Reload housing to check the saved placement before making a new draft.');
        }
        if (this.phase() !== 'idle') this.focusControl('[data-housing-recovery]');
      },
    });
  }

  protected restoreSession(): void {
    if (this.phase() !== 'session' && !(this.phase() === 'idle' && this.committed()?.housing_edit.reason === 'workspace_required')) return;
    this.invalidateEditing();
    this.phase.set('reloading');
    this.errorMessage.set('');
    const epoch = this.contextEpoch;
    this.sessionInitializationEpoch = epoch;
    this.session.reinitialize().pipe(switchMap(() => {
      if (this.sessionInitializationEpoch === epoch) this.sessionInitializationEpoch = null;
      if (!this.isCurrent(epoch)) return EMPTY;
      return this.mapService.getSnapshot(this.selectedDate);
    }), timeout(20000), takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (data) => { if (this.isCurrent(epoch)) { this.acceptSnapshot(data); this.phase.set('idle'); this.errorMessage.set(''); this.feedback.set('Demo session restored. Select dogs and review a new draft.'); } },
      error: () => { if (this.isCurrent(epoch)) { this.sessionInitializationEpoch = null; this.phase.set('session'); this.errorMessage.set('The demo session could not be restored. Try again.'); } },
    });
  }

  protected reloadHousing(): void {
    this.invalidateEditing();
    this.phase.set('reloading');
    this.errorMessage.set('');
    const epoch = this.contextEpoch;
    this.mapService.getSnapshot(this.selectedDate).pipe(timeout(20000), takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (data) => { if (this.isCurrent(epoch)) { this.acceptSnapshot(data); this.phase.set('idle'); this.errorMessage.set(''); this.feedback.set('Saved housing reloaded. Select dogs to start a new preview.'); } },
      error: () => { if (this.isCurrent(epoch)) { this.phase.set('unknown'); this.errorMessage.set('Housing could not be reloaded. Retry loading before editing.'); } },
    });
  }

  private isCurrent(epoch: number): boolean { return !this.destroyed && epoch === this.contextEpoch; }
  private acceptSnapshot(data: KennelMapSnapshot): void {
    this.committed.set(data);
    this.snapshotLoading.set(false);
  }
  private focusControl(selector: string): void {
    this.cancelReveal();
    const epoch = this.contextEpoch;
    this.pendingReveal = afterNextRender(() => {
      this.pendingReveal = null;
      // An asynchronous result never owns focus while a user decision is open.
      if (this.isCurrent(epoch) && !this.discardOpen() && !this.reviewOpen()) {
        this.host.nativeElement.querySelector<HTMLElement>(selector)?.focus();
      }
    }, { injector: this.injector });
  }
  protected destinationLocation(): KennelMapLocation | undefined { return this.preview()?.locations.find((location) => location.code === this.destinationCode); }
  protected committedOccupancy(code: string): number { return this.committed()?.locations.find((location) => location.code === code)?.residents.length ?? 0; }
  protected projectedOccupancy(location: KennelMapLocation): number { return location.residents.length + (location.residents.some((dog) => dog.id === this.selectedDogId()) ? 0 : 1); }
  private clearDraft(): void { this.draft.set(new Map()); this.undoStack = []; this.hasUndo.set(false); this.selectedDogId.set(null); this.destinationCode = ''; this.cancelReveal(); }
  private invalidateEditing(): void {
    this.printService.close(false);
    this.contextEpoch++;
    this.sessionInitializationEpoch = null;
    this.reviewOpen.set(false);
    this.feedback.set('');
    this.clearDraft();
  }

  protected selectLayer(layer: KennelMapLayer): void {
    this.updateUrl({ layer });
  }

  protected selectView(view: MapView): void {
    if (view !== this.activeView) {
      this.cancelReveal();
      this.updateUrl({ view });
    }
  }

  protected retry(): void {
    this.invalidateSearch();
    this.requestedDate.next(this.selectedDate);
  }

  protected invalidateSearch(): void {
    this.cancelReveal();
    this.highlightedDogId = null;
    this.searchNotFound = false;
  }

  protected residents(snapshot: KennelMapSnapshot): KennelMapResident[] {
    return snapshot.locations.flatMap((location) => location.residents);
  }

  protected findDog(snapshot: KennelMapSnapshot): void {
    this.cancelReveal();
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
      const date = this.selectedDate;
      const view = this.activeView;
      this.pendingReveal = afterNextRender(() => {
        this.pendingReveal = null;
        if (this.highlightedDogId !== dog.id || this.selectedDate !== date || this.activeView !== view) return;
        if (view === 'ground') {
          this.ground()?.revealDog(dog.id);
        } else {
          const element = this.host.nativeElement;
          const link = element.ownerDocument.getElementById(`map-dog-${dog.id}`);
          if (link && element.contains(link)) {
            link.scrollIntoView?.({ block: 'center', inline: 'nearest', behavior: 'instant' });
            link.focus({ preventScroll: true });
          }
        }
      }, { injector: this.injector });
    }
  }

  private cancelReveal(): void {
    this.pendingReveal?.destroy();
    this.pendingReveal = null;
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
