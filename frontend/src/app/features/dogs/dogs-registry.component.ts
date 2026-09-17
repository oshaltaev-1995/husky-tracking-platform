import { AsyncPipe, TitleCasePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { BehaviorSubject, catchError, map, of, startWith, switchMap } from 'rxjs';

import { DogsQuery, DogsService } from '../../core/api/dogs.service';
import { DogMediaComponent } from '../../shared/dog-media/dog-media.component';

@Component({
  selector: 'ht-dogs-registry',
  imports: [AsyncPipe, DogMediaComponent, FormsModule, RouterLink, TitleCasePipe],
  templateUrl: './dogs-registry.component.html',
  styleUrl: './dogs-registry.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DogsRegistryComponent {
  private readonly dogsService = inject(DogsService);
  private readonly query = new BehaviorSubject<DogsQuery>({ sort: 'name' });

  protected filters: DogsQuery = { sort: 'name' };
  protected readonly state$ = this.query.pipe(
    switchMap((query) =>
      this.dogsService.getDogs(query).pipe(
        map((data) => ({ kind: 'ready' as const, data })),
        startWith({ kind: 'loading' as const }),
        catchError(() => of({ kind: 'error' as const })),
      ),
    ),
  );

  protected applyFilters() {
    this.query.next({ ...this.filters });
  }

  protected resetFilters() {
    this.filters = { sort: 'name' };
    this.applyFilters();
  }
}
