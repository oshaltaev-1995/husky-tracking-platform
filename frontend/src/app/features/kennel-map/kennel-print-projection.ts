import { KennelMapLayer, KennelMapLocation, KennelMapSnapshot } from '../../core/api/kennel-map.models';
import { kennelMapLayout } from './kennel-map-layout';
import { MapLegendItem, mapLayerLabel, mapLayerLegend, mapResidentPresentation } from './kennel-map-presentation';

export interface KennelPrintResident {
  /** Internal identity for roster validation and Angular tracking; never rendered. */
  readonly id: string;
  readonly name: string;
  readonly marker: string;
  readonly label: string;
  readonly tone: string;
}

export interface KennelPrintLocation {
  readonly code: string;
  readonly displayName: string;
  readonly occupancy: number;
  readonly nominalCapacity: number;
  readonly residents: readonly KennelPrintResident[];
  readonly mapResidents: readonly KennelPrintResident[];
  readonly continuationResidents: readonly KennelPrintResident[];
  readonly groupLabel: string;
}

export interface KennelPrintRow {
  readonly code: string;
  readonly locations: readonly KennelPrintLocation[];
}

export interface KennelPrintProjection {
  readonly snapshotDate: string;
  readonly layer: KennelMapLayer;
  readonly layerLabel: string;
  readonly legend: readonly MapLegendItem[];
  readonly residentCount: number;
  readonly locationCount: number;
  readonly groups: readonly {
    readonly code: string;
    readonly label: string;
    readonly rows: readonly KennelPrintRow[];
  }[];
  readonly puppyBuildings: readonly KennelPrintLocation[];
  readonly continuations: readonly KennelPrintLocation[];
}

/** Conservative text-line budget for the spatial sheet, not a housing/capacity rule.
 * Every remaining resident is printed once in an explicitly labelled continuation.
 * Character estimates deliberately reserve room for wrapping at the fixed 9/10pt sizes.
 */
function locationProjection(location: KennelMapLocation, layer: KennelMapLayer, groupLabel: string): KennelPrintLocation {
  const residents = Object.freeze(location.residents.map((dog) => Object.freeze({
    id: dog.id, name: dog.name, ...mapResidentPresentation(dog, layer),
  })));
  const puppy = location.location_type === 'puppy_area';
  const budget = puppy ? 10 : 6;
  const fit = (available: number): number => {
    let used = 0, count = 0;
    for (const dog of residents) {
      const lines = Math.ceil(dog.name.length / (puppy ? 40 : 11)) +
        Math.ceil((dog.label.length + (dog.marker ? 2 : 0)) / (puppy ? 44 : 12));
      if (used + lines > available) break;
      used += lines;
      count++;
    }
    return count;
  };
  let count = fit(budget);
  // An overflow pointer occupies real space too; reserve its wrapped lines.
  if (count < residents.length) count = fit(budget - (puppy ? 2 : 3));
  return Object.freeze({
    code: location.code, displayName: location.display_name, occupancy: residents.length,
    nominalCapacity: location.capacity, groupLabel, residents,
    mapResidents: Object.freeze(residents.slice(0, count)),
    continuationResidents: Object.freeze(residents.slice(count)),
  });
}

/** Freeze detached display data from exactly one committed snapshot and active layer. */
export function projectKennelPrint(snapshot: KennelMapSnapshot, layer: KennelMapLayer): KennelPrintProjection {
  const layout = kennelMapLayout(snapshot);
  const projectLocations = (locations: KennelMapLocation[], groupLabel: string) => Object.freeze([...locations]
    .sort((a, b) => a.position - b.position || a.code.localeCompare(b.code, 'en'))
    .map((location) => locationProjection(location, layer, groupLabel)));
  const groups = Object.freeze(layout.blocks.map((group) => Object.freeze({
    code: group.zone, label: group.label,
    rows: Object.freeze(group.rows.map((row) => {
      const locations = projectLocations(row.locations, group.label);
      return Object.freeze({ code: row.code, locations });
    })),
  })));
  const puppyBuildings = projectLocations(layout.puppyAreas, 'Puppy buildings');
  const locations = [...groups.flatMap((group) => group.rows.flatMap((row) => row.locations)), ...puppyBuildings];
  return Object.freeze({
    snapshotDate: snapshot.selected_date,
    layer,
    layerLabel: mapLayerLabel(layer),
    legend: Object.freeze(mapLayerLegend(layer).map((item) => Object.freeze({ ...item }))),
    residentCount: locations.reduce((total, location) => total + location.occupancy, 0),
    locationCount: locations.length,
    groups,
    puppyBuildings,
    continuations: Object.freeze(locations.filter((location) => location.continuationResidents.length)),
  });
}
