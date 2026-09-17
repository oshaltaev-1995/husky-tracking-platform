import { AsyncPipe, DatePipe, TitleCasePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import {
  BehaviorSubject,
  catchError,
  map,
  of,
  shareReplay,
  startWith,
  switchMap,
} from 'rxjs';

import { ArchiveQuery, DogsService } from '../../core/api/dogs.service';
import { DogMediaComponent } from '../../shared/dog-media/dog-media.component';

@Component({
  selector: 'ht-archive-registry',
  imports: [AsyncPipe, DatePipe, DogMediaComponent, FormsModule, RouterLink, TitleCasePipe],
  templateUrl: './archive-registry.component.html',
  styleUrl: './archive-registry.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ArchiveRegistryComponent {
  private readonly dogsService = inject(DogsService);
  private readonly query = new BehaviorSubject<ArchiveQuery>({ sort: 'name' });

  protected filters: ArchiveQuery = { sort: 'name' };
  protected readonly state$ = this.query.pipe(
    switchMap((query) =>
      this.dogsService.getArchive(query).pipe(
        map((data) => ({ kind: 'ready' as const, data })),
        startWith({ kind: 'loading' as const }),
        catchError(() => of({ kind: 'error' as const })),
      ),
    ),
    shareReplay({ bufferSize: 1, refCount: true }),
  );

  protected applyFilters() {
    this.query.next({ ...this.filters });
  }

  protected resetFilters() {
    this.filters = { sort: 'name' };
    this.applyFilters();
  }

  protected reasonLabel(reason: string) {
    const labels: Record<string, string> = {
      euthanized: 'Euthanized',
      deceased: 'Died naturally',
      rehomed_to_guide: 'Rehomed to guide',
    };
    return labels[reason] ?? reason;
  }
}
