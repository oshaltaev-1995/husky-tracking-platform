import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { Observable, Subject, catchError, defer, of, shareReplay, tap, throwError } from 'rxjs';

export interface DemoSession {
  active: boolean;
  expires_at: string;
  ttl_hours: number;
  ttl_seconds: number;
  created: boolean;
  replaced_expired: boolean;
}

export interface DemoReset {
  status: string;
  expires_at: string;
}

@Injectable({ providedIn: 'root' })
export class DemoSessionService {
  private readonly http = inject(HttpClient);
  private request?: Observable<DemoSession>;
  readonly session = signal<DemoSession | null>(null);
  readonly resetReviewOpened$ = new Subject<void>();
  readonly resetStarted$ = new Subject<void>();
  readonly resetCompleted$ = new Subject<void>();
  readonly resetFailed$ = new Subject<void>();
  readonly replaced$ = new Subject<void>();

  reinitialize(): Observable<DemoSession> {
    this.session.set(null);
    this.request = undefined;
    return this.ensure();
  }

  ensure(): Observable<DemoSession> {
    const current = this.session();
    if (current && new Date(current.expires_at).getTime() > Date.now()) return of(current);
    if (current) this.request = undefined;
    this.request ??= this.http.get<DemoSession>('/api/v1/demo/session').pipe(
      tap((session) => this.session.set(session)),
      shareReplay({ bufferSize: 1, refCount: false }),
    );
    return this.request;
  }

  reset(): Observable<DemoReset> {
    return defer(() => {
      this.resetStarted$.next();
      return this.http.post<DemoReset>('/api/v1/demo/reset', {});
    }).pipe(
      tap((result) => {
        const current = this.session();
        if (current) this.session.set({ ...current, expires_at: result.expires_at });
        this.resetCompleted$.next();
      }),
      catchError((error: unknown) => {
        this.resetFailed$.next();
        return throwError(() => error);
      }),
    );
  }

  recognizeReplacement(expiresAt: string): void {
    const current = this.session();
    this.session.set({
      active: true,
      expires_at: expiresAt,
      ttl_hours: current?.ttl_hours ?? 24,
      ttl_seconds: current?.ttl_seconds ?? 86400,
      created: true,
      replaced_expired: true,
    });
    this.request = undefined;
    this.replaced$.next();
  }
}
