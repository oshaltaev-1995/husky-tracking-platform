import { ApplicationRef } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { vi } from 'vitest';

import { DogSummaryDocumentComponent } from './dog-summary-document.component';
import { DogSummaryPrintService } from './dog-summary-print.service';
import { DogSummaryProjection } from './dog-summary-projection';

const projection: DogSummaryProjection = {
  name: 'Atlas', snapshotDate: '2026-03-31', photoKey: null,
  birthDate: '2016-02-01', ageLabel: '10 years, 1 month', sex: 'Male',
  neuterLabel: 'Intact', neuteredOn: null, litterCode: null, litterBirthDate: null,
  lifecycle: 'Active', operationalClass: 'Standard', classIsHistorical: false,
  availability: 'Available', capabilities: ['Lead', 'Team', 'Wheel'],
  housing: { label: 'Current housing', code: 'A1-01', displayName: 'Adult enclosure A1-01' },
  archive: null,
  pedigree: {
    mother: null, father: null, maternalGrandmother: null, maternalGrandfather: null,
    paternalGrandmother: null, paternalGrandfather: null, littermates: 0, offspring: 0,
  },
  work: {
    seasonStart: '2025-12-01', seasonEnd: '2026-03-31', totalKm: 100, starts: 10,
    starts5km: 0, starts10km: 10, averageKmPerStart: 10, lastWorkDate: '2026-03-28',
  },
  history: [{ date: '2025-12-01', kind: 'Housing', value: 'A1-01' }],
  workspaceHousing: null, notes: null,
};

