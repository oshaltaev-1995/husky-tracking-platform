import { TestBed } from '@angular/core/testing';

import { KennelPrintDocumentComponent } from './kennel-print-document.component';
import { projectKennelPrint } from './kennel-print-projection';
import { printSnapshot } from './kennel-print-test-data';

describe('Kennel map print document', () => {
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

  it('renders empty sources and complete crowded rosters as native continuation-capable table rows', () => {
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
    const firstTable = document.querySelector('.housing-row')!;
    expect(firstTable.querySelectorAll('thead th').length).toBe(5);
    expect(firstTable.querySelectorAll('tbody tr').length).toBe(50);
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
    expect(document.querySelector('.printed-resident > strong')?.textContent).toBe(name);
    expect(document.querySelectorAll('script').length).toBe(0);
    expect(document.textContent).not.toContain('Later live change');
    expect(document.textContent).toContain('Female');
  });
});
