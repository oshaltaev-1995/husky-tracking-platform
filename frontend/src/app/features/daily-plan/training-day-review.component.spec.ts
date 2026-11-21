import { TestBed } from '@angular/core/testing';
import { vi } from 'vitest';

import { TrainingDayProposal } from '../../core/api/daily-plans.models';
import { TrainingDayReviewComponent, TrainingDayReviewPhase } from './training-day-review.component';

const proposal: TrainingDayProposal = {
  date: '2026-03-29', preset_version: 'training-day-v1', available: true, unavailable_reason: null,
  activities: [
    ['09:00:00', '10:00:00'], ['10:30:00', '11:30:00'], ['12:30:00', '13:30:00'], ['14:00:00', '15:00:00'],
  ].map(([start_time, suggested_end_time], index) => ({ sequence: index + 1, start_time, suggested_end_time, title: `Group ${index + 1}`, distance_km: 5 })),
  participants: Array.from({ length: 16 }, (_, index) => ({
    id: `synthetic-${index}`, name: `Synthetic Dog ${index + 1}`, housing_code: 'A1-01',
    dog_class: 'standard', availability: 'available', capabilities: ['lead', 'team'],
  })),
  unique_dogs: 16, planned_participations: 64, planned_dog_km: 320, planned_km_per_dog: 20,
  precondition: 'opaque-test-precondition-never-rendered',
};

