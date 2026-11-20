import { ApplicationRef } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { vi } from 'vitest';

import { KennelMapPrintService } from './kennel-map-print.service';
import { KennelPrintProjection } from './kennel-print-projection';

const residents = [{ id: 'test-only-identity', name: 'Atlas', marker: 'S', label: 'Standard', tone: 'standard' }];
const projection: KennelPrintProjection = {
  snapshotDate: '2026-03-31',
  layer: 'default',
  layerLabel: 'Default',
  legend: [{ label: 'Standard', marker: 'S', tone: 'standard' }],
  residentCount: 1,
  locationCount: 1,
  groups: [{ code: 'A', label: 'Zone A', rows: [{ code: 'A1', locations: [{
    code: 'A1-01', displayName: 'Adult enclosure A1-01', occupancy: 1, nominalCapacity: 2,
    residents, mapResidents: residents, continuationResidents: [], groupLabel: 'Zone A',
  }] }] }],
  puppyBuildings: [],
  continuations: [],
};

describe('Kennel print preview lifecycle', () => {
  let service: KennelMapPrintService;
  let trigger: HTMLButtonElement;
  let originalTitle: string;
  const extras: HTMLElement[] = [];

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [KennelMapPrintService] });
    service = TestBed.inject(KennelMapPrintService);
    originalTitle = document.title;
    document.title = 'Kennel Map · Husky Tracking Demo';
    trigger = document.createElement('button');
    trigger.textContent = 'Print map';
    document.body.append(trigger);
    trigger.focus();
  });

  afterEach(() => {
    service.close(false);
    trigger.remove();
    for (const extra of extras.splice(0)) extra.remove();
    document.title = originalTitle;
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  async function settle(): Promise<void> {
    await Promise.resolve();
    await TestBed.inject(ApplicationRef).whenStable();
    TestBed.tick();
  }

  async function open(): Promise<HTMLElement> {
    service.open(projection);
    await settle();
    const host = document.querySelector<HTMLElement>('ht-kennel-print-preview');
    expect(host).not.toBeNull();
    return host!;
  }

  function action(host: HTMLElement, name: string): HTMLButtonElement {
    const result = Array.from(host.querySelectorAll<HTMLButtonElement>('button'))
      .find((button) => button.textContent.trim() === name);
    if (!result) throw new Error(`Missing preview action: ${name}`);
    return result;
  }

  function printMedia(initial: boolean) {
    let matches = initial;
    const listeners = new Set<(event: MediaQueryListEvent) => void>();
    const media = {
      get matches() { return matches; },
      addEventListener: vi.fn((_type: string, callback: (event: MediaQueryListEvent) => void) => listeners.add(callback)),
      removeEventListener: vi.fn((_type: string, callback: (event: MediaQueryListEvent) => void) => listeners.delete(callback)),
    };
    vi.stubGlobal('matchMedia', vi.fn(() => media));
    return {
      media, listeners,
      change(next: boolean): void {
        matches = next;
        for (const callback of listeners) callback({ matches, media: 'print' } as MediaQueryListEvent);
      },
    };
  }

  it('attaches one dated document to body and makes content keyboard-readable before actions', async () => {
    const nativePrint = vi.spyOn(window, 'print').mockImplementation(() => undefined);
    const viewsBefore = TestBed.inject(ApplicationRef).viewCount;
    const host = await open();
    expect(service.isOpen()).toBe(true);
    expect(host.parentElement).toBe(document.body);
    expect(document.body.classList.contains('ht-kennel-print-open')).toBe(true);
    const dialog = host.querySelector('[role="dialog"]')!;
    expect(dialog.getAttribute('aria-modal')).toBe('true');
    const body = host.querySelector<HTMLElement>('.print-preview-content')!;
    expect(body.getAttribute('aria-label')).toBe('Kennel Map print document');
    expect(body.tabIndex).toBe(0);
    expect(document.activeElement).toBe(body);
    expect(host.querySelectorAll('ht-kennel-print-document').length).toBe(1);
    expect(host.textContent).toContain('Atlas');
    expect(document.title).toBe('Kennel Map · Husky Tracking Demo');
    expect(nativePrint).not.toHaveBeenCalled();
    service.close(false);
    expect(TestBed.inject(ApplicationRef).viewCount).toBe(viewsBefore);
    expect(document.querySelector('ht-kennel-print-preview')).toBeNull();
    expect(document.body.classList.contains('ht-kennel-print-open')).toBe(false);
  });

  it('wraps Tab through the content and actions and contains unexpected page focus', async () => {
    const host = await open();
    const body = host.querySelector<HTMLElement>('.print-preview-content')!;
    const print = action(host, 'Print / Save as PDF');
    print.focus();
    const next = new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true });
    document.dispatchEvent(next);
    expect(next.defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(body);
    const previous = new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true, cancelable: true });
    document.dispatchEvent(previous);
    expect(previous.defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(print);
    trigger.focus();
    expect(document.activeElement).toBe(body);
  });

  it('prints only on explicit request and preserves the same DOM after return, Cancel and repeated printing', async () => {
    const nativePrint = vi.spyOn(window, 'print').mockImplementation(() => {
      expect(document.title).toBe('Husky Tracking · Kennel Map · 2026-03-31');
      window.dispatchEvent(new Event('beforeprint'));
      window.dispatchEvent(new Event('afterprint'));
    });
    const host = await open();
    const documentNode = host.querySelector('ht-kennel-print-document');
    const print = action(host, 'Print / Save as PDF');
    expect(print.disabled).toBe(false);
    print.click();
    await settle();
    expect(nativePrint).toHaveBeenCalledTimes(1);
    expect(document.querySelector('ht-kennel-print-preview')).toBe(host);
    expect(host.querySelector('ht-kennel-print-document')).toBe(documentNode);
    expect(service.isOpen()).toBe(true);
    expect(document.title).toBe('Kennel Map · Husky Tracking Demo');
    expect(host.textContent).toContain('Print dialog closed');
    expect(host.textContent).not.toMatch(/PDF (?:was |is )?saved|successfully saved/i);
    print.click();
    await settle();
    expect(nativePrint).toHaveBeenCalledTimes(2);
    expect(host.querySelector('ht-kennel-print-document')).toBe(documentNode);
  });

  it('keeps the document when print returns before afterprint, and supports native keyboard print events', async () => {
    const nativePrint = vi.spyOn(window, 'print').mockImplementation(() => {
      window.dispatchEvent(new Event('beforeprint'));
    });
    const host = await open();
    action(host, 'Print / Save as PDF').click();
    await settle();
    expect(action(host, 'Print / Save as PDF').disabled).toBe(true);
    expect(action(host, 'Close').disabled).toBe(true);
    expect(document.title).toBe('Husky Tracking · Kennel Map · 2026-03-31');
    expect(host.isConnected).toBe(true);
    window.dispatchEvent(new Event('afterprint'));
    await settle();
    expect(action(host, 'Print / Save as PDF').disabled).toBe(false);
    expect(document.title).toBe('Kennel Map · Husky Tracking Demo');
    // Browser Ctrl/Cmd+P dispatches these events itself; the component never calls
    // print recursively from either event or intercepts the native shortcut.
    const shortcut = new KeyboardEvent('keydown', { key: 'p', ctrlKey: true, bubbles: true, cancelable: true });
    document.dispatchEvent(shortcut);
    expect(shortcut.defaultPrevented).toBe(false);
    window.dispatchEvent(new Event('beforeprint'));
    window.dispatchEvent(new Event('afterprint'));
    await settle();
    expect(nativePrint).toHaveBeenCalledTimes(1);
    expect(host.isConnected).toBe(true);
  });

  it('closes with Escape, restores the trigger/title and leaves no print listeners behind', async () => {
    const host = await open();
    host.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }));
    await settle();
    expect(service.isOpen()).toBe(false);
    expect(document.activeElement).toBe(trigger);
    expect(document.title).toBe('Kennel Map · Husky Tracking Demo');
    document.title = 'Another route';
    window.dispatchEvent(new Event('beforeprint'));
    window.dispatchEvent(new Event('afterprint'));
    expect(document.title).toBe('Another route');
    expect(document.body.classList.contains('ht-kennel-print-open')).toBe(false);
  });

  it('suppresses late focus on context close/destruction and never overwrites a newer route title', async () => {
    await open();
    document.title = 'Dog Profile · Husky Tracking Demo';
    service.close(false);
    await settle();
    expect(document.activeElement).not.toBe(trigger);
    expect(document.title).toBe('Dog Profile · Husky Tracking Demo');
    trigger.focus();
    service.open(projection);
    service.ngOnDestroy();
    const newer = document.createElement('button');
    document.body.append(newer);
    extras.push(newer);
    newer.focus();
    await settle();
    expect(document.activeElement).toBe(newer);
    expect(document.querySelector('ht-kennel-print-preview')).toBeNull();
    expect(document.body.classList.contains('ht-kennel-print-open')).toBe(false);
  });

  it('reopens as one preview and does not compete with an existing application modal', async () => {
    await open();
    service.open({ ...projection, snapshotDate: '2026-03-29' });
    await settle();
    expect(document.querySelectorAll('ht-kennel-print-preview').length).toBe(1);
    expect(document.querySelector('ht-kennel-print-preview')?.textContent).toContain('2026-03-29');
    service.close(false);
    const other = document.createElement('section');
    other.setAttribute('role', 'dialog');
    other.setAttribute('aria-modal', 'true');
    document.body.append(other);
    extras.push(other);
    service.open(projection);
    expect(service.isOpen()).toBe(false);
    expect(document.querySelector('ht-kennel-print-preview')).toBeNull();
  });

  it('shows a controlled print failure without claiming completion or losing the document', async () => {
    vi.spyOn(window, 'print').mockImplementation(() => { throw new Error('test-only unavailable'); });
    const host = await open();
    action(host, 'Print / Save as PDF').click();
    await settle();
    expect(host.querySelector('[role="alert"]')?.textContent).toContain('could not be opened');
    expect(host.isConnected).toBe(true);
    expect(action(host, 'Print / Save as PDF').disabled).toBe(false);
    expect(host.textContent).not.toMatch(/PDF (?:was |is )?saved/i);
  });

  it('recovers missing afterprint only after observed blur/return and inactive print media', async () => {
    let printing = true;
    vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: printing })));
    const nativePrint = vi.spyOn(window, 'print').mockImplementation(() => undefined);
    const host = await open();
    const documentNode = host.querySelector('ht-kennel-print-document');
    window.dispatchEvent(new Event('beforeprint'));
    window.dispatchEvent(new Event('focus'));
    await settle();
    expect(action(host, 'Close').disabled).toBe(true);
    expect(document.title).toContain('2026-03-31');

    window.dispatchEvent(new Event('blur'));
    window.dispatchEvent(new Event('focus'));
    await settle();
    expect(action(host, 'Close').disabled).toBe(true);
    expect(action(host, 'Print / Save as PDF').disabled).toBe(true);

    printing = false;
    window.dispatchEvent(new Event('focus'));
    await settle();
    expect(action(host, 'Close').disabled).toBe(false);
    expect(action(host, 'Print / Save as PDF').disabled).toBe(false);
    expect(document.title).toBe('Kennel Map · Husky Tracking Demo');
    expect(host.textContent).toContain('Returned to print preview');
    expect(host.textContent).not.toMatch(/PDF (?:was |is )?saved/i);
    expect(host.querySelector('ht-kennel-print-document')).toBe(documentNode);
    expect(nativePrint).not.toHaveBeenCalled();
  });

  it('does not use focus or unknown print media alone as evidence that native printing ended', async () => {
    vi.stubGlobal('matchMedia', undefined);
    const host = await open();
    window.dispatchEvent(new Event('beforeprint'));
    window.dispatchEvent(new Event('blur'));
    window.dispatchEvent(new Event('focus'));
    await settle();
    expect(action(host, 'Close').disabled).toBe(true);
    expect(document.title).toContain('2026-03-31');
    window.dispatchEvent(new Event('afterprint'));
    await settle();
    expect(action(host, 'Close').disabled).toBe(false);
    expect(document.title).toBe('Kennel Map · Husky Tracking Demo');
  });

  it('reconciles an already observed native blur/return when synchronous print returns after media ends', async () => {
    let printing = true;
    vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: printing })));
    const nativePrint = vi.spyOn(window, 'print').mockImplementation(() => {
      window.dispatchEvent(new Event('beforeprint'));
      window.dispatchEvent(new Event('blur'));
      window.dispatchEvent(new Event('focus'));
      // The focus event itself was insufficient while the browser rendered print.
      expect(document.title).toContain('2026-03-31');
      printing = false;
    });
    const host = await open();
    action(host, 'Print / Save as PDF').click();
    await settle();
    expect(nativePrint).toHaveBeenCalledTimes(1);
    expect(action(host, 'Close').disabled).toBe(false);
    expect(action(host, 'Print / Save as PDF').disabled).toBe(false);
    expect(document.title).toBe('Kennel Map · Husky Tracking Demo');
    expect(host.textContent).toContain('Returned to print preview');
    expect(host.isConnected).toBe(true);
  });

  it('does not steal another modal focus/title when the native focus-return fallback runs', async () => {
    vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: false })));
    const host = await open();
    window.dispatchEvent(new Event('beforeprint'));
    const other = document.createElement('section');
    other.setAttribute('role', 'dialog');
    other.setAttribute('aria-modal', 'true');
    const currentAction = document.createElement('button');
    other.append(currentAction);
    document.body.append(other);
    extras.push(other);
    currentAction.focus();
    document.title = 'Current modal';
    window.dispatchEvent(new Event('blur'));
    window.dispatchEvent(new Event('focus'));
    await settle();
    expect(document.activeElement).toBe(currentAction);
    expect(document.title).toBe('Current modal');
    expect(host.isConnected).toBe(true);
    expect(action(host, 'Close').disabled).toBe(false);
  });

  it('finishes keyboard printing when media ends after the observed focus return without another focus or afterprint', async () => {
    const media = printMedia(true);
    const nativePrint = vi.spyOn(window, 'print').mockImplementation(() => {
      window.dispatchEvent(new Event('beforeprint'));
      window.dispatchEvent(new Event('afterprint'));
    });
    const host = await open();
    const documentNode = host.querySelector('ht-kennel-print-document');
    window.dispatchEvent(new Event('beforeprint'));
    window.dispatchEvent(new Event('blur'));
    window.dispatchEvent(new Event('focus'));
    await settle();
    expect(action(host, 'Close').disabled).toBe(true);
    expect(document.title).toContain('2026-03-31');

    // This is the only new event: no second window focus, afterprint, or button
    // print() finally exists on this keyboard entry path.
    media.change(false);
    await settle();
    expect(action(host, 'Close').disabled).toBe(false);
    expect(action(host, 'Print / Save as PDF').disabled).toBe(false);
    expect(document.title).toBe('Kennel Map · Husky Tracking Demo');
    expect(host.textContent).toContain('Returned to print preview');
    expect(host.textContent).not.toMatch(/PDF (?:was |is )?saved/i);
    expect(host.querySelector('ht-kennel-print-document')).toBe(documentNode);
    expect(service.isOpen()).toBe(true);
    expect(nativePrint).not.toHaveBeenCalled();

    action(host, 'Print / Save as PDF').click();
    await settle();
    expect(nativePrint).toHaveBeenCalledTimes(1);
    expect(host.querySelector('ht-kennel-print-document')).toBe(documentNode);
    action(host, 'Close').click();
    await settle();
    expect(document.activeElement).toBe(trigger);
  });

  for (const observed of ['neither', 'blur only', 'focus only'] as const) {
    it(`keeps keyboard print locked on media end with ${observed} rather than a completed blur/return`, async () => {
      const media = printMedia(true);
      const host = await open();
      window.dispatchEvent(new Event('beforeprint'));
      if (observed === 'blur only') window.dispatchEvent(new Event('blur'));
      if (observed === 'focus only') window.dispatchEvent(new Event('focus'));
      media.change(false);
      await settle();
      expect(action(host, 'Close').disabled).toBe(true);
      expect(action(host, 'Print / Save as PDF').disabled).toBe(true);
      expect(document.title).toContain('2026-03-31');
      window.dispatchEvent(new Event('afterprint'));
      await settle();
      expect(action(host, 'Close').disabled).toBe(false);
    });
  }

  it('checks current print media and ignores a false event while the query still reports active printing', async () => {
    const media = printMedia(true);
    const host = await open();
    window.dispatchEvent(new Event('beforeprint'));
    window.dispatchEvent(new Event('blur'));
    window.dispatchEvent(new Event('focus'));
    for (const callback of media.listeners) callback({ matches: false } as MediaQueryListEvent);
    await settle();
    expect(action(host, 'Close').disabled).toBe(true);
    media.change(true);
    await settle();
    expect(action(host, 'Close').disabled).toBe(true);
  });

  it('does not steal a newer modal focus/title when a deferred print media change completes the old print', async () => {
    const media = printMedia(true);
    const host = await open();
    window.dispatchEvent(new Event('beforeprint'));
    window.dispatchEvent(new Event('blur'));
    window.dispatchEvent(new Event('focus'));
    const other = document.createElement('section');
    other.setAttribute('role', 'dialog');
    other.setAttribute('aria-modal', 'true');
    const currentAction = document.createElement('button');
    other.append(currentAction);
    document.body.append(other);
    extras.push(other);
    currentAction.focus();
    document.title = 'Newer modal';
    media.change(false);
    await settle();
    expect(action(host, 'Close').disabled).toBe(false);
    expect(document.activeElement).toBe(currentAction);
    expect(document.title).toBe('Newer modal');
    expect(host.isConnected).toBe(true);
  });

  it('removes its media listener on context close and ignores an already queued callback after destruction', async () => {
    const media = printMedia(true);
    const host = await open();
    expect(media.listeners.size).toBe(1);
    expect(media.media.addEventListener.mock.calls[0][0]).toBe('change');
    expect(typeof media.media.addEventListener.mock.calls[0][1]).toBe('function');
    window.dispatchEvent(new Event('beforeprint'));
    window.dispatchEvent(new Event('blur'));
    window.dispatchEvent(new Event('focus'));
    const queued = Array.from(media.listeners)[0];
    service.close(false);
    await settle();
    expect(media.listeners.size).toBe(0);
    expect(media.media.removeEventListener).toHaveBeenCalledWith('change', queued);
    document.title = 'Current route';
    const currentAction = document.createElement('button');
    document.body.append(currentAction);
    extras.push(currentAction);
    currentAction.focus();
    media.change(false);
    queued({ matches: false } as MediaQueryListEvent);
    await settle();
    expect(document.title).toBe('Current route');
    expect(document.activeElement).toBe(currentAction);
    expect(host.isConnected).toBe(false);
    expect(document.body.classList.contains('ht-kennel-print-open')).toBe(false);
    service.open(projection);
    await settle();
    expect(media.listeners.size).toBe(1);
  });
});
