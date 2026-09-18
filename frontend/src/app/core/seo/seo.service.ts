import { DOCUMENT } from '@angular/common';
import { DestroyRef, Injectable, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Meta, Title } from '@angular/platform-browser';
import { ActivatedRouteSnapshot, NavigationEnd, Router } from '@angular/router';
import { filter } from 'rxjs';

export const PUBLIC_SITE_URL = 'https://huskytracking.com';
const DEFAULT_DESCRIPTION =
  'Explore Husky Tracking, an independent demonstration of modern sled-dog kennel operations software.';
const DEFAULT_SOCIAL_IMAGE =
  '/media/dogs/9422673b-331b-5e72-a700-5fff0574a209.webp?v=dog-media-v1';

@Injectable({ providedIn: 'root' })
export class SeoService {
  private readonly router = inject(Router);
  private readonly title = inject(Title);
  private readonly meta = inject(Meta);
  private readonly document = inject(DOCUMENT);
  private readonly destroyRef = inject(DestroyRef);
  private started = false;

  start(): void {
    if (this.started) return;
    this.started = true;
    this.router.events
      .pipe(
        filter((event): event is NavigationEnd => event instanceof NavigationEnd),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe(() => this.update());
    this.update();
  }

  private update(): void {
    const route = this.deepest(this.router.routerState.snapshot.root);
    const title = typeof route.title === 'string' ? route.title : 'Husky Tracking';
    const description =
      typeof route.data['description'] === 'string'
        ? route.data['description']
        : DEFAULT_DESCRIPTION;
    const path = this.router.url.split('?')[0].split('#')[0];
    const publicPath = path === '/' || ['/features', '/about', '/contact'].includes(path);
    const canonicalUrl = `${PUBLIC_SITE_URL}${publicPath ? path : '/'}`;
    const imageUrl = `${PUBLIC_SITE_URL}${DEFAULT_SOCIAL_IMAGE}`;

    this.title.setTitle(title);
    this.meta.updateTag({ name: 'description', content: description });
    this.meta.updateTag({ name: 'robots', content: publicPath ? 'index,follow' : 'noindex,follow' });
    this.meta.updateTag({ property: 'og:title', content: title });
    this.meta.updateTag({ property: 'og:description', content: description });
    this.meta.updateTag({ property: 'og:type', content: 'website' });
    this.meta.updateTag({ property: 'og:url', content: canonicalUrl });
    this.meta.updateTag({ property: 'og:image', content: imageUrl });
    this.meta.updateTag({ name: 'twitter:card', content: 'summary_large_image' });
    this.meta.updateTag({ name: 'twitter:title', content: title });
    this.meta.updateTag({ name: 'twitter:description', content: description });
    this.meta.updateTag({ name: 'twitter:image', content: imageUrl });
    this.updateCanonical(canonicalUrl);
  }

  private deepest(route: ActivatedRouteSnapshot): ActivatedRouteSnapshot {
    let current = route;
    while (current.firstChild) current = current.firstChild;
    return current;
  }

  private updateCanonical(url: string): void {
    let link = this.document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
    if (!link) {
      link = this.document.createElement('link');
      link.rel = 'canonical';
      this.document.head.append(link);
    }
    link.href = url;
  }
}
