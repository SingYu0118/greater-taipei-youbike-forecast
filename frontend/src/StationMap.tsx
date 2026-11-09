import { useEffect, useRef } from "react";
import {
  AttributionControl,
  Map as MapLibreMap,
  NavigationControl,
  type ExpressionSpecification,
  type GeoJSONSource,
  type MapGeoJSONFeature,
  type MapLayerMouseEvent,
} from "maplibre-gl";
import type { Station } from "./types";

type Props = {
  stations: Station[];
  selectedId?: string;
  onSelect: (station: Station) => void;
};

const mapStyle = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

export default function StationMap({ stations, selectedId, onSelect }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MapLibreMap | null>(null);
  const onSelectRef = useRef(onSelect);
  const stationIndex = useRef(new Map<string, Station>());
  stationIndex.current = new Map(stations.map((station) => [station.station_id, station]));

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
        const station = feature?.properties?.station_id
          ? stationIndex.current.get(feature.properties.station_id)
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
    const station = stationIndex.current.get(selectedId ?? "");
    if (station && map.current) {
      map.current.easeTo({ center: [station.longitude, station.latitude], zoom: 14, duration: 700 });
    }
  }, [selectedId]);

  return <div className="map" ref={container} aria-label="Interactive YouBike station map" />;
}

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
        station_id: station.station_id,
        ratio: station.capacity ? station.available_bikes / station.capacity : 0,
      },
    })),
  };
}

