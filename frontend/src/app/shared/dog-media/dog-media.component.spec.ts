import { TestBed } from '@angular/core/testing';

import { DOG_MEDIA_VERSION, DogMediaComponent } from './dog-media.component';

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
});
