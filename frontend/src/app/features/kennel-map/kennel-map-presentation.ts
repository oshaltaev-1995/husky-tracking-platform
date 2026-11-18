import { KennelMapLayer, KennelMapResident } from '../../core/api/kennel-map.models';

export interface MapLegendItem {
  readonly label: string;
  readonly marker: string;
  readonly tone: string;
}

export interface ResidentPresentation {
  readonly marker: string;
  readonly label: string;
  readonly tone: string;
}

const LAYER_LABELS: Readonly<Record<KennelMapLayer, string>> = Object.freeze({
  default: 'Default', gender: 'Gender', neutered: 'Neutered', class: 'Class', unavailable: 'Unavailable',
});

const LEGENDS: Readonly<Record<KennelMapLayer, readonly MapLegendItem[]>> = Object.freeze({
  default: [{ label: 'Class and sex · unavailable status marked', marker: 'D', tone: 'default' }],
  gender: [
    { label: 'Female', marker: 'F', tone: 'female' },
    { label: 'Male', marker: 'M', tone: 'male' },
  ],
  neutered: [
    { label: 'Intact', marker: 'I', tone: 'intact' },
    { label: 'Neutered / spayed', marker: 'N', tone: 'neutered' },
  ],
  class: [
    { label: 'Puppy', marker: 'P', tone: 'puppy' },
    { label: 'Junior', marker: 'J', tone: 'junior' },
    { label: 'Training', marker: 'T', tone: 'training' },
    { label: 'Standard', marker: 'S', tone: 'standard' },
  ],
  unavailable: [
    { label: 'Available', marker: 'A', tone: 'available' },
    { label: 'Injured', marker: 'I', tone: 'injured' },
    { label: 'Rest', marker: 'R', tone: 'rest' },
    { label: 'Restricted', marker: 'X', tone: 'restricted' },
    { label: 'Retired', marker: 'T', tone: 'retired' },
  ],
});

export function mapLayerLabel(layer: KennelMapLayer): string {
  return LAYER_LABELS[layer];
}

export function mapLayerLegend(layer: KennelMapLayer): readonly MapLegendItem[] {
  return LEGENDS[layer];
}

function title(value: string): string {
  return value.slice(0, 1).toUpperCase() + value.slice(1).replaceAll('_', ' ');
}

function statusMarker(status: string | null): string {
  return { injured: 'I', rest: 'R', restricted: 'X', retired: 'T', available: 'A' }[status ?? ''] ?? '?';
}

/** Shared text and markers for interactive residents and the committed print snapshot. */
export function mapResidentPresentation(dog: KennelMapResident, layer: KennelMapLayer): ResidentPresentation {
  switch (layer) {
    case 'gender':
      return { marker: dog.sex === 'female' ? 'F' : 'M', label: dog.sex === 'female' ? 'Female' : 'Male', tone: dog.sex };
    case 'neutered':
      return dog.is_neutered
        ? { marker: 'N', label: dog.sex === 'female' ? 'Spayed' : 'Neutered', tone: 'neutered' }
        : { marker: 'I', label: 'Intact', tone: 'intact' };
    case 'class':
      return { marker: dog.dog_class?.slice(0, 1).toUpperCase() ?? '?', label: title(dog.dog_class ?? 'Class not recorded'), tone: dog.dog_class ?? 'unknown' };
    case 'unavailable':
      return { marker: statusMarker(dog.availability), label: title(dog.availability ?? 'Status not recorded'), tone: dog.availability ?? 'unknown' };
    default:
      return {
        marker: dog.availability === 'available' ? '' : statusMarker(dog.availability),
        label: dog.availability === 'available'
          ? `${title(dog.dog_class ?? 'Class not recorded')} · ${title(dog.sex)}`
          : title(dog.availability ?? 'Status not recorded'),
        tone: dog.availability === 'available' ? 'default' : (dog.availability ?? 'unknown'),
      };
  }
}
