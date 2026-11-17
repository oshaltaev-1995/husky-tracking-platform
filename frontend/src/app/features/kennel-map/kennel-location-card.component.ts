import { ChangeDetectionStrategy, Component, computed, effect, ElementRef, inject, input, output, signal } from '@angular/core';

import {
  KennelMapLayer,
  KennelMapLocation,
} from '../../core/api/kennel-map.models';
import { ResidentDogComponent } from './resident-dog.component';

@Component({
  selector: 'ht-kennel-location-card',
  imports: [ResidentDogComponent],
  template: `
    <article
      class="location-card"
      [class.puppy-area]="location().location_type === 'puppy_area'"
      [class.highlighted]="containsHighlight()"
      [class.compact]="compact()"
      [class.move-target]="moveMode() && !interactionsDisabled()"
      [class.drop-active]="dragOver()"
      [class.affected]="moveMode() && affectedLocationCodes().has(location().code)"
      [attr.data-location-code]="location().code"
      [attr.aria-label]="location().display_name + ', ' + occupancyLabel()"
      (dragenter)="onDragOver($event)"
      (dragover)="onDragOver($event)"
      (dragleave)="onDragLeave($event)"
      (drop)="onDrop($event)"
    >
      <header>
        <div>
          @if (!compact()) {
            <p>{{ location().location_type === 'puppy_area' ? 'Puppy area' : 'Enclosure' }}</p>
          }
          <h3>{{ location().code }}</h3>
        </div>
        <span>{{ occupancyLabel() }}</span>
      </header>
      @if (moveMode() && affectedLocationCodes().has(location().code)) {
        <p class="pending-location">Pending changes</p>
      }
      @if (location().residents.length > location().capacity) {
        <p class="capacity-note">{{ location().residents.length }} residents · nominal capacity {{ location().capacity }}</p>
      }
      @if (location().location_type === 'puppy_area') {
        <p class="area-detail">{{ litterLabel() }}</p>
      }
      <div class="resident-list">
        @for (dog of location().residents; track dog.id) {
          <ht-resident-dog
            [resident]="dog"
            [layer]="layer()"
            [highlighted]="dog.id === highlightedDogId()"
            [compact]="compact()"
            [moveMode]="moveMode()"
            [selectedDogId]="selectedDogId()"
            [pendingDogIds]="pendingDogIds()"
            [interactionsDisabled]="interactionsDisabled()"
            (dogSelected)="dogSelected.emit($event)"
          />
        }
        @for (slot of emptySlots(); track slot) {
          <div class="empty-resident-slot" aria-label="Empty resident place">
            <span aria-hidden="true">—</span>
            <small>Empty</small>
          </div>
        }
      </div>
    </article>
  `,
  styleUrl: './kennel-location-card.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KennelLocationCardComponent {
  readonly location = input.required<KennelMapLocation>();
  readonly layer = input.required<KennelMapLayer>();
  readonly highlightedDogId = input<string | null>(null);
  readonly compact = input(false);
  readonly moveMode = input(false);
  readonly selectedDogId = input<string | null>(null);
  readonly pendingDogIds = input<ReadonlySet<string>>(new Set<string>());
  readonly affectedLocationCodes = input<ReadonlySet<string>>(new Set<string>());
  readonly interactionsDisabled = input(false);
  readonly dogSelected = output<string>();
  readonly dogDropped = output<{ dogId: string; destinationCode: string }>();
  protected readonly dragOver = signal(false);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);

  constructor() {
    effect(() => {
      if (!this.moveMode() || this.interactionsDisabled()) this.dragOver.set(false);
    });
  }

  protected onDragOver(event: DragEvent): void {
    if (!this.canAcceptDrag(event)) return;
    event.preventDefault();
    event.stopPropagation();
    if (event.dataTransfer) event.dataTransfer.dropEffect = 'move';
    this.dragOver.set(true);
  }

  protected onDragLeave(event: DragEvent): void {
    if (event.relatedTarget instanceof Node && this.host.nativeElement.contains(event.relatedTarget)) return;
    this.dragOver.set(false);
  }

  protected onDrop(event: DragEvent): void {
    this.dragOver.set(false);
    if (!this.canAcceptDrag(event)) return;
    event.preventDefault();
    event.stopPropagation();
    const dogId = event.dataTransfer?.getData('application/x-husky-dog');
    if (dogId) this.dogDropped.emit({ dogId, destinationCode: this.location().code });
  }

  private canAcceptDrag(event: DragEvent): boolean {
    return this.moveMode() && !this.interactionsDisabled() && this.location().is_active &&
      Array.from(event.dataTransfer?.types ?? []).includes('application/x-husky-dog');
  }

  protected readonly containsHighlight = computed(() =>
    this.location().residents.some((dog) => dog.id === this.highlightedDogId()),
  );

  protected occupancyLabel(): string {
    return `${this.location().residents.length} / ${this.location().capacity}`;
  }

  protected emptySlots(): number[] {
    // Ground shows occupancy, rather than drawing nominal places as separate rows.
    if (this.compact()) return this.location().residents.length ? [] : [0];
    return Array.from(
      { length: Math.max(0, this.location().capacity - this.location().residents.length) },
      (_, index) => index,
    );
  }

  protected litterLabel(): string {
    const litters = [...new Set(this.location().residents.map((dog) => dog.litter_code).filter(Boolean))];
    return litters.length ? `${litters.join(' + ')}-litter residents` : this.location().display_name;
  }
}
