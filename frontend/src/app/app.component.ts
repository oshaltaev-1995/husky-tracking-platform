import { AsyncPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { catchError, map, of, startWith } from 'rxjs';

import { HealthService } from './core/api/health.service';

type ConnectionState =
  | { kind: 'loading' }
  | { kind: 'connected'; season: string; referenceDate: string }
  | { kind: 'unavailable' };

@Component({
  selector: 'ht-root',
  imports: [AsyncPipe],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AppComponent {
  private readonly health = inject(HealthService);

  protected readonly connection$ = this.health.getStatus().pipe(
    map(
      (status): ConnectionState => ({
        kind: 'connected',
        season: status.demo_season,
        referenceDate: status.demo_reference_date,
      }),
    ),
    startWith<ConnectionState>({ kind: 'loading' }),
    catchError(() => of<ConnectionState>({ kind: 'unavailable' })),
  );
}
