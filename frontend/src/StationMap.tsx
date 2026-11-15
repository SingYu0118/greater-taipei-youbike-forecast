import { useEffect, useRef } from "react";
import {
  AttributionControl,
  LngLatBounds,
  Map as MapLibreMap,
  NavigationControl,
  setWorkerUrl,
  type ExpressionSpecification,
  type GeoJSONSource,
  type MapGeoJSONFeature,
  type MapLayerMouseEvent,
} from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import type { Station } from "./types";
import type { MrtStation } from "./mrt";

setWorkerUrl(workerUrl);

type Props = {
  stations: Station[];
  focusRegion: "all" | "taipei" | "new_taipei";
  selectedId?: string;
  focusMrtStations?: MrtStation[];
  onSelect: (station: Station) => void;
};

const mapStyle = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

export default function StationMap({ stations, focusRegion, selectedId, focusMrtStations = [], onSelect }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MapLibreMap | null>(null);
  const onSelectRef = useRef(onSelect);
  const stationIndex = useRef(new Map<string, Station>());
  stationIndex.current = new Map(stations.map((station) => [stationKey(station), station]));

  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  useEffect(() => {
    if (!container.current || map.current) return;
    const instance = new MapLibreMap({
      container: container.current,
      style: mapStyle,
      center: [121.54, 25.04],
      zoom: 10.7,
      attributionControl: false,
    });
    instance.addControl(new NavigationControl({ showCompass: false }), "top-right");
    instance.addControl(new AttributionControl({ compact: true }), "bottom-left");
    instance.on("load", () => {
      instance.addSource("stations", {
        type: "geojson",
        data: featureCollection([...stationIndex.current.values()]),
      });
      instance.addSource("selected-mrt", {
        type: "geojson",
        data: emptyFeatureCollection(),
      });
      instance.addLayer({
        id: "station-halo",
        type: "circle",
        source: "stations",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 9, 2, 14, 8],
          "circle-color": statusColorExpression,
          "circle-opacity": 0.2,
          "circle-blur": 0.5,
        },
      });
      instance.addLayer({
        id: "selected-mrt",
        type: "circle",
        source: "selected-mrt",
        paint: {
          "circle-radius": 10,
          "circle-color": "#ffd83d",
          "circle-stroke-color": "#27231c",
          "circle-stroke-width": 3,
        },
      });
      instance.addLayer({
        id: "stations",
        type: "circle",
        source: "stations",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 9, 1.5, 14, 5],
          "circle-color": statusColorExpression,
          "circle-stroke-color": "#081713",
          "circle-stroke-width": 1,
        },
      });
      instance.on("mouseenter", "stations", () => (instance.getCanvas().style.cursor = "pointer"));
      instance.on("mouseleave", "stations", () => (instance.getCanvas().style.cursor = ""));
      instance.on("click", "stations", (event: MapLayerMouseEvent) => {
        const feature = event.features?.[0] as MapGeoJSONFeature | undefined;
        const station = feature?.properties?.station_key
          ? stationIndex.current.get(feature.properties.station_key)
          : undefined;
        if (station) onSelectRef.current(station);
      });
    });
    map.current = instance;
    return () => {
      instance.remove();
      map.current = null;
    };
  }, []);

  useEffect(() => {
    const source = map.current?.getSource("stations") as GeoJSONSource | undefined;
    source?.setData(featureCollection(stations));
  }, [stations]);

  useEffect(() => {
    const instance = map.current;
    if (!instance) return;
    const view = regionViews[focusRegion];
    const moveToRegion = () => instance.easeTo({ ...view, duration: 850 });
    if (instance.isStyleLoaded()) moveToRegion();
    else instance.once("load", moveToRegion);
  }, [focusRegion]);

  useEffect(() => {
    const station = stationIndex.current.get(selectedId ?? "");
    const instance = map.current;
    if (!station || !instance) return;
    const moveToStation = () => instance.easeTo({
      center: [station.longitude, station.latitude],
      zoom: 14,
      duration: 700,
    });
    if (instance.isStyleLoaded()) moveToStation();
    else instance.once("load", moveToStation);
  }, [selectedId]);

  useEffect(() => {
    const instance = map.current;
    if (!instance) return;
    const update = () => {
      const source = instance.getSource("selected-mrt") as GeoJSONSource | undefined;
      source?.setData(focusMrtStations.length ? mrtFeatureCollection(focusMrtStations) : emptyFeatureCollection());
      if (focusMrtStations.length === 1) {
        const [station] = focusMrtStations;
        instance.easeTo({ center: [station.longitude, station.latitude], zoom: 14.2, duration: 850 });
      } else if (focusMrtStations.length > 1) {
        const bounds = focusMrtStations.reduce(
          (current, station) => current.extend([station.longitude, station.latitude]),
          new LngLatBounds(
            [focusMrtStations[0].longitude, focusMrtStations[0].latitude],
            [focusMrtStations[0].longitude, focusMrtStations[0].latitude],
          ),
        );
        instance.fitBounds(bounds, { padding: 70, maxZoom: 12.5, duration: 850 });
      }
    };
    if (instance.isStyleLoaded()) update();
    else instance.once("load", update);
  }, [focusMrtStations]);

  return <div className="map" ref={container} aria-label="Interactive YouBike station map" />;
}

const regionViews = {
  all: { center: [121.52, 25.05] as [number, number], zoom: 9.65 },
  taipei: { center: [121.545, 25.055] as [number, number], zoom: 11.15 },
  new_taipei: { center: [121.49, 25.04] as [number, number], zoom: 10.05 },
};

const statusColorExpression: ExpressionSpecification = [
  "step",
  ["get", "ratio"],
  "#ff7163",
  0.15,
  "#ffbd5c",
  0.35,
  "#8be0bd",
  0.8,
  "#64a7ff",
];

function featureCollection(stations: Station[]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: stations.map((station) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [station.longitude, station.latitude] },
      properties: {
        station_key: stationKey(station),
        ratio: station.capacity
          ? (station.predicted_bikes ?? station.available_bikes) / station.capacity
          : 0,
      },
    })),
  };
}

function stationKey(station: Station): string {
  return `${station.source}:${station.station_id}`;
}

function mrtFeatureCollection(stations: MrtStation[]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: stations.map((station) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [station.longitude, station.latitude] },
      properties: { name: station.name },
    })),
  };
}

function emptyFeatureCollection(): GeoJSON.FeatureCollection {
  return { type: "FeatureCollection", features: [] };
}

