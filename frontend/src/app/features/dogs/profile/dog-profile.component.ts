import { AsyncPipe, DatePipe, DOCUMENT, TitleCasePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, effect, inject, viewChild } from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { catchError, distinctUntilChanged, map, merge, of, startWith, Subject, switchMap, tap } from 'rxjs';

import { DemoSessionService } from '../../../core/api/demo-session.service';
import { DogSummaryPrintService } from './dog-summary-print.service';
import { DogSummaryProjection, projectDogSummary } from './dog-summary-projection';
import { DogsService } from '../../../core/api/dogs.service';
import { DogMediaComponent } from '../../../shared/dog-media/dog-media.component';
import { HistoryComponent } from './history.component';
import { PedigreeComponent } from './pedigree.component';
import { ProfileInfoComponent } from './profile-info.component';
import { WorkComponent } from './work.component';
import { workingRoleList } from '../../../shared/working-role-label';

type ProfileTab = 'profile' | 'pedigree' | 'work' | 'history';

/** Accept the existing UUID route spellings without accepting misplaced separators. */
function canonicalUuid(value: string): string | null {
  if (!/^(?:[0-9a-f]{32}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/i.test(value)) return null;
  const hex = value.replace(/-/g, '').toLowerCase();
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

@Component({
  selector: 'ht-dog-profile',
  imports: [
    AsyncPipe,
    DatePipe,
    DogMediaComponent,
    HistoryComponent,
    PedigreeComponent,
    ProfileInfoComponent,
    RouterLink,
    TitleCasePipe,
    WorkComponent,
  ],
  providers: [DogSummaryPrintService],
  templateUrl: './dog-profile.component.html',
  styleUrl: './dog-profile.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DogProfileComponent {
  private readonly route = inject(ActivatedRoute);
  private readonly dogs = inject(DogsService);
  private readonly session = inject(DemoSessionService);
  private readonly document = inject(DOCUMENT);
  protected readonly summaryPrint = inject(DogSummaryPrintService);
  private readonly context = new Subject<'reload' | 'invalidate'>();
  private readonly media = viewChild(DogMediaComponent);

  constructor() {
    this.session.resetReviewOpened$.pipe(takeUntilDestroyed()).subscribe(() => this.closeOverlays());
    this.session.resetStarted$.pipe(takeUntilDestroyed()).subscribe(() => this.invalidateContext());
    this.session.resetCompleted$.pipe(takeUntilDestroyed()).subscribe(() => this.context.next('reload'));
    this.session.replaced$.pipe(takeUntilDestroyed()).subscribe(() => this.invalidateContext());
    effect((onCleanup) => {
      const expiresAt = this.session.session()?.expires_at;
      if (!expiresAt) return;
      // Wall-clock time is used only for cookie expiry, never for domain values.
      const remaining = new Date(expiresAt).getTime() - Date.now();
      if (!Number.isFinite(remaining)) return;
      if (remaining <= 0) { this.invalidateContext(); return; }
      const timeout = setTimeout(() => this.invalidateContext(), remaining);
      onCleanup(() => clearTimeout(timeout));
    });
  }

  private invalidateContext(): void {
    this.closeOverlays();
    this.context.next('invalidate');
  }

  private closeOverlays(): void {
    this.media()?.closeViewer(false);
    this.summaryPrint.close(false);
  }

  protected reloadProfile(): void {
    const session = this.session.session();
    if (session && new Date(session.expires_at).getTime() <= Date.now()) {
      // Explicit recovery returns through the existing route session guard; print
      // itself never creates/replaces a workspace or replays a mutable request.
      this.document.defaultView?.location.reload();
      return;
    }
    this.context.next('reload');
  }

  protected printSummary(projection: DogSummaryProjection): void {
    const session = this.session.session();
    if (session && new Date(session.expires_at).getTime() <= Date.now()) {
      this.invalidateContext();
      return;
    }
    this.summaryPrint.open(projection);
  }

  protected readonly tabs: ProfileTab[] = ['profile', 'pedigree', 'work', 'history'];
  protected readonly profileOrigin = toSignal(
    this.route.queryParamMap.pipe(
      map((params) => params.get('from') === 'archive' ? 'archive' as const : 'dogs' as const),
      distinctUntilChanged(),
    ),
    { initialValue: 'dogs' as const },
  );

  protected readonly activeTab$ = this.route.queryParamMap.pipe(
    map((params) => params.get('tab')),
    map((tab): ProfileTab => this.tabs.includes(tab as ProfileTab) ? (tab as ProfileTab) : 'profile'),
    distinctUntilChanged(),
  );

  protected readonly state$ = this.route.paramMap.pipe(
    map((params) => params.get('dogId') ?? ''),
    distinctUntilChanged(),
    tap(() => this.closeOverlays()),
    switchMap((id) => merge(of('reload' as const), this.context).pipe(
      switchMap((action) => {
        this.closeOverlays();
        if (action === 'invalidate') return of({ kind: 'context-changed' as const });
        const routeId = canonicalUuid(id);
        if (!routeId) return of({ kind: 'not-found' as const });
        return this.dogs.getProfileBundle(id).pipe(
          map((data) => {
            const summary = projectDogSummary(data);
            if (canonicalUuid(data.profile.id) !== routeId || !summary) throw new Error('Inconsistent profile sections');
            return { kind: 'ready' as const, data, summary };
          }),
          startWith({ kind: 'loading' as const }),
          catchError((error: HttpErrorResponse) =>
            of({ kind: error.status === 404 || error.status === 422 ? ('not-found' as const) : ('error' as const) }),
          ),
        );
      }),
    )),
  );

  protected tabLabel(tab: ProfileTab) {
    if (tab === 'profile') return 'Overview';
    return tab.slice(0, 1).toUpperCase() + tab.slice(1);
  }

  protected reasonLabel(reason: string) {
    return ({ euthanized: 'Euthanized', deceased: 'Died naturally', rehomed_to_guide: 'Rehomed to guide' } as Record<string, string>)[reason] ?? reason;
  }

  protected roleList = workingRoleList;

  protected tabQueryParams(tab: ProfileTab): Record<string, string | null> {
    return {
      tab: tab === 'profile' ? null : tab,
      from: this.profileOrigin() === 'archive' ? 'archive' : null,
    };
  }
}
