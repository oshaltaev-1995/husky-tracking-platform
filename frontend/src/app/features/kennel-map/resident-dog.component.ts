import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
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
  imports: [RouterLink],
  template: `
    <a
      class="resident-dog"
      [id]="'map-dog-' + resident().id"
      [routerLink]="['/dogs', resident().id]"
      [class.highlighted]="highlighted()"
      [class.receded]="layer() === 'unavailable' && resident().availability === 'available'"
      [attr.data-tone]="presentation().tone"
      [attr.aria-label]="ariaLabel()"
    >
      <span class="resident-initial" aria-hidden="true">{{ resident().name.slice(0, 1) }}</span>
      <span class="resident-copy">
        <strong>{{ resident().name }}</strong>
        <small>{{ presentation().label }}</small>
      </span>
      @if (presentation().marker) {
        <span class="resident-marker" aria-hidden="true">{{ presentation().marker }}</span>
      }
    </a>
  `,
  styleUrl: './resident-dog.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ResidentDogComponent {
  readonly resident = input.required<KennelMapResident>();
  readonly layer = input.required<KennelMapLayer>();
  readonly highlighted = input(false);

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

  private statusMarker(status: string | null): string {
    return { injured: 'I', rest: 'R', restricted: 'X', retired: 'T', available: 'A' }[
      status ?? ''
    ] ?? '?';
  }

  private title(value: string): string {
    return value.slice(0, 1).toUpperCase() + value.slice(1).replaceAll('_', ' ');
  }
}
