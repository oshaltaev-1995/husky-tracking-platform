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
  });
});
