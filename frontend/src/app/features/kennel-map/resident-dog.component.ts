import { NgTemplateOutlet } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input, output, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import {
  KennelMapLayer,
  KennelMapResident,
} from '../../core/api/kennel-map.models';

interface ResidentPresentation {
  marker: string;
  label: string;
  tone: string;
}

@Component({
  selector: 'ht-resident-dog',
  imports: [NgTemplateOutlet, RouterLink],
  template: `
    @if (moveMode()) {
      <button
        class="resident-dog move-dog"
        type="button"
        [id]="'map-dog-' + resident().id"
        [class.highlighted]="highlighted()"
        [class.compact]="compact()"
        [class.selected]="selectedDogId() === resident().id"
        [class.dragging]="dragging()"
        [class.pending]="pendingDogIds().has(resident().id)"
        [class.receded]="layer() === 'unavailable' && resident().availability === 'available'"
        [attr.data-tone]="presentation().tone"
        [attr.aria-label]="selectionLabel()"
        [attr.aria-pressed]="selectedDogId() === resident().id"
        [disabled]="interactionsDisabled()"
        [draggable]="!interactionsDisabled()"
        (click)="selectDog()"
        (dragstart)="onDragStart($event)"
        (dragend)="onDragEnd()"
      ><ng-container [ngTemplateOutlet]="content" /></button>
    } @else {
      <a
      class="resident-dog"
      [id]="'map-dog-' + resident().id"
      [routerLink]="['/demo/dogs', resident().id]"
      [class.highlighted]="highlighted()"
      [class.compact]="compact()"
      [class.receded]="layer() === 'unavailable' && resident().availability === 'available'"
      [attr.data-tone]="presentation().tone"
      [attr.aria-label]="ariaLabel()"
      ><ng-container [ngTemplateOutlet]="content" /></a>
    }
    <ng-template #content>
      @if (!compact()) {
        <span class="resident-initial" aria-hidden="true">{{ resident().name.slice(0, 1) }}</span>
      }
      <span class="resident-copy">
        <strong>{{ resident().name }}</strong>
        <small>{{ presentation().label }}</small>
        @if (moveMode() && pendingDogIds().has(resident().id)) {
          <small class="pending-label">Pending move</small>
        }
      </span>
      @if (presentation().marker) {
        <span class="resident-marker" aria-hidden="true">{{ presentation().marker }}</span>
      }
    </ng-template>
  `,
  styleUrl: './resident-dog.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ResidentDogComponent {
  readonly resident = input.required<KennelMapResident>();
  readonly layer = input.required<KennelMapLayer>();
  readonly highlighted = input(false);
  readonly compact = input(false);
  readonly moveMode = input(false);
  readonly selectedDogId = input<string | null>(null);
  readonly pendingDogIds = input<ReadonlySet<string>>(new Set<string>());
  readonly interactionsDisabled = input(false);
  readonly dogSelected = output<string>();
  protected readonly dragging = signal(false);

  protected selectDog(): void {
    if (this.moveMode() && !this.interactionsDisabled()) this.dogSelected.emit(this.resident().id);
  }

  protected onDragStart(event: DragEvent): void {
    if (!this.moveMode() || this.interactionsDisabled() || !event.dataTransfer) {
      event.preventDefault();
      return;
    }
    event.stopPropagation();
    event.dataTransfer.setData('application/x-husky-dog', this.resident().id);
    event.dataTransfer.effectAllowed = 'move';
    this.dragging.set(true);
  }

  protected onDragEnd(): void {
    this.dragging.set(false);
  }

  protected readonly presentation = computed<ResidentPresentation>(() => {
    const dog = this.resident();
    switch (this.layer()) {
      case 'gender':
        return {
          marker: dog.sex === 'female' ? 'F' : 'M',
          label: dog.sex === 'female' ? 'Female' : 'Male',
          tone: dog.sex,
        };
      case 'neutered':
        return dog.is_neutered
          ? {
              marker: 'N',
              label: dog.sex === 'female' ? 'Spayed' : 'Neutered',
              tone: 'neutered',
            }
          : { marker: 'I', label: 'Intact', tone: 'intact' };
      case 'class':
        return {
          marker: dog.dog_class?.slice(0, 1).toUpperCase() ?? '?',
          label: this.title(dog.dog_class ?? 'Class not recorded'),
          tone: dog.dog_class ?? 'unknown',
        };
      case 'unavailable':
        return {
          marker: this.statusMarker(dog.availability),
          label: this.title(dog.availability ?? 'Status not recorded'),
          tone: dog.availability ?? 'unknown',
        };
      default:
        return {
          marker: dog.availability === 'available' ? '' : this.statusMarker(dog.availability),
          label:
            dog.availability === 'available'
              ? `${this.title(dog.dog_class ?? 'Class not recorded')} · ${this.title(dog.sex)}`
              : this.title(dog.availability ?? 'Status not recorded'),
          tone: dog.availability === 'available' ? 'default' : (dog.availability ?? 'unknown'),
        };
    }
  });

  protected ariaLabel(): string {
    const dog = this.resident();
    return `Open ${dog.name} profile. ${this.presentation().label}. Housed in ${dog.housing_code}.`;
  }

  protected selectionLabel(): string {
    const dog = this.resident();
    const pending = this.pendingDogIds().has(dog.id) ? ' Pending move.' : '';
    return `Select ${dog.name} to move. ${this.presentation().label}. Preview housing ${dog.housing_code}.${pending}`;
  }

  private statusMarker(status: string | null): string {
    return { injured: 'I', rest: 'R', restricted: 'X', retired: 'T', available: 'A' }[
      status ?? ''
    ] ?? '?';
  }

  private title(value: string): string {
    return value.slice(0, 1).toUpperCase() + value.slice(1).replaceAll('_', ' ');
  }
}
