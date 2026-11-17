import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { vi } from 'vitest';

import { KennelMapLocation, KennelMapResident } from '../../core/api/kennel-map.models';
import { KennelLocationCardComponent } from './kennel-location-card.component';

const resident: KennelMapResident = {
  id: '9422673b-331b-5e72-a700-5fff0574a209', name: 'Aurora', sex: 'female',
  is_neutered: true, dog_class: 'standard', lifecycle: 'active', availability: 'injured',
  housing_code: 'A1-01', litter_code: null, photo_key: null,
};
const location: KennelMapLocation = {
  id: 'A1-01', code: 'A1-01', display_name: 'A1 enclosure 1',
  location_type: 'adult_enclosure', zone: 'A', row: '1', position: 1,
  capacity: 2, is_active: true, residents: [resident],
};

describe('Housing map interactions', () => {
  let fixture: ComponentFixture<KennelLocationCardComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ providers: [provideRouter([])] }).compileComponents();
    fixture = TestBed.createComponent(KennelLocationCardComponent);
    fixture.componentRef.setInput('location', location);
    fixture.componentRef.setInput('layer', 'default');
    fixture.detectChanges();
  });

  function drag(type: string, mime = 'application/x-husky-dog'): Event {
    const event = new Event(type, { bubbles: true, cancelable: true });
    Object.defineProperty(event, 'dataTransfer', { value: {
      types: [mime], getData: () => resident.id, setData: vi.fn(), effectAllowed: '', dropEffect: '',
    } });
    return event;
  }

  it('keeps the profile link in View and selects the same uniquely identified resident in Move', () => {
    expect(fixture.nativeElement.querySelector('a.resident-dog').getAttribute('href')).toBe(`/demo/dogs/${resident.id}`);
    const selected = vi.fn();
    fixture.componentInstance.dogSelected.subscribe(selected);
    fixture.componentRef.setInput('moveMode', true);
    fixture.componentRef.setInput('selectedDogId', resident.id);
    fixture.componentRef.setInput('pendingDogIds', new Set([resident.id]));
    fixture.componentRef.setInput('affectedLocationCodes', new Set(['A1-01']));
    fixture.detectChanges();
    const button = fixture.nativeElement.querySelector('button.resident-dog') as HTMLButtonElement;
    expect(button.id).toBe(`map-dog-${resident.id}`);
    expect(button.getAttribute('aria-pressed')).toBe('true');
    expect(fixture.nativeElement.querySelectorAll(`[id="map-dog-${resident.id}"]`).length).toBe(1);
    expect(fixture.nativeElement.querySelector('a.resident-dog')).toBeNull();
    expect(fixture.nativeElement.textContent).toContain('Pending move');
    expect(fixture.nativeElement.textContent).toContain('Pending changes');
    button.click();
    expect(selected).toHaveBeenCalledWith(resident.id);
  });

  it('only emits a native drop in enabled Move mode with the dedicated dog MIME', () => {
    const dropped = vi.fn();
    fixture.componentInstance.dogDropped.subscribe(dropped);
    const article = fixture.nativeElement.querySelector('article') as HTMLElement;
    article.dispatchEvent(drag('drop'));
    expect(dropped).not.toHaveBeenCalled();
    fixture.componentRef.setInput('moveMode', true);
    fixture.detectChanges();
    article.dispatchEvent(drag('drop', 'text/plain'));
    expect(dropped).not.toHaveBeenCalled();
    const over = drag('dragover');
    article.dispatchEvent(over);
    fixture.detectChanges();
    expect(over.defaultPrevented).toBe(true);
    expect(article.classList.contains('drop-active')).toBe(true);
    article.dispatchEvent(drag('drop'));
    expect(dropped).toHaveBeenCalledTimes(1);
    expect(dropped).toHaveBeenCalledWith({ dogId: resident.id, destinationCode: 'A1-01' });
    fixture.componentRef.setInput('interactionsDisabled', true);
    fixture.detectChanges();
    article.dispatchEvent(drag('drop'));
    expect(dropped).toHaveBeenCalledTimes(1);
    expect(article.classList.contains('drop-active')).toBe(false);
    expect((fixture.nativeElement.querySelector('button.resident-dog') as HTMLButtonElement).disabled).toBe(true);
  });

  it('emits no drop for cancelled drag and uses dedicated UUID data for a dog drag', () => {
    fixture.componentRef.setInput('moveMode', true);
    fixture.detectChanges();
    const button = fixture.nativeElement.querySelector('button.resident-dog') as HTMLButtonElement;
    const dropped = vi.fn();
    fixture.componentInstance.dogDropped.subscribe(dropped);
    const start = drag('dragstart');
    button.dispatchEvent(start);
    const data = (start as DragEvent).dataTransfer!;
    expect(data.setData).toHaveBeenCalledWith('application/x-husky-dog', resident.id);
    fixture.detectChanges();
    expect(button.classList.contains('dragging')).toBe(true);
    button.dispatchEvent(drag('dragend'));
    fixture.detectChanges();
    expect(button.classList.contains('dragging')).toBe(false);
    expect(dropped).not.toHaveBeenCalled();
  });
});
