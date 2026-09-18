import { inject } from '@angular/core';
import { CanActivateFn } from '@angular/router';
import { map } from 'rxjs';

import { DemoSessionService } from '../api/demo-session.service';

export const demoSessionGuard: CanActivateFn = () =>
  inject(DemoSessionService)
    .ensure()
    .pipe(map(() => true));
