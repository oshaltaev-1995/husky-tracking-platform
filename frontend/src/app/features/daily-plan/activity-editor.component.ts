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
  ActivityWrite,
  EligibleDog,
  PlannedActivity,
  PlannedActivityType,
} from '../../core/api/daily-plans.models';
import { DailyPlansService } from '../../core/api/daily-plans.service';

@Component({
  selector: 'ht-activity-editor',
  imports: [FormsModule],
  templateUrl: './activity-editor.component.html',
  styleUrl: './activity-editor.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ActivityEditorComponent implements OnInit, AfterViewInit, OnDestroy {
  private readonly plans = inject(DailyPlansService);
  private readonly document = inject(DOCUMENT);
  private readonly cdr = inject(ChangeDetectorRef);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private returnFocus: HTMLElement | null = null;

  @ViewChild('titleInput') private titleInput?: ElementRef<HTMLInputElement>;
  @Input({ required: true }) planDate!: string;
  @Input() revision: number | null = null;
  @Input() activity: PlannedActivity | null = null;
  @Input() saving = false;
  @Input() serverError = '';
  @Input() lineupClearRequired = false;
  @Output() saved = new EventEmitter<ActivityWrite>();
  @Output() closed = new EventEmitter<void>();
  @Output() confirmedLineupClear = new EventEmitter<void>();
  @Output() keptLineup = new EventEmitter<void>();

  protected activityType: PlannedActivityType = 'training';
  protected startTime = '';
  protected title = 'Training Loop';
  protected distanceKm: 5 | 10 | null = 5;
  protected notes = '';
  protected search = '';
  protected candidates: EligibleDog[] = [];
  protected selectedDogIds: string[] = [];
  protected loadingCandidates = true;
  protected eligibilityError = '';
  protected readonly activityTypes: { value: PlannedActivityType; label: string }[] = [
    { value: 'training', label: 'Training' },
    { value: 'open_space_walk', label: 'Open-space walk' },
    { value: 'individual_exercise', label: 'Individual exercise' },
    { value: 'rest', label: 'Rest' },
  ];

  ngOnInit(): void {
    if (this.activity) {
      this.activityType = this.activity.activity_type;
      this.startTime = this.activity.start_time?.slice(0, 5) ?? '';
      this.title = this.activity.title;
      this.distanceKm = this.activity.distance_km as 5 | 10 | null;
      this.notes = this.activity.notes ?? '';
      this.selectedDogIds = this.activity.participants.map((dog) => dog.id);
    }
    this.loadCandidates();
  }

  ngAfterViewInit(): void {
    this.returnFocus = this.document.activeElement as HTMLElement | null;
    this.document.body.classList.add('dialog-open');
    queueMicrotask(() => this.titleInput?.nativeElement.focus());
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

  protected typeChanged(): void {
    const defaults: Record<PlannedActivityType, string> = {
      training: 'Training Loop',
      open_space_walk: 'Open-space walk',
      individual_exercise: 'Individual exercise',
      rest: 'Rest',
    };
    this.title = defaults[this.activityType];
    this.distanceKm = this.activityType === 'training' ? 5 : null;
    this.loadCandidates();
  }

  protected distanceChanged(): void {
    this.loadCandidates();
  }

  protected visibleCandidates(): EligibleDog[] {
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

  protected selected(dog: EligibleDog): boolean {
    return this.selectedDogIds.includes(dog.id);
  }

  protected toggleDog(dog: EligibleDog): void {
    if (!dog.eligible && !this.selected(dog)) return;
    this.selectedDogIds = this.selected(dog)
      ? this.selectedDogIds.filter((id) => id !== dog.id)
      : [...this.selectedDogIds, dog.id];
  }

  protected submit(): void {
    if (!this.title.trim() || !this.selectedDogIds.length || this.saving) return;
    this.saved.emit({
      activity_type: this.activityType,
      start_time: this.startTime || null,
      title: this.title.trim(),
      distance_km: this.activityType === 'training' ? this.distanceKm : null,
      notes: this.notes.trim() || null,
      participant_ids: this.selectedDogIds,
      expected_revision: this.revision,
    });
  }

  protected close(): void {
    if (!this.saving) this.closed.emit();
  }

  protected label(value: string | null): string {
    if (!value) return 'Unknown';
    return value.replaceAll('_', ' ').replace(/^./, (character) => character.toUpperCase());
  }

  protected activityLabel(): string {
    return this.activityTypes.find((item) => item.value === this.activityType)?.label ?? '';
  }

  private loadCandidates(): void {
    this.loadingCandidates = true;
    this.eligibilityError = '';
    this.plans
      .getEligibility(
        this.planDate,
        this.activityType,
        this.activityType === 'training' ? this.distanceKm : null,
        this.activity?.id,
      )
      .subscribe({
        next: (eligibility) => {
          this.candidates = eligibility.dogs;
          const allowed = new Set(
            eligibility.dogs.filter((dog) => dog.eligible).map((dog) => dog.id),
          );
          this.selectedDogIds = this.selectedDogIds.filter((id) => allowed.has(id));
          this.loadingCandidates = false;
          this.cdr.markForCheck();
        },
        error: () => {
          this.loadingCandidates = false;
          this.eligibilityError = 'Eligibility could not be loaded. Close and try again.';
          this.cdr.markForCheck();
        },
      });
  }
}
