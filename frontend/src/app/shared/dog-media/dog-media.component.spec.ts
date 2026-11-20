import { vi } from 'vitest';
import { TestBed } from '@angular/core/testing';

import { DOG_MEDIA_PRINT_TIMEOUT_MS, DOG_MEDIA_VERSION, DogMediaComponent } from './dog-media.component';

const photoKey = '9422673b-331b-5e72-a700-5fff0574a209.webp';

describe('DogMediaComponent', () => {
  async function render(options?: {
    photoKey?: string | null;
    size?: 'card' | 'compact' | 'profile';
  }) {
    await TestBed.configureTestingModule({ imports: [DogMediaComponent] }).compileComponents();
    const fixture = TestBed.createComponent(DogMediaComponent);
    fixture.componentRef.setInput('name', 'Aurora');
    fixture.componentRef.setInput('photoKey', options?.photoKey ?? null);
    fixture.componentRef.setInput('size', options?.size ?? 'card');
    fixture.detectChanges();
    return fixture;
  }

  it('renders a stable accessible placeholder without requesting a missing image', async () => {
    const fixture = await render();
    expect(fixture.nativeElement.querySelector('img')).toBeNull();
    const fallback = fixture.nativeElement.querySelector('[role="img"]') as HTMLElement;
    expect(fallback.getAttribute('aria-label')).toBe('Portrait of Aurora');
    expect(fixture.nativeElement.textContent).toContain('A');
  });

  it('builds the canonical versioned URL and lazy-loads registry media', async () => {
    const fixture = await render({ photoKey });
    const image = fixture.nativeElement.querySelector('img') as HTMLImageElement;
    expect(image.getAttribute('src')).toBe(`/media/dogs/${photoKey}?v=${DOG_MEDIA_VERSION}`);
    expect(image.getAttribute('alt')).toBe('Portrait of Aurora');
    expect(image.getAttribute('loading')).toBe('lazy');
  });

  it('loads the profile hero eagerly and falls back after a load failure', async () => {
    const fixture = await render({ photoKey, size: 'profile' });
    const image = fixture.nativeElement.querySelector('img') as HTMLImageElement;
    expect(image.getAttribute('loading')).toBe('eager');
    expect(image.getAttribute('fetchpriority')).toBe('high');

    image.dispatchEvent(new Event('error'));
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('img')).toBeNull();
    expect(fixture.nativeElement.querySelector('[role="img"]')).not.toBeNull();
  });

  it('rejects non-canonical keys instead of issuing an unsafe request', async () => {
    const fixture = await render({ photoKey: '../outside.webp' });
    expect(fixture.nativeElement.querySelector('img')).toBeNull();
  });
  it('prepares an already decoded portrait and does not decode another dog after destroy', async () => {
    const fixture = await render({ photoKey, size: 'profile' });
    const image = fixture.nativeElement.querySelector('img') as HTMLImageElement;
    Object.defineProperty(image, 'complete', { value: true });
    Object.defineProperty(image, 'naturalWidth', { value: 1086 });
    const decode = vi.fn().mockResolvedValue(undefined);
    image.decode = decode;
    await fixture.componentInstance.whenReady();
    expect(decode).toHaveBeenCalledTimes(1);
    fixture.destroy();
    await fixture.componentInstance.whenReady();
    expect(decode).toHaveBeenCalledTimes(1);
  });

  it('bounds print preparation with a rendered fallback when loading never finishes', async () => {
    vi.useFakeTimers();
    try {
      const fixture = await render({ photoKey, size: 'profile' });
      const image = fixture.nativeElement.querySelector('img') as HTMLImageElement;
      Object.defineProperty(image, 'complete', { value: false });
      const prepared = fixture.componentInstance.whenReady();
      await vi.advanceTimersByTimeAsync(DOG_MEDIA_PRINT_TIMEOUT_MS);
      await prepared;
      expect(fixture.nativeElement.querySelector('img')).toBeNull();
      expect(fixture.nativeElement.querySelector('[role="img"]').getAttribute('aria-label')).toBe('Portrait of Aurora');
    } finally { vi.useRealTimers(); }
  });

  it('resolves preparation on failure or teardown without stale decode changing a new portrait', async () => {
    const fixture = await render({ photoKey, size: 'profile' });
    const image = fixture.nativeElement.querySelector('img') as HTMLImageElement;
    Object.defineProperty(image, 'complete', { value: false });
    Object.defineProperty(image, 'naturalWidth', { value: 1086 });
    let rejectDecode!: () => void;
    image.decode = () => new Promise<void>((_, reject) => { rejectDecode = reject; });
    const prepared = fixture.componentInstance.whenReady();
    image.dispatchEvent(new Event('load'));
    fixture.componentRef.setInput('photoKey', 'b265ec9a-985f-5533-9142-7ba9d59f899f.webp');
    fixture.componentRef.setInput('name', 'Cedar');
    fixture.detectChanges();
    rejectDecode();
    await prepared;
    expect(fixture.nativeElement.querySelector('img').getAttribute('alt')).toBe('Portrait of Cedar');
    const pending = fixture.componentInstance.whenReady();
    fixture.destroy();
    await pending;
  });

});
