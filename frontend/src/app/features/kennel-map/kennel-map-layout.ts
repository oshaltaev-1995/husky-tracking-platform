import {
  KennelMapLocation,
  KennelMapSnapshot,
  KennelRowView,
} from '../../core/api/kennel-map.models';

export interface KennelBlockView {
  zone: string;
  label: string;
  rows: KennelRowView[];
}

export function kennelMapLayout(snapshot: KennelMapSnapshot): {
  blocks: KennelBlockView[];
  puppyAreas: KennelMapLocation[];
} {
  return {
    blocks: ['A', 'B'].map((zone) => ({
      zone,
      label: `Zone ${zone}`,
      rows: ['1', '2'].map((row) => ({
        code: `${zone}${row}`,
        label: `Row ${zone}${row}`,
        locations: snapshot.locations.filter(
          (location) =>
            location.location_type === 'adult_enclosure' &&
            location.zone === zone &&
            location.row === row,
        ),
      })),
    })),
    puppyAreas: snapshot.locations.filter((location) => location.location_type === 'puppy_area'),
  };
}
