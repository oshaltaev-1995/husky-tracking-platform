import { Availability, DogClass, DogSex } from './dogs.models';

export type KennelMapLayer = 'default' | 'gender' | 'neutered' | 'class' | 'unavailable';

export interface KennelMapResident {
  id: string;
  name: string;
  sex: DogSex;
  is_neutered: boolean;
  dog_class: DogClass | null;
  lifecycle: 'active';
  availability: Availability | null;
  housing_code: string;
  litter_code: string | null;
  photo_key: string | null;
}

export interface KennelMapLocation {
  id: string;
  code: string;
  display_name: string;
  location_type: 'adult_enclosure' | 'puppy_area';
  zone: string;
  row: string;
  position: number;
  capacity: number;
  is_active: boolean;
  residents: KennelMapResident[];
}

export interface KennelMapSummary {
  resident_dogs: number;
  occupied_locations: number;
  unavailable_dogs: number;
  class_counts: Record<string, number>;
  sex_counts: Record<string, number>;
  neutered_counts: Record<string, number>;
  availability_counts: Record<string, number>;
}

export interface KennelMapSnapshot {
  selected_date: string;
  season_start: string;
  season_end: string;
  reference_date: string;
  summary: KennelMapSummary;
  locations: KennelMapLocation[];
}

export interface KennelRowView {
  code: string;
  label: string;
  locations: KennelMapLocation[];
}
