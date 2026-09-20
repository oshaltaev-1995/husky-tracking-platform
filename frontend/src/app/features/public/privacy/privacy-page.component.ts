import { AsyncPipe, DatePipe, DOCUMENT } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { catchError, filter, of, shareReplay } from 'rxjs';
import { Router, RouterLink, Scroll } from '@angular/router';

import { PrivacyService } from '../../../core/api/privacy.service';

@Component({
  selector: 'ht-privacy-page',
  imports: [AsyncPipe, DatePipe, RouterLink],
  templateUrl: './privacy-page.component.html',
  styleUrl: './privacy-page.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PrivacyPageComponent {
  private readonly privacy = inject(PrivacyService);
  private readonly router = inject(Router);
  private readonly document = inject(DOCUMENT);
  protected readonly metadata$ = this.privacy.getMetadata().pipe(
    catchError(() => of(null)),
    shareReplay({ bufferSize: 1, refCount: true }),
  );

  constructor() {
    this.router.events.pipe(
      filter((event): event is Scroll => event instanceof Scroll && Boolean(event.anchor)),
      takeUntilDestroyed(),
    ).subscribe((event) => {
      const fragment = event.anchor;
      if (!fragment || !['anonymous-demo', 'contact-form', 'technical-data', 'your-choices'].includes(fragment)) return;
      this.document.defaultView?.requestAnimationFrame(() => {
        this.document.getElementById(fragment)?.scrollIntoView({ block: 'start', behavior: 'instant' });
      });
    });
  }
}
