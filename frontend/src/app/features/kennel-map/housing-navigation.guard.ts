import { Injectable, inject } from '@angular/core';
import { CanActivateFn, CanDeactivateFn, Router } from '@angular/router';

import type { KennelMapPageComponent } from './kennel-map-page.component';

/** Only the mounted map registers. No housing data or session identity is retained here. */
@Injectable({ providedIn: 'root' })
export class HousingNavigationGuardState {
  current: { date: () => string; leave: () => boolean | Promise<boolean> } | null = null;
}

export const housingLeaveGuard: CanDeactivateFn<KennelMapPageComponent> = (component, route, _state, nextState) => {
  const next = inject(Router).parseUrl(nextState.url);
  const path = next.root.children['primary']?.segments.map((segment) => segment.path).join('/');
  if (path === 'demo/kennel' && (next.queryParams['date'] ?? '2026-03-31') === (route.queryParamMap.get('date') ?? '2026-03-31')) return true;
  return component?.canLeave() ?? true;
};

export const housingDateGuard: CanActivateFn = (route) => {
  const current = inject(HousingNavigationGuardState).current;
  const date = route.queryParamMap.get('date') ?? '2026-03-31';
  return !current || date === current.date() ? true : current.leave();
};
