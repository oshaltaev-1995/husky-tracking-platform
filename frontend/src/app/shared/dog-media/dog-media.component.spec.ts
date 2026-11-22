import { vi } from 'vitest';
import { TestBed } from '@angular/core/testing';

import { DOG_MEDIA_PRINT_TIMEOUT_MS, DOG_MEDIA_VERSION, DogMediaComponent } from './dog-media.component';

const photoKey = '9422673b-331b-5e72-a700-5fff0574a209.webp';

describe('DogMediaComponent', () => {
  async function render(options?: {
    photoKey?: string | null;
    size?: 'card' | 'compact' | 'profile';
    expandable?: boolean;
  }) {
    await TestBed.configureTestingModule({ imports: [DogMediaComponent] }).compileComponents();
    const fixture = TestBed.createComponent(DogMediaComponent);
    fixture.componentRef.setInput('name', 'Aurora');
    fixture.componentRef.setInput('photoKey', options?.photoKey ?? null);
    fixture.componentRef.setInput('size', options?.size ?? 'card');
    fixture.componentRef.setInput('expandable', options?.expandable ?? false);
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

  it('makes only an explicitly opted-in real portrait enlargeable and preserves its exact URL', async () => {
    const fixture = await render({ photoKey, size: 'profile', expandable: true });
    const trigger = fixture.nativeElement.querySelector('.photo-enlarge') as HTMLButtonElement;
    expect(trigger.getAttribute('aria-label')).toBe('Enlarge portrait of Aurora');
    expect(trigger.textContent).toContain('Enlarge photo');
    trigger.focus();
    trigger.click();
    fixture.detectChanges();
    await fixture.whenStable();
    const dialog = fixture.nativeElement.querySelector('[role="dialog"]') as HTMLElement;
    expect(dialog.getAttribute('aria-modal')).toBe('true');
    expect(dialog.querySelector('h2')?.textContent).toBe('Aurora');
    const full = dialog.querySelector('img') as HTMLImageElement;
    expect(full.getAttribute('src')).toBe(fixture.nativeElement.querySelector('.dog-media img').getAttribute('src'));
    expect(full.getAttribute('alt')).toBe('Portrait of Aurora');
    expect(dialog.textContent).toContain('Loading portrait');
    Object.defineProperty(full, 'naturalWidth', { value: 1086 });
    full.dispatchEvent(new Event('load'));
    fixture.detectChanges();
    expect(full.classList.contains('loaded')).toBe(true);
    full.click();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="dialog"]')).not.toBeNull();
    expect(document.body.classList.contains('ht-dog-photo-open')).toBe(true);
    const close = dialog.querySelector('button')!;
    expect(document.activeElement).toBe(close);
    for (const shiftKey of [false, true]) {
      const tab = new KeyboardEvent('keydown', { key: 'Tab', shiftKey, bubbles: true, cancelable: true });
      document.dispatchEvent(tab);
      expect(tab.defaultPrevented).toBe(true);
      expect(document.activeElement).toBe(close);
    }
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }));
    fixture.detectChanges();
    await fixture.whenStable();
    expect(fixture.nativeElement.querySelector('[role="dialog"]')).toBeNull();
    expect(document.body.classList.contains('ht-dog-photo-open')).toBe(false);
    expect(document.activeElement).toBe(trigger);
  });

  it('keeps Close operable on viewer error and restores focus without changing the canonical thumbnail', async () => {
    const fixture = await render({ photoKey, expandable: true });
    const trigger = fixture.nativeElement.querySelector('.photo-enlarge') as HTMLButtonElement;
    trigger.focus();
    trigger.click();
    fixture.detectChanges();
    await fixture.whenStable();
    const failedImage = fixture.nativeElement.querySelector('ht-dog-photo-viewer img') as HTMLImageElement;
    failedImage.dispatchEvent(new Event('error'));
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('ht-dog-photo-viewer [role="alert"]')?.textContent).toContain('could not be loaded');
    const close = fixture.nativeElement.querySelector('ht-dog-photo-viewer button') as HTMLButtonElement;
    expect(close.disabled).toBe(false);
    close.click();
    fixture.detectChanges();
    await fixture.whenStable();
    expect(document.activeElement).toBe(trigger);
    expect(fixture.nativeElement.querySelector('.dog-media img').getAttribute('src')).toContain(photoKey);
    expect(document.body.classList.contains('ht-dog-photo-open')).toBe(false);
  });

  it('does not offer enlargement for placeholder, unsafe or failed media, or ordinary registry media', async () => {
    const fixture = await render({ expandable: true });
    expect(fixture.nativeElement.querySelector('.photo-enlarge')).toBeNull();
    fixture.componentRef.setInput('photoKey', '../outside.webp');
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.photo-enlarge')).toBeNull();
    fixture.componentRef.setInput('photoKey', photoKey);
    fixture.detectChanges();
    (fixture.nativeElement.querySelector('img') as HTMLImageElement).dispatchEvent(new Event('error'));
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.photo-enlarge')).toBeNull();
    fixture.componentRef.setInput('photoKey', 'b265ec9a-985f-5533-9142-7ba9d59f899f.webp');
    fixture.componentRef.setInput('expandable', false);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('img')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('.photo-enlarge')).toBeNull();
  });

  it('closes on identity/media replacement and ignores a late old image event', async () => {
    const fixture = await render({ photoKey, expandable: true });
    (fixture.nativeElement.querySelector('.photo-enlarge') as HTMLButtonElement).click();
    fixture.detectChanges();
    await fixture.whenStable();
    const oldImage = fixture.nativeElement.querySelector('ht-dog-photo-viewer img') as HTMLImageElement;
    fixture.componentRef.setInput('name', 'Cedar');
    fixture.componentRef.setInput('photoKey', 'b265ec9a-985f-5533-9142-7ba9d59f899f.webp');
    fixture.detectChanges();
    await fixture.whenStable();
    expect(fixture.nativeElement.querySelector('[role="dialog"]')).toBeNull();
    oldImage.dispatchEvent(new Event('load'));
    oldImage.dispatchEvent(new Event('error'));
    fixture.detectChanges();
    (fixture.nativeElement.querySelector('.photo-enlarge') as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('ht-dog-photo-viewer h2')?.textContent).toBe('Cedar');
    expect(fixture.nativeElement.querySelector('ht-dog-photo-viewer img').getAttribute('src')).not.toContain(photoKey);
    expect(fixture.nativeElement.querySelector('ht-dog-photo-viewer').textContent).toContain('Loading portrait');
    fixture.destroy();
    oldImage.dispatchEvent(new Event('load'));
    expect(document.body.classList.contains('ht-dog-photo-open')).toBe(false);
  });

  it('does not open a second modal over an existing preview', async () => {
    const fixture = await render({ photoKey, expandable: true });
    const existing = document.createElement('section');
    existing.setAttribute('role', 'dialog');
    existing.setAttribute('aria-modal', 'true');
    document.body.append(existing);
    try {
      (fixture.nativeElement.querySelector('.photo-enlarge') as HTMLButtonElement).click();
      fixture.detectChanges();
      expect(fixture.nativeElement.querySelector('ht-dog-photo-viewer')).toBeNull();
    } finally { existing.remove(); }
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
