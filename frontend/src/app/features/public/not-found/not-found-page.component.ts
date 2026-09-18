import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'ht-not-found-page',
  imports: [RouterLink],
  template: `
    <article class="public-page not-found-page">
      <section class="public-page-hero">
        <div class="public-container">
          <p class="public-kicker">404 · Page not found</p>
          <h1 class="public-page-title">This trail does not lead anywhere.</h1>
          <p class="public-lead">
            The address may have changed, or the page may never have existed.
          </p>
          <div class="public-actions">
            <a class="button primary" routerLink="/">Return home</a>
            <a class="button secondary" routerLink="/demo/dashboard">Open interactive demo</a>
          </div>
        </div>
      </section>
    </article>
  `,
  styles: `
    .not-found-page { min-height: 60vh; display: grid; align-items: center; }
    .public-page-hero { width: 100%; }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class NotFoundPageComponent {}
