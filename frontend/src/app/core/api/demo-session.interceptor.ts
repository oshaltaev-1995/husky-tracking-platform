import { HttpEvent, HttpHandlerFn, HttpRequest, HttpResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { Observable, tap } from 'rxjs';

import { DemoSessionService } from './demo-session.service';

export function demoSessionInterceptor(
  request: HttpRequest<unknown>,
  next: HttpHandlerFn,
): Observable<HttpEvent<unknown>> {
  const demoSession = inject(DemoSessionService);
  return next(request).pipe(
    tap((event) => {
      if (!(event instanceof HttpResponse)) return;
      if (event.headers.get('X-Demo-Session-State') !== 'replaced-expired') return;
      const expiresAt = event.headers.get('X-Demo-Session-Expires-At');
      if (expiresAt) demoSession.recognizeReplacement(expiresAt);
    }),
  );
}
