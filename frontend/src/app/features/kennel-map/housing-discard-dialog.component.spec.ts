import { ComponentFixture, TestBed } from '@angular/core/testing';
import { vi } from 'vitest';

import { HousingDiscardDialogComponent } from './housing-discard-dialog.component';

describe('Housing discard dialog focus', () => {
  let fixture: ComponentFixture<HousingDiscardDialogComponent>;
  let trigger: HTMLButtonElement;
  const extraElements: HTMLElement[] = [];

  async function setup(): Promise<void> {
    trigger = document.createElement('button');
    trigger.textContent = 'Done moving';
    document.body.append(trigger);
    trigger.focus();
    fixture = TestBed.createComponent(HousingDiscardDialogComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
  }

  function buttons(): HTMLButtonElement[] {
    return Array.from(fixture.nativeElement.querySelectorAll('button'));
  }

  function keydown(key: string, shiftKey = false): KeyboardEvent {
    const event = new KeyboardEvent('keydown', { key, shiftKey, bubbles: true, cancelable: true });
    document.dispatchEvent(event);
    return event;
  }

  function externalButton(): HTMLButtonElement {
    const button = document.createElement('button');
    button.textContent = 'Reload housing';
    document.body.append(button);
    extraElements.push(button);
    return button;
  }

  afterEach(() => {
    fixture?.destroy();
    trigger?.remove();
    for (const element of extraElements.splice(0)) element.remove();
    document.body.classList.remove('dialog-open');
  });

  it('starts on Keep editing and emits no choice just because it opened', async () => {
    await setup();
    const decided = vi.fn();
    fixture.componentInstance.decided.subscribe(decided);
    const dialog = fixture.nativeElement.querySelector('[role="dialog"]');
    expect(dialog.getAttribute('aria-modal')).toBe('true');
    expect(dialog.getAttribute('aria-labelledby')).toBe('housing-discard-title');
    expect(document.activeElement).toBe(buttons()[0]);
    expect(buttons()[0].textContent).toContain('Keep editing');
    expect(document.body.classList.contains('dialog-open')).toBe(true);
    expect(decided).not.toHaveBeenCalled();
  });

  it('wraps both ends of the actual focusable targets and skips a disabled action', async () => {
    await setup();
    const [keep, discard] = buttons();
    discard.focus();
    expect(keydown('Tab').defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(keep);
    expect(keydown('Tab', true).defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(discard);
    discard.disabled = true;
    keep.focus();
    expect(keydown('Tab').defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(keep);
    expect(keydown('Tab', true).defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(keep);
  });

  it('contains unexpected outside focus so Keep editing cannot activate Reload housing', async () => {
    await setup();
    const reload = externalButton();
    const reloaded = vi.fn();
    reload.addEventListener('click', reloaded);
    const decided = vi.fn();
    fixture.componentInstance.decided.subscribe(decided);
    reload.focus();
    expect(document.activeElement).toBe(buttons()[0]);
    expect(keydown('Tab', true).defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(buttons()[1]);
    expect(keydown('Tab').defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(buttons()[0]);
    // jsdom does not synthesize a button's native Enter activation; click the
    // observed focused control. The built-browser scenario covers real Enter.
    (document.activeElement as HTMLButtonElement).click();
    expect(decided).toHaveBeenCalledTimes(1);
    expect(decided).toHaveBeenCalledWith(false);
    expect(reloaded).not.toHaveBeenCalled();
  });

  it('recovers Tab and Shift+Tab from a non-focusable point within the modal', async () => {
    await setup();
    const heading = fixture.nativeElement.querySelector('h2') as HTMLElement;
    heading.tabIndex = -1;
    heading.focus();
    expect(keydown('Tab').defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(buttons()[0]);
    heading.focus();
    expect(keydown('Tab', true).defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(buttons()[1]);
  });

  it('Escape and the explicit actions keep their distinct choices', async () => {
    await setup();
    const decided = vi.fn();
    fixture.componentInstance.decided.subscribe(decided);
    expect(keydown('Escape').defaultPrevented).toBe(true);
    buttons()[0].click();
    buttons()[1].click();
    expect(decided.mock.calls).toEqual([[false], [false], [true]]);
  });

  it('restores a connected enabled trigger after ordinary dismissal', async () => {
    await setup();
    fixture.destroy();
    await Promise.resolve();
    expect(document.activeElement).toBe(trigger);
    expect(document.body.classList.contains('dialog-open')).toBe(false);
  });

  it('does not restore a disabled or removed trigger', async () => {
    await setup();
    trigger.disabled = true;
    fixture.destroy();
    await Promise.resolve();
    expect(document.activeElement).not.toBe(trigger);
    trigger.remove();
  });

  it('does not steal focus or clear another active modal on teardown', async () => {
    await setup();
    const newerModal = document.createElement('section');
    newerModal.setAttribute('role', 'dialog');
    newerModal.setAttribute('aria-modal', 'true');
    const action = document.createElement('button');
    newerModal.append(action);
    document.body.append(newerModal);
    extraElements.push(newerModal);
    action.focus();
    expect(document.activeElement).toBe(action);
    fixture.destroy();
    await Promise.resolve();
    expect(document.activeElement).toBe(action);
    expect(document.body.classList.contains('dialog-open')).toBe(true);
  });

  it('does not override a deliberate focus change after its destruction', async () => {
    await setup();
    const reload = externalButton();
    fixture.destroy();
    reload.focus();
    await Promise.resolve();
    expect(document.activeElement).toBe(reload);
  });

  it('cancels queued autofocus when destroyed before it can run', async () => {
    trigger = document.createElement('button');
    document.body.append(trigger);
    trigger.focus();
    fixture = TestBed.createComponent(HousingDiscardDialogComponent);
    fixture.detectChanges();
    const keep = buttons()[0];
    const focus = vi.spyOn(keep, 'focus');
    fixture.destroy();
    await Promise.resolve();
    expect(focus).not.toHaveBeenCalled();
  });
});
