import { AsyncPipe, TitleCasePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { BehaviorSubject, catchError, map, of, startWith, switchMap } from 'rxjs';

import { DogsQuery, DogsService } from '../../core/api/dogs.service';
import { DogMediaComponent } from '../../shared/dog-media/dog-media.component';

type FilterKey = 'search' | 'dogClass' | 'sex' | 'availability' | 'neutered' | 'housing' | 'capability';

interface ActiveFilter {
  key: FilterKey;
  label: string;
}

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

  protected filters: DogsQuery = {
    search: '',
    dogClass: '',
    sex: '',
    availability: '',
    neutered: '',
    housing: '',
    capability: '',
    sort: 'name',
  };
  protected filtersOpen = false;
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
    this.filters = {
      search: '',
      dogClass: '',
      sex: '',
      availability: '',
      neutered: '',
      housing: '',
      capability: '',
      sort: 'name',
    };
    this.applyFilters();
  }

  protected toggleFilters(): void {
    this.filtersOpen = !this.filtersOpen;
  }

  protected activeFilters(): ActiveFilter[] {
    const filters: ActiveFilter[] = [];
    if (this.filters.search) filters.push({ key: 'search', label: `Search: ${this.filters.search}` });
    if (this.filters.dogClass) filters.push({ key: 'dogClass', label: this.title(this.filters.dogClass) });
    if (this.filters.sex) filters.push({ key: 'sex', label: this.title(this.filters.sex) });
    if (this.filters.availability) filters.push({ key: 'availability', label: this.title(this.filters.availability) });
    if (this.filters.neutered) filters.push({ key: 'neutered', label: `Neutered: ${this.filters.neutered === 'true' ? 'Yes' : 'No'}` });
    if (this.filters.housing) filters.push({ key: 'housing', label: this.filters.housing === 'PUPPY' ? 'Puppy areas' : `Row ${this.filters.housing}` });
    if (this.filters.capability) filters.push({ key: 'capability', label: `${this.title(this.filters.capability)} capable` });
    return filters;
  }

  protected clearFilter(key: FilterKey): void {
    this.filters = { ...this.filters, [key]: undefined };
    this.applyFilters();
  }

  private title(value: string): string {
    return value.slice(0, 1).toUpperCase() + value.slice(1);
  }
}
