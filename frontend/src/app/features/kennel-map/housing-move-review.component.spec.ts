import { ComponentFixture, TestBed } from '@angular/core/testing';
import { vi } from 'vitest';

import { KennelMapLocation } from '../../core/api/kennel-map.models';
import { HousingMoveReviewComponent } from './housing-move-review.component';

const finalLocation: KennelMapLocation = {
  id: 'PUPPY-A', code: 'PUPPY-A', display_name: 'Puppy building A',
  location_type: 'puppy_area', zone: 'PUPPY', row: 'A', position: 1,
  capacity: 5, is_active: true,
  residents: Array.from({ length: 8 }, (_, index) => ({
    id: `resident-${index}`, name: index === 7 ? 'Aurora With A Long Test Name' : `Puppy ${index + 1}`,
    sex: 'female', is_neutered: false, dog_class: 'puppy', lifecycle: 'active',
    availability: 'available', housing_code: 'PUPPY-A', litter_code: 'T', photo_key: null,
  })),
};

describe('Housing move review', () => {
  let fixture: ComponentFixture<HousingMoveReviewComponent>;
  let trigger: HTMLButtonElement;

  async function setup() {
    trigger = document.createElement('button');
    document.body.append(trigger);
    trigger.focus();
    fixture = TestBed.createComponent(HousingMoveReviewComponent);
    fixture.componentRef.setInput('effectiveDate', '2026-03-31');
    fixture.componentRef.setInput('changes', [{
      dog_id: 'resident-7', dog_name: 'Aurora With A Long Test Name',
      source_code: 'A1-01', destination_code: 'PUPPY-A',
    }]);
    fixture.componentRef.setInput('locations', [finalLocation]);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
  }

  function buttons(): HTMLButtonElement[] {
    return Array.from(fixture.nativeElement.querySelectorAll('.review-dialog button'));
  }

  afterEach(() => {
    fixture?.destroy();
    trigger?.remove();
    document.body.classList.remove('dialog-open');
  });

  it('shows dated changes and every resulting resident above nominal capacity without a write', async () => {
    await setup();
    const confirm = vi.fn();
    fixture.componentInstance.confirmed.subscribe(confirm);
    expect(fixture.nativeElement.querySelector('[role="dialog"]').getAttribute('aria-labelledby')).toBe('housing-review-title');
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('Review housing moves');
    expect(text).toContain('Tuesday, 31 March 2026');
    expect(text).toContain('A1-01');
    expect(text).toContain('PUPPY-A');
    expect(text).toContain('8 residents');
    expect(text).toContain('Nominal capacity 5');
    expect(fixture.nativeElement.querySelectorAll('.resident-roster li').length).toBe(8);
    expect(text).toContain('Aurora With A Long Test Name');
    expect(confirm).not.toHaveBeenCalled();
    const body = fixture.nativeElement.querySelector('.review-body') as HTMLElement;
    expect(body.getAttribute('role')).toBe('region');
    expect(body.getAttribute('aria-label')).toBe('Housing move details and resulting residents');
    expect(body.tabIndex).toBe(0);
    expect(document.activeElement).toBe(body);
  });

  it('cancels without confirming, supports Escape, and restores the original trigger', async () => {
    await setup();
    const cancel = vi.fn();
    const confirm = vi.fn();
    fixture.componentInstance.cancelled.subscribe(cancel);
    fixture.componentInstance.confirmed.subscribe(confirm);
    buttons()[0].click();
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }));
    expect(cancel).toHaveBeenCalledTimes(2);
    expect(confirm).not.toHaveBeenCalled();
    fixture.destroy();
    await Promise.resolve();
    expect(document.activeElement).toBe(trigger);
    expect(document.body.classList.contains('dialog-open')).toBe(false);
  });

  it('includes the scrollable content in the complete modal focus cycle', async () => {
    await setup();
    const [cancel, confirm] = buttons();
    const body = fixture.nativeElement.querySelector('.review-body') as HTMLElement;
    confirm.focus();
    const tab = new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true });
    document.dispatchEvent(tab);
    expect(tab.defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(body);
    const previous = new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true, cancelable: true });
    document.dispatchEvent(previous);
    expect(previous.defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(confirm);
    body.focus();
    const onward = new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true });
    body.dispatchEvent(onward);
    expect(onward.defaultPrevented).toBe(false);
    cancel.focus();
    const backToBody = new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true, cancelable: true });
    cancel.dispatchEvent(backToBody);
    expect(backToBody.defaultPrevented).toBe(false);
  });

  it('leaves native keyboard scrolling available and recovers focus from outside the modal', async () => {
    await setup();
    const body = fixture.nativeElement.querySelector('.review-body') as HTMLElement;
    for (const key of ['PageDown', 'End', 'ArrowDown', 'Home']) {
      const event = new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true });
      body.dispatchEvent(event);
      expect(event.defaultPrevented).toBe(false);
      expect(document.activeElement).toBe(body);
    }
    trigger.focus();
    const tab = new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true });
    trigger.dispatchEvent(tab);
    expect(tab.defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(body);
    trigger.focus();
    const previous = new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true, cancelable: true });
    trigger.dispatchEvent(previous);
    expect(previous.defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(buttons()[1]);
  });

  it('emits once for rapid confirmation and can close while the save continues', async () => {
    await setup();
    const confirm = vi.fn();
    const cancel = vi.fn();
    fixture.componentInstance.confirmed.subscribe(confirm);
    fixture.componentInstance.cancelled.subscribe(cancel);
    buttons()[1].click();
    buttons()[1].click();
    expect(confirm).toHaveBeenCalledTimes(1);
    fixture.componentRef.setInput('saving', true);
    fixture.detectChanges();
    expect(buttons()[1].disabled).toBe(true);
    expect(buttons()[0].disabled).toBe(false);
    expect(buttons()[0].textContent).toContain('Close review');
    expect(fixture.nativeElement.textContent).toContain('The save continues if you close this review.');
    const body = fixture.nativeElement.querySelector('.review-body') as HTMLElement;
    body.focus();
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true, cancelable: true }));
    expect(document.activeElement).toBe(buttons()[0]);
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(cancel).toHaveBeenCalledTimes(1);
    fixture.componentRef.setInput('saving', false);
    fixture.componentRef.setInput('serverError', 'Review this request and try again.');
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="alert"]').textContent).toContain('try again');
    buttons()[1].click();
    expect(confirm).toHaveBeenCalledTimes(2);
  });

  it('cannot confirm an empty draft and does not focus a removed trigger', async () => {
    await setup();
    fixture.componentRef.setInput('changes', []);
    fixture.detectChanges();
    const confirm = vi.fn();
    fixture.componentInstance.confirmed.subscribe(confirm);
    buttons()[1].click();
    expect(confirm).not.toHaveBeenCalled();
    trigger.remove();
    fixture.destroy();
    await Promise.resolve();
    expect(document.activeElement).not.toBe(trigger);
  });
});
