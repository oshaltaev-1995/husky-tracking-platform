import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';

import { SeoService } from './core/seo/seo.service';

@Component({
  selector: 'ht-root',
  imports: [RouterOutlet],
  template: '<router-outlet />',
  styles: ':host { display: block; min-height: 100vh; }',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AppComponent {
  private readonly seo = inject(SeoService);

  constructor() {
    this.seo.start();
  }
}
