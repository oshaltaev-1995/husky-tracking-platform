import { DOCUMENT } from '@angular/common';
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
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';

import { BrandMarkComponent } from '../../shared/brand-mark/brand-mark.component';

@Component({
  selector: 'ht-public-shell',
  imports: [BrandMarkComponent, RouterLink, RouterLinkActive, RouterOutlet],
  templateUrl: './public-shell.component.html',
  styleUrl: './public-shell.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PublicShellComponent {
  private readonly router = inject(Router);
  private readonly document = inject(DOCUMENT);
  private readonly destroyRef = inject(DestroyRef);
  private readonly menuButton = viewChild<ElementRef<HTMLButtonElement>>('menuButton');
  private readonly mobileMenu = viewChild<ElementRef<HTMLElement>>('mobileMenu');
  private readonly mainContent = viewChild<ElementRef<HTMLElement>>('mainContent');

  protected readonly menuOpen = signal(false);
  protected readonly year = new Date().getUTCFullYear();

  protected skipLinkHref(): string {
    return `${this.router.url.split('#')[0]}#public-content`;
  }

  protected skipToContent(event: MouseEvent): void {
    event.preventDefault();
    this.mainContent()?.nativeElement.focus();
  }

  constructor() {
    this.router.events
      .pipe(
        filter((event): event is NavigationEnd => event instanceof NavigationEnd),
        takeUntilDestroyed(),
      )
      .subscribe(() => this.closeMenu(false));
    this.destroyRef.onDestroy(() => this.document.body.classList.remove('mobile-nav-open'));
  }

  protected openMenu(): void {
    this.menuOpen.set(true);
    this.document.body.classList.add('mobile-nav-open');
    this.document.defaultView?.setTimeout(() => {
      this.mobileMenu()?.nativeElement.querySelector<HTMLElement>('a, button')?.focus();
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

  protected handleMenuKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      event.preventDefault();
      this.closeMenu();
      return;
    }
    if (event.key !== 'Tab') return;
    const elements = Array.from(
      this.mobileMenu()?.nativeElement.querySelectorAll<HTMLElement>('a[href], button') ?? [],
    );
    if (!elements.length) return;
    const first = elements[0];
    const last = elements[elements.length - 1];
    if (event.shiftKey && this.document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && this.document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
}
