import { vi } from 'vitest';
import { TestBed } from '@angular/core/testing';

import { DogSummaryDocumentComponent } from './dog-summary-document.component';
import { DogSummaryProjection } from './dog-summary-projection';

const summary: DogSummaryProjection = {
  name: 'Test northern dog', snapshotDate: '2026-03-31', photoKey: null,
  birthDate: '2024-01-15', ageLabel: '2 years, 2 months', sex: 'Female',
  neuterLabel: 'Neutered / spayed', neuteredOn: '2025-10-12',
  litterCode: 'N', litterBirthDate: '2024-01-15', lifecycle: 'Active',
  operationalClass: 'Standard', classIsHistorical: false, availability: 'Available',
  capabilities: ['Lead', 'Team'],
  housing: { label: 'Current housing', code: 'A1-02', displayName: 'A1 enclosure 2' },
  archive: null,
  pedigree: {
    mother: 'Northern mother', father: 'Northern father',
    maternalGrandmother: 'Maternal grandmother name', maternalGrandfather: 'Maternal grandfather name',
    paternalGrandmother: 'Paternal grandmother name', paternalGrandfather: 'Paternal grandfather name',
    littermates: 3, offspring: 2,
  },
  work: {
    seasonStart: '2025-12-01', seasonEnd: '2026-03-31', totalKm: 75,
    starts: 9, starts5km: 3, starts10km: 6, averageKmPerStart: 8.33,
    lastWorkDate: '2026-03-24',
  },
  history: [{ date: '2026-02-01', kind: 'Class', value: 'Standard' }],
  workspaceHousing: null,
  notes: { text: 'A fictional note for this dog.', shortened: false },
};

function render(projection: DogSummaryProjection = summary) {
  const fixture = TestBed.createComponent(DogSummaryDocumentComponent);
  fixture.componentRef.setInput('projection', projection);
  fixture.detectChanges();
  return fixture.nativeElement as HTMLElement;
}

describe('Dog Summary document', () => {
  it('renders the dog’s complete identity, both pedigree lines and actual-work values without controls', () => {
    const element = render();
    expect(element.querySelector('h1')?.textContent).toBe(summary.name);
    expect(element.textContent).toContain('31 March 2026');
    expect(element.textContent).toContain('15 Jan 2024');
    expect(element.textContent).toContain('2 years, 2 months');
    expect(element.textContent).toContain('Neutered / spayed');
    expect(element.textContent).toContain('12 Oct 2025');
    expect(element.textContent).toContain('N-litter');
    expect(element.textContent).toContain('Current housing');
    expect(element.textContent).toContain('A1-02');
    expect(element.textContent).toContain('Lead · Team');
    for (const name of [summary.pedigree.mother, summary.pedigree.father, summary.pedigree.maternalGrandmother,
      summary.pedigree.maternalGrandfather, summary.pedigree.paternalGrandmother, summary.pedigree.paternalGrandfather]) {
      expect(element.textContent).toContain(name);
    }
    const work = element.querySelector('[aria-label="Actual work"]')!;
    expect(work.textContent).toContain('1 Dec 2025 – 31 Mar 2026');
    expect(work.querySelector('.distance dd')?.textContent).toBe('75 km');
    expect(work.querySelector('.starts dd')?.textContent).toBe('9');
    expect(work.textContent).toContain('8.33');
    expect(work.textContent).toContain('24 Mar 2026');
    expect(element.querySelectorAll('button, a, input, select, canvas').length).toBe(0);
    expect(element.textContent).toContain('Fictional demo data');
  });

  it('labels archived historical class, last housing and temporary housing separately from canonical changes', () => {
    const element = render({ ...summary,
      lifecycle: 'Archived', availability: null, classIsHistorical: true,
      housing: { label: 'Last known housing', code: 'B1-03', displayName: 'B1 enclosure 3' },
      archive: { date: '2026-02-15', reason: 'Rehomed to guide' },
      workspaceHousing: { date: '2026-03-31', code: 'A2-02', displayName: 'A2 enclosure 2' },
    });
    expect(element.textContent).toContain('Last assigned class');
    expect(element.textContent).toContain('Last known housing');
    expect(element.querySelector('.archive-record')?.textContent).toContain('Archived 15 Feb 2026');
    expect(element.querySelector('.archive-record')?.textContent).toContain('Rehomed to guide');
    expect(element.querySelector('.workspace-record')?.textContent).toContain('Temporary demo housing');
    expect(element.querySelector('.history-list')?.textContent).not.toContain('A2-02');
  });

  it('keeps zero work, missing averages/dates, missing relationships and missing portrait neutral', () => {
    const element = render({ ...summary, photoKey: null, capabilities: [], housing: null,
      pedigree: { mother: null, father: null, maternalGrandmother: null, maternalGrandfather: null,
        paternalGrandmother: null, paternalGrandfather: null, littermates: 0, offspring: 0 },
      work: { ...summary.work, totalKm: 0, starts: 0, starts5km: 0, starts10km: 0,
        averageKmPerStart: null, lastWorkDate: null },
      history: [], notes: null,
    });
    expect(element.querySelector('.distance dd')?.textContent).toBe('0 km');
    expect(element.querySelector('.starts dd')?.textContent).toBe('0');
    expect(element.querySelector('.empty-work')?.textContent).toContain('0 starts');
    expect(Array.from(element.querySelectorAll('.family-line dd')).every((value) => value.textContent === 'Not recorded')).toBe(true);
    expect(element.querySelector('[aria-label="Actual work"]')?.textContent?.match(/Not recorded/g)?.length).toBe(2);
    expect(element.querySelector('ht-dog-media img')).toBeNull();
    expect(element.querySelector('ht-dog-media [role="img"]')?.getAttribute('aria-label')).toBe(`Portrait of ${summary.name}`);
    expect(element.textContent).toContain('None recorded');
    expect(element.textContent).toContain('No dated changes recorded.');
  });

  it('preserves full names and renders a clearly bounded note as ordinary escaped text', () => {
    const name = '<script>full fictional name & surname</script> ' + 'Northern '.repeat(8);
    const note = '<img src=x onerror=alert(1)> Fictional shortened note…';
    const element = render({ ...summary, name, notes: { text: note, shortened: true } });
    expect(element.querySelector('h1')?.textContent).toBe(name);
    expect(element.querySelector('.notes')?.textContent).toBe(note);
    expect(element.querySelector('.note-disclosure')?.textContent).toContain('Shortened for this summary');
    expect(element.querySelectorAll('script, .notes img').length).toBe(0);
  });

  it('formats supplied calendar days without using the machine date', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2045-11-27T22:00:00Z'));
    try {
      const element = render({ ...summary,
        workspaceHousing: { date: '2026-03-31', code: 'B2-01', displayName: 'B2 enclosure 1' },
      });
      expect(element.querySelector('time[datetime="2026-03-31"]')?.textContent).toBe('31 March 2026');
      expect(element.querySelector('time[datetime="2026-02-01"]')?.textContent).toBe('1 Feb 2026');
      expect(element.querySelector('.workspace-record')?.textContent).toContain('31 Mar 2026');
      expect(element.textContent).not.toContain('2045');
    } finally {
      vi.useRealTimers();
    }
  });
});