describe('TrainingDayReviewComponent', () => {
  let trigger: HTMLButtonElement;

  async function setup() {
    await TestBed.configureTestingModule({ imports: [TrainingDayReviewComponent] }).compileComponents();
    trigger = document.createElement('button');
    trigger.textContent = 'Try a training day';
    document.body.append(trigger);
    trigger.focus();
    const fixture = TestBed.createComponent(TrainingDayReviewComponent);
    document.body.append(fixture.nativeElement);
    fixture.componentRef.setInput('proposal', structuredClone(proposal));
    fixture.componentRef.setInput('phase', 'ready');
    fixture.detectChanges();
    await fixture.whenStable();
    return fixture;
  }

  afterEach(() => {
    trigger?.remove();
    document.body.querySelectorAll('ht-training-day-review, [data-test-other-modal]').forEach((node) => node.remove());
    document.body.classList.remove('dialog-open');
  });

  it('shows the reviewed schedule, repeated pool and planned totals without technical authorization values', async () => {
    const fixture = await setup();
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('Sunday, 29 March 2026');
    for (const range of ['09:00–10:00', '10:30–11:30', '12:30–13:30', '14:00–15:00']) expect(text).toContain(range);
    expect(text).toContain('20 km');
    expect(text).toContain('320 km');
    expect(text).toContain('not 64 different dogs');
    expect(text).toContain('No teams are saved and no actual work is recorded');
    expect(fixture.nativeElement.querySelectorAll('.example-pool li').length).toBe(16);
    expect(text).toContain('Lead · Team');
    expect(text).not.toContain(proposal.precondition);
    expect(text).not.toContain('synthetic-0');
  });

  it('focuses the scrollable review region, contains Tab/Shift+Tab, and restores the trigger on Escape', async () => {
    const fixture = await setup();
    const region = fixture.nativeElement.querySelector('[role="region"]') as HTMLElement;
    const buttons = fixture.nativeElement.querySelectorAll('footer button') as NodeListOf<HTMLButtonElement>;
    expect(document.activeElement).toBe(region);
    buttons[buttons.length - 1].focus();
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true }));
    expect(document.activeElement).toBe(region);
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true, cancelable: true }));
    expect(document.activeElement).toBe(buttons[buttons.length - 1]);
    const closed = vi.fn();
    fixture.componentInstance.closed.subscribe(closed);
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(closed).toHaveBeenCalledTimes(1);
    fixture.destroy();
    await Promise.resolve();
    expect(document.activeElement).toBe(trigger);
    expect(document.body.classList.contains('dialog-open')).toBe(false);
  });

  it('allows only an explicit Apply and keeps Cancel/Escape unavailable while the request is pending', async () => {
    const fixture = await setup();
    const applied = vi.fn(), closed = vi.fn();
    fixture.componentInstance.applied.subscribe(applied);
    fixture.componentInstance.closed.subscribe(closed);
    expect(applied).not.toHaveBeenCalled();
    (fixture.nativeElement.querySelector('footer .primary') as HTMLButtonElement).click();
    expect(applied).toHaveBeenCalledTimes(1);
    fixture.componentRef.setInput('phase', 'applying');
    fixture.detectChanges();
    expect(Array.from(fixture.nativeElement.querySelectorAll('footer button') as NodeListOf<HTMLButtonElement>).every((button) => button.disabled)).toBe(true);
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(closed).not.toHaveBeenCalled();
    const region = fixture.nativeElement.querySelector('[role="region"]') as HTMLElement;
    region.focus();
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true }));
    expect(document.activeElement).toBe(region);
  });

  it('makes unknown outcome explicit and offers a read before a fresh conscious review', async () => {
    const fixture = await setup();
    fixture.componentRef.setInput('phase', 'unknown');
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('The day may already be saved');
    expect(fixture.nativeElement.textContent).not.toContain('nothing was saved');
    expect(fixture.nativeElement.querySelector('footer .primary')).toBeNull();
    expect(fixture.nativeElement.textContent).not.toContain('Review again');
    const checked = vi.fn();
    fixture.componentInstance.checkedCurrentDay.subscribe(checked);
    (fixture.nativeElement.querySelector('footer .secondary') as HTMLButtonElement).click();
    expect(checked).toHaveBeenCalledTimes(1);
    fixture.componentRef.setInput('reconciledEmpty', true);
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('does not prove an earlier request has stopped');
    expect(fixture.nativeElement.textContent).toContain('Review again');
    const feedback = fixture.nativeElement.querySelector('.training-day-feedback') as HTMLElement;
    expect(feedback.querySelector('[role="alert"]')?.textContent).toContain('does not prove an earlier request has stopped');
    expect(fixture.nativeElement.querySelector('.training-day-content').contains(feedback)).toBe(false);
  });

  const feedbackCases: { phase: TrainingDayReviewPhase; role: string; error: string; text: string }[] = [
    { phase: 'applying', role: 'status', error: '', text: 'Creating the four planned activities' },
    { phase: 'reconciling', role: 'status', error: '', text: 'Reading the current day' },
    { phase: 'rejected', role: 'alert', error: 'The proposed date already contains a plan.', text: 'already contains a plan' },
    { phase: 'unknown', role: 'alert', error: '', text: 'The day may already be saved' },
    { phase: 'error', role: 'alert', error: 'Too many training-day requests. Please wait a moment.', text: 'Too many training-day requests' },
  ];
  for (const example of feedbackCases) {
    it(`places ${example.phase} feedback outside the roster scroll area without moving keyboard focus`, async () => {
      const fixture = await setup();
      const content = fixture.nativeElement.querySelector('.training-day-content') as HTMLElement;
      const footer = fixture.nativeElement.querySelector('footer') as HTMLElement;
      content.scrollTop = 400;
      fixture.componentRef.setInput('phase', example.phase);
      fixture.componentRef.setInput('error', example.error);
      fixture.detectChanges();
      const feedback = fixture.nativeElement.querySelector('.training-day-feedback') as HTMLElement;
      expect(feedback).not.toBeNull();
      expect(content.contains(feedback)).toBe(false);
      expect(feedback.parentElement).toBe(footer.parentElement);
      expect(feedback.nextElementSibling).toBe(footer);
      expect(feedback.querySelector(`[role="${example.role}"]`)?.textContent).toContain(example.text);
      expect(content.scrollTop).toBe(400);
      expect(document.activeElement).toBe(content);
    });
  }

  it('shows occupied-day context and a destination action without an Apply control', async () => {
    const fixture = await setup();
    fixture.componentRef.setInput('proposal', { ...proposal, available: false, participants: [], precondition: null, unavailable_reason: 'The proposed date already contains a plan.' });
    fixture.componentRef.setInput('phase', 'unavailable');
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('already contains a plan');
    expect(fixture.nativeElement.textContent).toContain('Open current day');
    expect(fixture.nativeElement.querySelector('footer .primary')).toBeNull();
  });

  it('does not steal focus from a newer modal or remove its body lock', async () => {
    const fixture = await setup();
    const other = document.createElement('section');
    other.dataset['testOtherModal'] = 'true';
    other.setAttribute('role', 'dialog');
    other.setAttribute('aria-modal', 'true');
    const button = document.createElement('button');
    button.textContent = 'New dialog';
    other.append(button);
    document.body.append(other);
    button.focus();
    fixture.destroy();
    await Promise.resolve();
    expect(document.activeElement).toBe(button);
    expect(document.body.classList.contains('dialog-open')).toBe(true);
  });

  it('does not restore old-route focus after context invalidation', async () => {
    const fixture = await setup();
    fixture.componentRef.setInput('returnFocusAllowed', () => false);
    fixture.detectChanges();
    fixture.destroy();
    await Promise.resolve();
    expect(document.activeElement).not.toBe(trigger);
  });
});
