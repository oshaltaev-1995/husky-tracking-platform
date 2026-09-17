import { DOCUMENT } from '@angular/common';
import {
  AfterViewInit,
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  ElementRef,
  EventEmitter,
  HostListener,
  Input,
  OnDestroy,
  OnInit,
  Output,
  ViewChild,
  inject,
} from '@angular/core';
import { FormsModule } from '@angular/forms';

import {
  ActualEligibleDog,
  ActualParticipantWrite,
  ActualSession,
  ActualSessionWrite,
} from '../../core/api/daily-entry.models';
import { DailyEntryService } from '../../core/api/daily-entry.service';

@Component({
  selector: 'ht-actual-session-editor',
  imports: [FormsModule],
  templateUrl: './actual-session-editor.component.html',
  styleUrl: './actual-session-editor.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ActualSessionEditorComponent implements OnInit, AfterViewInit, OnDestroy {
  private readonly entries = inject(DailyEntryService);
  private readonly document = inject(DOCUMENT);
  private readonly cdr = inject(ChangeDetectorRef);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private returnFocus: HTMLElement | null = null;

  @ViewChild('labelInput') private labelInput?: ElementRef<HTMLInputElement>;
  @Input({ required: true }) entryDate!: string;
  @Input() session: ActualSession | null = null;
  @Input() saving = false;
  @Input() serverError = '';
  @Output() saved = new EventEmitter<ActualSessionWrite>();
  @Output() closed = new EventEmitter<void>();

  protected distanceKm: 5 | 10 = 5;
  protected startTime = '';
  protected label = 'Actual training';
  protected note = '';
  protected search = '';
  protected participants: ActualParticipantWrite[] = [];
  protected candidates: ActualEligibleDog[] = [];
  protected loadingCandidates = true;
  protected eligibilityError = '';

  ngOnInit(): void {
    if (this.session) {
      this.distanceKm = this.session.distance_km;
      this.startTime = this.session.start_time?.slice(0, 5) ?? '';
      this.label = this.session.label ?? 'Actual training';
      this.note = this.session.note ?? '';
      this.participants = this.session.participants.map((item) => ({
        dog_id: item.dog_id,
        assigned_role: item.assigned_role,
        actual_team_sequence: item.actual_team_sequence,
        pair_index: item.pair_index,
        side: item.side,
        position_order: item.position_order,
      }));
    }
    this.loadCandidates();
  }

  ngAfterViewInit(): void {
    this.returnFocus = this.document.activeElement as HTMLElement | null;
    this.document.body.classList.add('dialog-open');
    queueMicrotask(() => this.labelInput?.nativeElement.focus());
  }

  ngOnDestroy(): void {
    this.document.body.classList.remove('dialog-open');
    queueMicrotask(() => this.returnFocus?.focus());
  }

  @HostListener('document:keydown.escape', ['$event'])
  protected onEscape(event: Event): void {
    event.preventDefault();
    this.close();
  }

  @HostListener('document:keydown.tab', ['$event'])
  protected trapFocus(event: Event): void {
    const keyboardEvent = event as KeyboardEvent;
    const focusable = Array.from(
      this.host.nativeElement.querySelectorAll<HTMLElement>(
        'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled])',
      ),
    ).filter((element) => element.offsetParent !== null);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (keyboardEvent.shiftKey && this.document.activeElement === first) {
      keyboardEvent.preventDefault();
      last.focus();
    } else if (!keyboardEvent.shiftKey && this.document.activeElement === last) {
      keyboardEvent.preventDefault();
      first.focus();
    }
  }

  protected distanceChanged(): void {
    this.loadCandidates();
  }

  protected visibleCandidates(): ActualEligibleDog[] {
    const term = this.search.trim().toLocaleLowerCase();
    return this.candidates.filter((dog) => {
      if (!term) return true;
      return [dog.name, dog.housing_code, dog.dog_class, dog.availability]
        .filter(Boolean)
        .join(' ')
        .toLocaleLowerCase()
        .includes(term);
    });
  }

  protected positioned(): ActualParticipantWrite[] {
    return this.participants.filter((item) => item.actual_team_sequence !== null);
  }

  protected unpositioned(): ActualParticipantWrite[] {
    return this.participants.filter((item) => item.actual_team_sequence === null);
  }

  protected selected(dogId: string): boolean {
    return this.participants.some((item) => item.dog_id === dogId);
  }

  protected candidate(dogId: string): ActualEligibleDog | undefined {
    return this.candidates.find((dog) => dog.id === dogId);
  }

  protected dogName(dogId: string): string {
    return (
      this.candidate(dogId)?.name ??
      this.session?.participants.find((item) => item.dog_id === dogId)?.dog_name ??
      'Unknown dog'
    );
  }

  protected toggleDog(dog: ActualEligibleDog): void {
    const existing = this.participants.find((item) => item.dog_id === dog.id);
    if (existing) {
      this.participants = this.participants.filter((item) => item !== existing);
    } else if (dog.eligible) {
      this.participants = [
        ...this.participants,
        {
          dog_id: dog.id,
          assigned_role: null,
          actual_team_sequence: null,
          pair_index: null,
          side: null,
          position_order: null,
        },
      ];
    }
  }

  protected replaceSlot(slot: ActualParticipantWrite, dogId: string): void {
    if (!dogId || this.selected(dogId)) return;
    slot.dog_id = dogId;
  }

  protected replacementCandidates(slot: ActualParticipantWrite): ActualEligibleDog[] {
    return this.candidates.filter(
      (dog) =>
        dog.eligible &&
        !this.selected(dog.id) &&
        (!slot.assigned_role || dog.capabilities.includes(slot.assigned_role)),
    );
  }

  protected swapCandidates(slot: ActualParticipantWrite): ActualParticipantWrite[] {
    const dog = this.candidate(slot.dog_id);
    if (!dog) return [];
    return this.positioned().filter((other) => {
      if (other === slot) return false;
      const otherDog = this.candidate(other.dog_id);
      return (
        !!otherDog &&
        (!slot.assigned_role || otherDog.capabilities.includes(slot.assigned_role)) &&
        (!other.assigned_role || dog.capabilities.includes(other.assigned_role))
      );
    });
  }

  protected swapSlot(slot: ActualParticipantWrite, dogId: string): void {
    const other = this.participants.find((item) => item.dog_id === dogId);
    if (!other) return;
    const current = slot.dog_id;
    slot.dog_id = other.dog_id;
    other.dog_id = current;
  }

  protected removeParticipant(item: ActualParticipantWrite): void {
    this.participants = this.participants.filter((participant) => participant !== item);
  }

  protected clearGeometry(): void {
    this.participants = this.participants.map((item) => ({
      ...item,
      assigned_role: null,
      actual_team_sequence: null,
      pair_index: null,
      side: null,
      position_order: null,
    }));
  }

  protected pairLabel(item: ActualParticipantWrite): string {
    if (item.assigned_role === 'lead') return 'Lead';
    if (item.assigned_role === 'wheel') return 'Wheel';
    return `Team ${item.pair_index}`;
  }

  protected labelValue(value: string | null): string {
    if (!value) return 'Unknown';
    return value.replaceAll('_', ' ').replace(/^./, (character) => character.toUpperCase());
  }

  protected submit(): void {
    if (!this.participants.length || this.saving) return;
    this.saved.emit({
      distance_km: this.distanceKm,
      start_time: this.startTime || null,
      label: this.label.trim() || null,
      note: this.note.trim() || null,
      participants: this.participants,
    });
  }

  protected close(): void {
    if (!this.saving) this.closed.emit();
  }

  private loadCandidates(): void {
    this.loadingCandidates = true;
    this.eligibilityError = '';
    this.entries.getEligibility(this.entryDate, this.distanceKm, this.session?.id).subscribe({
      next: (result) => {
        this.candidates = result.dogs;
        const available = new Set(result.dogs.map((dog) => dog.id));
        this.participants = this.participants.filter((item) => available.has(item.dog_id));
        this.loadingCandidates = false;
        this.cdr.markForCheck();
      },
      error: () => {
        this.loadingCandidates = false;
        this.eligibilityError = 'Actual-work eligibility could not be loaded.';
        this.cdr.markForCheck();
      },
    });
  }
}
