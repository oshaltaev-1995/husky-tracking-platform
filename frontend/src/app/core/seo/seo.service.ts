import { DOCUMENT } from '@angular/common';
import { DestroyRef, Injectable, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Meta, Title } from '@angular/platform-browser';
import { ActivatedRouteSnapshot, NavigationEnd, Router } from '@angular/router';
import { filter } from 'rxjs';

const DEFAULT_DESCRIPTION =
  'Explore Husky Tracking, an operations platform preview for professional sled-dog kennels and safari teams, covering planning, teams, actual work and workload.';
const DEFAULT_SOCIAL_IMAGE =
  '/assets/husky-tracking-social-preview-v1.jpg';
const SOCIAL_IMAGE_ALT =
  'Husky Tracking interface showing a fictional sled dog and operational kennel snapshot';

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
    const publicPath = path === '/' || ['/features', '/about', '/contact', '/privacy'].includes(path);
    const publicSiteUrl = this.publicSiteUrl();
    const canonicalUrl = `${publicSiteUrl}${publicPath ? path : '/'}`;
    const imageUrl = `${publicSiteUrl}${DEFAULT_SOCIAL_IMAGE}`;

    this.title.setTitle(title);
    this.meta.updateTag({ name: 'description', content: description });
    this.meta.updateTag({ name: 'robots', content: publicPath ? 'index,follow' : 'noindex,follow' });
    this.meta.updateTag({ property: 'og:title', content: title });
    this.meta.updateTag({ property: 'og:description', content: description });
    this.meta.updateTag({ property: 'og:type', content: 'website' });
    this.meta.updateTag({ property: 'og:site_name', content: 'Husky Tracking' });
    this.meta.updateTag({ property: 'og:url', content: canonicalUrl });
    this.meta.updateTag({ property: 'og:image', content: imageUrl });
    this.meta.updateTag({ property: 'og:image:secure_url', content: imageUrl });
    this.meta.updateTag({ property: 'og:image:type', content: 'image/jpeg' });
    this.meta.updateTag({ property: 'og:image:width', content: '1200' });
    this.meta.updateTag({ property: 'og:image:height', content: '630' });
    this.meta.updateTag({ property: 'og:image:alt', content: SOCIAL_IMAGE_ALT });
    this.meta.updateTag({ name: 'twitter:card', content: 'summary_large_image' });
    this.meta.updateTag({ name: 'twitter:title', content: title });
    this.meta.updateTag({ name: 'twitter:description', content: description });
    this.meta.updateTag({ name: 'twitter:image', content: imageUrl });
    this.meta.updateTag({ name: 'twitter:image:alt', content: SOCIAL_IMAGE_ALT });
    this.updateCanonical(canonicalUrl);
    this.updateStructuredData(publicSiteUrl);
  }

  private publicSiteUrl(): string {
    const runtimeWindow = this.document.defaultView as
      | (Window & { __HT_CONFIG__?: { publicBaseUrl?: string } })
      | null;
    const configured = runtimeWindow?.__HT_CONFIG__?.publicBaseUrl?.trim().replace(/\/$/, '');
    return configured || this.document.location?.origin || 'http://localhost:4300';
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

  private updateStructuredData(publicSiteUrl: string): void {
    let script = this.document.head.querySelector<HTMLScriptElement>('#ht-product-schema');
    if (!script) {
      script = this.document.createElement('script');
      script.id = 'ht-product-schema';
      script.type = 'application/ld+json';
      this.document.head.append(script);
    }
    script.textContent = JSON.stringify({
      '@context': 'https://schema.org',
      '@type': 'WebApplication',
      name: 'Husky Tracking',
      url: `${publicSiteUrl}/`,
      applicationCategory: 'BusinessApplication',
      operatingSystem: 'Web',
      description:
        'An independent operations platform preview for professional sled-dog kennels and safari teams, with an interactive fictional dataset.',
    });
  }
}
