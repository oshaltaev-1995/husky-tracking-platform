import { TestBed } from '@angular/core/testing';

import { KennelPrintDocumentComponent } from './kennel-print-document.component';
import { projectKennelPrint } from './kennel-print-projection';
import { printSnapshot } from './kennel-print-test-data';

describe('Kennel map print document', () => {
  it('keeps the Ground zone/row/path/puppy composition rather than stacking full-width rosters', () => {
    const fixture = TestBed.createComponent(KennelPrintDocumentComponent);
    fixture.componentRef.setInput('projection', projectKennelPrint(printSnapshot(), 'gender'));
    fixture.detectChanges();
    const document = fixture.nativeElement as HTMLElement;
    const grounds = document.querySelector('.print-adult-grounds')!;
    expect(Array.from(grounds.children).map((child) => child.getAttribute('data-print-zone') ?? child.textContent?.trim())).toEqual(['A', 'Main path', 'B']);
    expect(Array.from(grounds.querySelectorAll('[data-print-row]')).map((row) => row.getAttribute('data-print-row'))).toEqual(['A1','A2','B1','B2']);
    expect(document.querySelectorAll('.print-service-aisle').length).toBe(2);
    expect(Array.from(document.querySelector('.print-buildings')!.querySelectorAll('[data-print-location]')).map((location) => location.getAttribute('data-print-location'))).toEqual(['PUPPY-A','PUPPY-B']);
    expect(document.querySelector('.print-legend [data-tone="female"]')?.textContent).toContain('Female');
    expect(document.querySelector('.printed-resident')?.getAttribute('data-tone')).toBe('female');
  });
  it('renders one noninteractive text roster for every location without session metadata or dog IDs', () => {
    const snapshot = printSnapshot();
    const fixture = TestBed.createComponent(KennelPrintDocumentComponent);
    fixture.componentRef.setInput('projection', projectKennelPrint(snapshot, 'default'));
    fixture.detectChanges();
    const document = fixture.nativeElement as HTMLElement;
    expect(document.textContent).toContain('31 March 2026');
    expect(document.textContent).toContain('50 residents');
    expect(document.querySelectorAll('[data-print-location]').length).toBe(22);
    expect(document.querySelectorAll('.printed-resident').length).toBe(50);
    for (const location of snapshot.locations) {
      const printed = Array.from(document.querySelectorAll(`[data-print-roster="${location.code}"] .printed-resident > strong`))
        .map((name) => name.textContent);
      expect(printed).toEqual(location.residents.map((dog) => dog.name));
    }
    expect(document.querySelectorAll('a, button, input, select, [id], [draggable]').length).toBe(0);
    expect(document.innerHTML).not.toContain(snapshot.locations[0].residents[0].id);
    expect(document.innerHTML).not.toContain('test-only-edit-context');
    expect(document.textContent).not.toContain('revision');
    expect(document.textContent).toContain('Fictional demo data');
  });

  it('keeps spatial empty locations and each crowded resident once across explicit continuations', () => {
    const snapshot = printSnapshot();
    const allDogs = snapshot.locations.flatMap((location) => location.residents);
    snapshot.locations.forEach((location) => location.residents = []);
    snapshot.locations[0].residents = allDogs;
    const fixture = TestBed.createComponent(KennelPrintDocumentComponent);
    fixture.componentRef.setInput('projection', projectKennelPrint(snapshot, 'class'));
    fixture.detectChanges();
    const document = fixture.nativeElement as HTMLElement;
    expect(document.querySelectorAll('[data-print-location]').length).toBe(22);
    expect(document.querySelectorAll('.printed-resident').length).toBe(50);
    expect(document.querySelectorAll('[data-print-roster="A1-01"] .printed-resident').length).toBe(50);
    expect(document.querySelectorAll('.print-empty').length).toBe(21);
    const table = document.querySelector('[data-print-continuation="A1-01"]')!;
    expect(table.querySelector('thead')?.textContent).toContain('A1-01');
    expect(table.querySelector('thead')?.textContent).toContain('Continued residents');
    expect(document.querySelector('[data-print-location="A1-01"]')?.textContent).toContain('Roster continues');
    const names = Array.from(document.querySelectorAll('.printed-resident > strong')).map((name) => name.textContent);
    expect(new Set(names).size).toBe(50);
    expect(document.textContent).not.toContain('+N');
  });

  it('renders long names and source strings as ordinary selectable escaped text', () => {
    const snapshot = printSnapshot();
    const name = '<script>fictional name & text</script> ' + 'Long synthetic dog name '.repeat(8);
    snapshot.locations[0].residents[0].name = name;
    const projection = projectKennelPrint(snapshot, 'gender');
    snapshot.locations[0].residents[0].name = 'Later live change';
    const fixture = TestBed.createComponent(KennelPrintDocumentComponent);
    fixture.componentRef.setInput('projection', projection);
    fixture.detectChanges();
    const document = fixture.nativeElement as HTMLElement;
    expect(Array.from(document.querySelectorAll('.printed-resident > strong')).some((element) => element.textContent === name)).toBe(true);
    expect(document.querySelectorAll('script').length).toBe(0);
    expect(document.textContent).not.toContain('Later live change');
    expect(document.textContent).toContain('Female');
  });
});
