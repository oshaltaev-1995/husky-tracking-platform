import { AsyncPipe, DatePipe, TitleCasePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { catchError, distinctUntilChanged, map, of, startWith, switchMap } from 'rxjs';

import { DogsService } from '../../../core/api/dogs.service';
import { DogMediaComponent } from '../../../shared/dog-media/dog-media.component';
import { HistoryComponent } from './history.component';
import { PedigreeComponent } from './pedigree.component';
import { ProfileInfoComponent } from './profile-info.component';
import { WorkComponent } from './work.component';
import { workingRoleList } from '../../../shared/working-role-label';

type ProfileTab = 'profile' | 'pedigree' | 'work' | 'history';

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
  templateUrl: './dog-profile.component.html',
  styleUrl: './dog-profile.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DogProfileComponent {
  private readonly route = inject(ActivatedRoute);
  private readonly dogs = inject(DogsService);
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
    switchMap((id) =>
      this.dogs.getProfileBundle(id).pipe(
        map((data) => ({ kind: 'ready' as const, data })),
        startWith({ kind: 'loading' as const }),
        catchError((error: HttpErrorResponse) =>
          of({ kind: error.status === 404 || error.status === 422 ? ('not-found' as const) : ('error' as const) }),
        ),
      ),
    ),
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
