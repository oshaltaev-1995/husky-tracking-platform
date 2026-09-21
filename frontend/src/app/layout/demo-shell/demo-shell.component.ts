import { AsyncPipe, DatePipe, DOCUMENT, NgTemplateOutlet } from '@angular/common';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import {
  NavigationEnd,
  Router,
  RouterLink,
  RouterLinkActive,
  RouterOutlet,
} from '@angular/router';
import { catchError, filter, map, of, shareReplay, startWith } from 'rxjs';

import { HealthService } from '../../core/api/health.service';
import { DemoSessionService } from '../../core/api/demo-session.service';
import { BrandMarkComponent } from '../../shared/brand-mark/brand-mark.component';
import { NavIconComponent, NavIconName } from '../../shared/nav-icon/nav-icon.component';

type ConnectionState =
  | { kind: 'loading' }
  | { kind: 'connected'; season: string; referenceDate: string }
  | { kind: 'unavailable' };

interface NavigationItem {
  label: string;
  route: string;
  icon: NavIconName;
}

interface NavigationSection {
  label: string;
  items: NavigationItem[];
}

@Component({
  selector: 'ht-demo-shell',
  imports: [AsyncPipe, BrandMarkComponent, DatePipe, NavIconComponent, NgTemplateOutlet, RouterLink, RouterLinkActive, RouterOutlet],
  templateUrl: './demo-shell.component.html',
  styleUrl: './demo-shell.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DemoShellComponent {
  private readonly health = inject(HealthService);
  protected readonly demoSession = inject(DemoSessionService);
  private readonly router = inject(Router);
  private readonly document = inject(DOCUMENT);
  private readonly destroyRef = inject(DestroyRef);
  private readonly menuButton = viewChild<ElementRef<HTMLButtonElement>>('menuButton');
  private readonly mobileDrawer = viewChild<ElementRef<HTMLElement>>('mobileDrawer');
  private readonly mainContent = viewChild<ElementRef<HTMLElement>>('mainContent');

  protected readonly menuOpen = signal(false);
  protected readonly resetConfirming = signal(false);
  protected readonly resetting = signal(false);
  protected readonly resetMessage = signal<string | null>(null);
  protected readonly layoutMode = signal<'standard' | 'wide'>('standard');

  protected skipLinkHref(): string {
    return `${this.router.url.split('#')[0]}#main-content`;
  }

  protected skipToContent(event: MouseEvent): void {
    event.preventDefault();
    this.mainContent()?.nativeElement.focus();
  }
  protected readonly navigation: NavigationSection[] = [
    {
      label: 'Overview',
      items: [{ label: 'Dashboard', route: '/demo/dashboard', icon: 'dashboard' }],
    },
    {
      label: 'Kennel',
      items: [
        { label: 'Dogs', route: '/demo/dogs', icon: 'dogs' },
        { label: 'Kennel Map', route: '/demo/kennel', icon: 'kennel' },
      ],
    },
    {
      label: 'Operations',
      items: [
        { label: 'Daily Plan', route: '/demo/daily', icon: 'daily' },
        { label: 'Daily Entry', route: '/demo/daily-entry', icon: 'entry' },
      ],
    },
    {
      label: 'Insights',
      items: [{ label: 'Analytics', route: '/demo/analytics', icon: 'analytics' }],
    },
    {
      label: 'Records',
      items: [{ label: 'Archive', route: '/demo/archive', icon: 'archive' }],
    },
  ];

  protected readonly connection$ = this.health.getStatus().pipe(
    map(
      (status): ConnectionState => ({
        kind: 'connected',
        season: status.demo_season.replace('Demo season — ', ''),
        referenceDate: status.demo_reference_date,
      }),
    ),
    startWith<ConnectionState>({ kind: 'loading' }),
    catchError(() => of<ConnectionState>({ kind: 'unavailable' })),
    shareReplay({ bufferSize: 1, refCount: true }),
  );

  constructor() {
    this.router.events
      .pipe(
        filter((event): event is NavigationEnd => event instanceof NavigationEnd),
        takeUntilDestroyed(),
      )
      .subscribe(() => {
        let route = this.router.routerState.snapshot.root;
        while (route.firstChild) route = route.firstChild;
        this.layoutMode.set(route.data['layout'] === 'wide' ? 'wide' : 'standard');
        this.closeMenu(false);
      });
    this.destroyRef.onDestroy(() => this.document.body.classList.remove('mobile-nav-open'));
  }

  protected openMenu(): void {
    this.menuOpen.set(true);
    this.document.body.classList.add('mobile-nav-open');
    this.document.defaultView?.setTimeout(() => {
      this.mobileDrawer()?.nativeElement.querySelector<HTMLElement>('button, a')?.focus();
    }, 0);
  }

  protected closeMenu(restoreFocus = true): void {
    if (!this.menuOpen()) return;
    this.menuOpen.set(false);
    this.document.body.classList.remove('mobile-nav-open');
    if (restoreFocus) {
      this.document.defaultView?.setTimeout(() => this.menuButton()?.nativeElement.focus(), 0);
    }
  }

  protected handleDrawerKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      event.preventDefault();
      this.closeMenu();
      return;
    }
    if (event.key !== 'Tab') return;

    const focusable = Array.from(
      this.mobileDrawer()?.nativeElement.querySelectorAll<HTMLElement>('button, a[href]') ?? [],
    ).filter((element) => !element.hasAttribute('disabled'));
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && this.document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && this.document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  protected requestReset(): void {
    this.resetMessage.set(null);
    this.resetConfirming.set(true);
  }

  protected cancelReset(): void {
    this.resetConfirming.set(false);
  }

  protected confirmReset(): void {
    this.resetting.set(true);
    this.demoSession.reset().subscribe({
      next: () => {
        this.resetMessage.set('Your demo changes were reset. Reloading the shared baseline…');
        this.document.defaultView?.setTimeout(() => this.document.defaultView?.location.reload(), 500);
      },
      error: () => {
        this.resetting.set(false);
        this.resetConfirming.set(false);
        this.resetMessage.set('Reset could not be completed. Please try again.');
      },
    });
  }
}
