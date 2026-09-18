import { AsyncPipe, DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { catchError, of, shareReplay } from 'rxjs';

import { PrivacyService } from '../../../core/api/privacy.service';

@Component({
  selector: 'ht-privacy-page',
  imports: [AsyncPipe, DatePipe],
  templateUrl: './privacy-page.component.html',
  styleUrl: './privacy-page.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PrivacyPageComponent {
  private readonly privacy = inject(PrivacyService);
  protected readonly metadata$ = this.privacy.getMetadata().pipe(
    catchError(() => of(null)),
    shareReplay({ bufferSize: 1, refCount: true }),
  );
}
