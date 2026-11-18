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
}

export interface KennelPrintRow {
  readonly code: string;
  readonly locations: readonly KennelPrintLocation[];
  /** Native table rows can continue across pages without splitting one dog entry. */
  readonly lines: readonly number[];
}

export interface KennelPrintProjection {
  readonly snapshotDate: string;
  readonly layer: KennelMapLayer;
  readonly layerLabel: string;
  readonly legend: readonly MapLegendItem[];
  readonly residentCount: number;
  readonly locationCount: number;
  readonly groups: readonly {
    readonly label: string;
    readonly rows: readonly KennelPrintRow[];
  }[];
  readonly puppyBuildings: readonly KennelPrintLocation[];
  readonly puppyLines: readonly number[];
}

function locationProjection(location: KennelMapLocation, layer: KennelMapLayer): KennelPrintLocation {
  return Object.freeze({
    code: location.code,
    displayName: location.display_name,
    occupancy: location.residents.length,
    nominalCapacity: location.capacity,
    residents: Object.freeze(location.residents.map((dog) => Object.freeze({
      id: dog.id, name: dog.name, ...mapResidentPresentation(dog, layer),
    }))),
  });
}

function residentLines(locations: readonly KennelPrintLocation[]): readonly number[] {
  return Object.freeze(Array.from({ length: Math.max(1, ...locations.map((location) => location.occupancy)) }, (_, index) => index));
}

/** Freeze detached display data from exactly one committed snapshot and active layer. */
export function projectKennelPrint(snapshot: KennelMapSnapshot, layer: KennelMapLayer): KennelPrintProjection {
  const layout = kennelMapLayout(snapshot);
  const projectLocations = (locations: KennelMapLocation[]) => Object.freeze([...locations]
    .sort((a, b) => a.position - b.position || a.code.localeCompare(b.code, 'en'))
    .map((location) => locationProjection(location, layer)));
  const groups = Object.freeze(layout.blocks.map((group) => Object.freeze({
    label: group.label,
    rows: Object.freeze(group.rows.map((row) => {
      const locations = projectLocations(row.locations);
      return Object.freeze({ code: row.code, locations, lines: residentLines(locations) });
    })),
  })));
  const puppyBuildings = projectLocations(layout.puppyAreas);
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
    puppyLines: residentLines(puppyBuildings),
  });
}
