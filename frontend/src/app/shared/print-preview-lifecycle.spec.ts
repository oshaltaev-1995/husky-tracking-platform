import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { vi } from 'vitest';

import { PrintPreviewLifecycle } from './print-preview-lifecycle';

@Component({
  selector: 'ht-delayed-print-test',
  template: `
    <section role="dialog" aria-modal="true" aria-label="Test print preview">
      <div #paper tabindex="0" role="region" aria-label="Test document">Readable document</div>
      @if (printError()) { <p role="alert">{{ printError() }}</p> }
      <button type="button" (click)="close()">Close</button>
      <button type="button" [disabled]="!ready() || requestingPrint() || nativePrinting()" (click)="print()">Print</button>
    </section>
  `,
})
class DelayedPrintTestComponent extends PrintPreviewLifecycle {
  preparation: Promise<void> | undefined;

  protected override printDocumentTitle(): string {
    return 'Test document';
  }

  protected override prepareContent(): void | Promise<void> {
    return this.preparation;
  }
}

describe('Shared print preview content readiness', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('keeps the document keyboard-readable while media preparation blocks only Print', async () => {
    let resolve!: () => void;
    const fixture = TestBed.createComponent(DelayedPrintTestComponent);
    fixture.componentInstance.preparation = new Promise<void>((done) => { resolve = done; });
    document.body.append(fixture.nativeElement);
    fixture.detectChanges();
    await Promise.resolve();
    fixture.detectChanges();
    const region = fixture.nativeElement.querySelector('[role="region"]') as HTMLElement;
    const buttons = fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>;
    expect(document.activeElement).toBe(region);
    expect(buttons[0].disabled).toBe(false);
    expect(buttons[1].disabled).toBe(true);
    buttons[0].focus();
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true }));
    expect(document.activeElement).toBe(region);
    resolve();
    await Promise.resolve();
    fixture.detectChanges();
    expect(buttons[1].disabled).toBe(false);
    fixture.destroy();
    fixture.nativeElement.remove();
  });

  it('ignores deferred preparation completion after context destruction', async () => {
    let resolve!: () => void;
    const fixture = TestBed.createComponent(DelayedPrintTestComponent);
    fixture.componentInstance.preparation = new Promise<void>((done) => { resolve = done; });
    document.body.append(fixture.nativeElement);
    fixture.detectChanges();
    await Promise.resolve();
    fixture.destroy();
    fixture.nativeElement.remove();
    const current = document.createElement('button');
    document.body.append(current);
    current.focus();
    const title = document.title;
    resolve();
    await Promise.resolve();
    expect(document.activeElement).toBe(current);
    expect(document.title).toBe(title);
    current.remove();
  });

  it('reports preparation failure safely and leaves Close usable without opening native print', async () => {
    const nativePrint = vi.spyOn(window, 'print').mockImplementation(() => undefined);
    let reject!: () => void;
    const fixture = TestBed.createComponent(DelayedPrintTestComponent);
    fixture.componentInstance.preparation = new Promise<void>((_resolve, fail) => { reject = fail; });
    document.body.append(fixture.nativeElement);
    fixture.detectChanges();
    await Promise.resolve();
    reject();
    await Promise.resolve();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="alert"]').textContent).toContain('could not be prepared');
    const buttons = fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>;
    expect(buttons[1].disabled).toBe(true);
    expect(buttons[0].disabled).toBe(false);
    const closed = vi.fn();
    fixture.componentInstance.closed.subscribe(closed);
    buttons[0].click();
    expect(closed).toHaveBeenCalledTimes(1);
    expect(nativePrint).not.toHaveBeenCalled();
    fixture.destroy();
    fixture.nativeElement.remove();
  });
});