describe('Dog Summary preview lifecycle and context ownership', () => {
  let service: DogSummaryPrintService;
  let trigger: HTMLButtonElement;
  let originalTitle: string;
  const extras: HTMLElement[] = [];

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [DogSummaryPrintService] });
    service = TestBed.inject(DogSummaryPrintService);
    vi.spyOn(DogSummaryDocumentComponent.prototype, 'whenMediaReady').mockResolvedValue();
    originalTitle = document.title;
    document.title = 'Atlas · Husky Tracking Demo';
    trigger = document.createElement('button');
    trigger.textContent = 'Print summary';
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

  async function open(value = projection): Promise<HTMLElement> {
    service.open(value);
    await settle();
    const host = document.querySelector<HTMLElement>('ht-dog-summary-preview');
    expect(host).not.toBeNull();
    return host!;
  }

  function action(host: HTMLElement, label: string): HTMLButtonElement {
    const button = Array.from(host.querySelectorAll<HTMLButtonElement>('button'))
      .find((candidate) => candidate.textContent.trim() === label);
    if (!button) throw new Error(`Missing Dog Summary action: ${label}`);
    return button;
  }

  it('opens one named portrait document without HTTP providers or automatic printing and restores its trigger', async () => {
    const nativePrint = vi.spyOn(window, 'print').mockImplementation(() => undefined);
    const viewsBefore = TestBed.inject(ApplicationRef).viewCount;
    const host = await open();
    expect(service.isOpen()).toBe(true);
    expect(host.parentElement).toBe(document.body);
    expect(document.body.classList.contains('ht-dog-summary-open')).toBe(true);
    expect(document.body.classList.contains('ht-kennel-print-open')).toBe(false);
    const dialog = host.querySelector('[role="dialog"]')!;
    expect(dialog.getAttribute('aria-labelledby')).toBe('dog-summary-preview-title');
    expect(dialog.getAttribute('aria-describedby')).toBe('dog-summary-preview-description');
    expect(host.querySelector('#dog-summary-preview-description')?.textContent).toContain('A4 portrait');
    const paper = host.querySelector<HTMLElement>('[role="region"]')!;
    expect(document.activeElement).toBe(paper);
    expect(paper.tabIndex).toBe(0);
    expect(host.querySelectorAll('ht-dog-summary-document').length).toBe(1);
    expect(host.textContent).toContain('Atlas');
    expect(nativePrint).not.toHaveBeenCalled();
    expect(document.title).toBe('Atlas · Husky Tracking Demo');
    action(host, 'Close').click();
    await settle();
    expect(document.activeElement).toBe(trigger);
    expect(TestBed.inject(ApplicationRef).viewCount).toBe(viewsBefore);
    expect(document.body.classList.contains('ht-dog-summary-open')).toBe(false);
    expect(document.querySelector('ht-dog-summary-preview')).toBeNull();
    window.dispatchEvent(new Event('beforeprint'));
    window.dispatchEvent(new Event('afterprint'));
    expect(document.title).toBe('Atlas · Husky Tracking Demo');
  });

  it('waits for portrait readiness while keeping the paper and Close keyboard-accessible, then enables Print', async () => {
    let resolve!: () => void;
    vi.mocked(DogSummaryDocumentComponent.prototype.whenMediaReady)
      .mockReturnValue(new Promise<void>((done) => { resolve = done; }));
    const host = await open();
    const paper = host.querySelector<HTMLElement>('[role="region"]')!;
    expect(action(host, 'Print / Save as PDF').disabled).toBe(true);
    expect(action(host, 'Close').disabled).toBe(false);
    action(host, 'Close').focus();
    const tab = new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true });
    document.dispatchEvent(tab);
    expect(tab.defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(paper);
    resolve();
    await settle();
    expect(action(host, 'Print / Save as PDF').disabled).toBe(false);
  });

  it('does not let late portrait completion or a stale close restore an old dog context', async () => {
    let resolveOld!: () => void;
    vi.mocked(DogSummaryDocumentComponent.prototype.whenMediaReady)
      .mockReturnValueOnce(new Promise<void>((done) => { resolveOld = done; }));
    const oldHost = await open();
    service.close(true);
    const newHost = await open({ ...projection, name: 'Nova' });
    const paper = newHost.querySelector<HTMLElement>('[role="region"]')!;
    resolveOld();
    await settle();
    expect(oldHost.isConnected).toBe(false);
    expect(document.querySelectorAll('ht-dog-summary-preview').length).toBe(1);
    expect(newHost.textContent).toContain('Nova');
    expect(newHost.textContent).not.toContain('Atlas');
    expect(document.activeElement).toBe(paper);
    expect(action(newHost, 'Print / Save as PDF').disabled).toBe(false);
    expect(document.title).toBe('Atlas · Husky Tracking Demo');
  });

  it('uses the accepted dated dog title only during native print and retains one document after Cancel/repeat', async () => {
    const nativePrint = vi.spyOn(window, 'print').mockImplementation(() => {
      expect(document.title).toBe('Husky Tracking · Dog Summary · Atlas · 2026-03-31');
      window.dispatchEvent(new Event('beforeprint'));
      window.dispatchEvent(new Event('afterprint'));
    });
    const host = await open();
    const paper = host.querySelector('ht-dog-summary-document');
    action(host, 'Print / Save as PDF').click();
    await settle();
    expect(document.title).toBe('Atlas · Husky Tracking Demo');
    expect(host.textContent).toContain('Print dialog closed');
    expect(host.textContent).not.toMatch(/PDF (?:was |is )?saved|successfully saved/i);
    action(host, 'Print / Save as PDF').click();
    await settle();
    expect(nativePrint).toHaveBeenCalledTimes(2);
    expect(host.querySelector('ht-dog-summary-document')).toBe(paper);
    const escape = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true });
    document.dispatchEvent(escape);
    await settle();
    expect(escape.defaultPrevented).toBe(true);
    expect(service.isOpen()).toBe(false);
    expect(document.activeElement).toBe(trigger);
  });

  it('shows a preparation error without claiming success, then permits close and a clean reopen', async () => {
    let reject!: () => void;
    vi.mocked(DogSummaryDocumentComponent.prototype.whenMediaReady)
      .mockReturnValueOnce(new Promise<void>((_resolve, fail) => { reject = fail; }));
    const nativePrint = vi.spyOn(window, 'print').mockImplementation(() => undefined);
    const host = await open();
    reject();
    await settle();
    expect(host.querySelector('[role="alert"]')?.textContent).toContain('could not be prepared');
    expect(action(host, 'Print / Save as PDF').disabled).toBe(true);
    expect(action(host, 'Close').disabled).toBe(false);
    expect(nativePrint).not.toHaveBeenCalled();
    action(host, 'Close').click();
    await settle();
    const reopened = await open();
    expect(action(reopened, 'Print / Save as PDF').disabled).toBe(false);
    expect(reopened.querySelector('[role="alert"]')).toBeNull();
  });

  it('does not overwrite a newer route title or steal focus from another modal during destruction', async () => {
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
    document.title = 'Newer route';
    service.close(true);
    await settle();
    expect(host.isConnected).toBe(false);
    expect(document.title).toBe('Newer route');
    expect(document.activeElement).toBe(currentAction);
    expect(document.body.classList.contains('ht-dog-summary-open')).toBe(false);
    service.open(projection);
    expect(service.isOpen()).toBe(false);
    expect(document.querySelector('ht-dog-summary-preview')).toBeNull();
  });
});
