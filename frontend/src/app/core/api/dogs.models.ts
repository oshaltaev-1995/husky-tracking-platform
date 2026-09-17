export type DogSex = 'female' | 'male';
export type DogClass = 'puppy' | 'junior' | 'training' | 'standard';
export type Availability = 'available' | 'injured' | 'rest' | 'restricted' | 'retired';
export type WorkingRole = 'lead' | 'team' | 'wheel';

export interface LocationView {
  code: string;
  display_name: string;
  location_type: 'adult_enclosure' | 'puppy_area';
  zone: string;
  row: string;
}

export interface ArchiveRecord {
  archive_date: string;
  reason: 'euthanized' | 'deceased' | 'rehomed_to_guide';
  note: string | null;
}

export interface CurrentDogState {
  reference_date: string;
  lifecycle: 'active' | 'archived' | 'unknown';
  dog_class: DogClass | null;
  class_is_historical: boolean;
  availability: Availability | null;
  housing: LocationView | null;
}

export interface DogListItem {
  id: string;
  name: string;
  birth_date: string;
  age_years: number;
  age_months: number;
  age_label: string;
  sex: DogSex;
  is_neutered: boolean;
  litter_code: string | null;
  capabilities: WorkingRole[];
  state: CurrentDogState;
  photo_key: string | null;
}

export interface ActivePopulationSummary {
  total: number;
  puppy: number;
  junior: number;
  training: number;
  standard: number;
}

export interface DogsRegistryResponse {
  reference_date: string;
  result_count: number;
  summary: ActivePopulationSummary;
  housing_groups: string[];
  items: DogListItem[];
}

export interface ArchiveListItem {
  id: string;
  name: string;
  birth_date: string;
  age_years: number;
  age_months: number;
  age_label: string;
  sex: DogSex;
  litter_code: string | null;
  archive: ArchiveRecord;
  offspring_count: number;
  photo_key: string | null;
}

export interface ArchiveRegistryResponse {
  reference_date: string;
  result_count: number;
  total_archived: number;
  items: ArchiveListItem[];
}

export interface DogProfile {
  id: string;
  name: string;
  birth_date: string;
  age_years: number;
  age_months: number;
  age_label: string;
  sex: DogSex;
  is_neutered: boolean;
  neutered_on: string | null;
  photo_key: string | null;
  notes: string | null;
  litter_code: string | null;
  litter_birth_date: string | null;
  capabilities: WorkingRole[];
  state: CurrentDogState;
  archive: ArchiveRecord | null;
  last_known_housing: LocationView | null;
}

export interface RelatedDog {
  id: string;
  name: string;
  birth_date: string;
  lifecycle: 'active' | 'archived';
  dog_class: DogClass | null;
}

export interface GrandparentPair {
  mother: RelatedDog | null;
  father: RelatedDog | null;
}

export interface DogPedigree {
  dog_id: string;
  mother: RelatedDog | null;
  father: RelatedDog | null;
  maternal_grandparents: GrandparentPair;
  paternal_grandparents: GrandparentPair;
  litter: { code: string; birth_date: string; siblings: RelatedDog[] } | null;
  offspring: { code: string; birth_date: string; children: RelatedDog[] }[];
}

export interface DogWork {
  dog_id: string;
  season_start: string;
  season_end: string;
  summary: {
    total_km: number;
    starts: number;
    starts_5km: number;
    starts_10km: number;
    last_work_date: string | null;
    average_km_per_start: number | null;
  };
  weekly: { week_start: string; starts: number; total_km: number }[];
  entries: {
    date: string;
    distance_km: number;
    activity_type: string;
    label: string | null;
    role: string | null;
  }[];
}

export interface PeriodHistory {
  value: string;
  valid_from: string;
  valid_to: string | null;
  is_current: boolean;
  note: string | null;
}

export interface HousingHistory {
  location: LocationView;
  valid_from: string;
  valid_to: string | null;
  is_current: boolean;
  note: string | null;
}

export interface DogHistory {
  dog_id: string;
  reference_date: string;
  availability: PeriodHistory[];
  classes: PeriodHistory[];
  lifecycle: PeriodHistory[];
  housing: HousingHistory[];
  archive: ArchiveRecord | null;
}

export interface DogProfileBundle {
  profile: DogProfile;
  pedigree: DogPedigree;
  work: DogWork;
  history: DogHistory;
}
