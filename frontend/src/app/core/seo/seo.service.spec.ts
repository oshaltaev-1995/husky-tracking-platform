import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { SeoService } from './seo.service';

describe('SeoService production origin', () => {
  afterEach(() => {
    delete (window as Window & { __HT_CONFIG__?: unknown }).__HT_CONFIG__;
    document.querySelector('#ht-product-schema')?.remove();
  });

  it('uses runtime PUBLIC_BASE_URL instead of a build-time localhost value', () => {
    (window as Window & { __HT_CONFIG__?: { publicBaseUrl: string } }).__HT_CONFIG__ = {
      publicBaseUrl: 'https://huskytracking.com/',
    };
    TestBed.configureTestingModule({ providers: [provideRouter([])] });

    const service = TestBed.inject(SeoService);

    expect(service['publicSiteUrl']()).toBe('https://huskytracking.com');
    service['updateStructuredData'](service['publicSiteUrl']());
    const schema = document.querySelector<HTMLScriptElement>('#ht-product-schema');
    expect(schema?.textContent).toContain('"url":"https://huskytracking.com/"');
    expect(schema?.textContent).toContain('"applicationCategory":"BusinessApplication"');
    expect(schema?.textContent).toContain('professional sled-dog kennels and safari teams');
    expect(schema?.textContent).not.toContain('"offers"');
  });

  it('publishes the complete versioned social preview metadata', () => {
    (window as Window & { __HT_CONFIG__?: { publicBaseUrl: string } }).__HT_CONFIG__ = {
      publicBaseUrl: 'https://huskytracking.com/',
    };
    TestBed.configureTestingModule({ providers: [provideRouter([])] });

    const service = TestBed.inject(SeoService);
    service['update']();

    const imageUrl =
      'https://huskytracking.com/assets/husky-tracking-social-preview-v1.jpg';
    expect(document.querySelector('meta[property="og:site_name"]')?.getAttribute('content')).toBe(
      'Husky Tracking',
    );
    expect(document.querySelector('meta[property="og:image"]')?.getAttribute('content')).toBe(
      imageUrl,
    );
    expect(
      document.querySelector('meta[property="og:image:secure_url"]')?.getAttribute('content'),
    ).toBe(imageUrl);
    expect(document.querySelector('meta[property="og:image:type"]')?.getAttribute('content')).toBe(
      'image/jpeg',
    );
    expect(document.querySelector('meta[property="og:image:width"]')?.getAttribute('content')).toBe(
      '1200',
    );
    expect(document.querySelector('meta[property="og:image:height"]')?.getAttribute('content')).toBe(
      '630',
    );
    expect(document.querySelector('meta[property="og:image:alt"]')?.getAttribute('content')).toContain(
      'fictional sled dog',
    );
    expect(document.querySelector('meta[name="twitter:card"]')?.getAttribute('content')).toBe(
      'summary_large_image',
    );
    expect(document.querySelector('meta[name="twitter:image"]')?.getAttribute('content')).toBe(
      imageUrl,
    );
    expect(document.querySelector('meta[name="twitter:image:alt"]')?.getAttribute('content')).toContain(
      'operational kennel snapshot',
    );
  });
});
