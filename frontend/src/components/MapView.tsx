import { cellToBoundary } from "h3-js";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useMemo, useRef, useState } from "react";
import type { DriverPos, Ride, Zone } from "../types";

const CENTER: [number, number] = [77.5946, 12.9716];
const STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

type FC = { type: "FeatureCollection"; features: any[] };
const EMPTY: FC = { type: "FeatureCollection", features: [] };

const SURGE_COLOR: any = [
  "interpolate", ["linear"], ["get", "surge"],
  1, "#1d4e89", 1.4, "#f2c94c", 2.2, "#f2994a", 3.2, "#eb5757", 4, "#b3123c",
];
const DRIVER_COLOR: any = [
  "match", ["get", "status"],
  "available", "#3ddc97", "busy", "#4dabf7", "offline", "#6c757d", "stale", "#495057", "#adb5bd",
];
const RIDE_COLOR: any = [
  "match", ["get", "status"],
  "QUOTED", "#ff6b9d", "MATCHING", "#ff6b9d", "ASSIGNED", "#ffd43b",
  "DRIVER_EN_ROUTE", "#ffd43b", "DRIVER_ARRIVED", "#b197fc", "#ffffff",
];

type Props = {
  zones: Zone[];
  drivers: DriverPos[];
  rides: Ride[];
  selectedZone: string | null;
  selectedRide: string | null;
  onSelectZone: (id: string) => void;
  onSelectRide: (id: string) => void;
};

export function MapView({ zones, drivers, rides, selectedZone, selectedRide, onSelectZone, onSelectRide }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [ready, setReady] = useState(false);
  const handlers = useRef({ onSelectZone, onSelectRide });
  handlers.current = { onSelectZone, onSelectRide }; // always the latest callbacks

  // ---- turn data into GeoJSON (the format the map understands) ----
  const zonesFC = useMemo<FC>(
    () => ({
      type: "FeatureCollection",
      features: zones.map((z) => {
        const ring = cellToBoundary(z.h3_id, true); // [lng, lat] pairs
        return {
          type: "Feature",
          properties: { id: z.h3_id, surge: z.surge_multiplier },
          geometry: { type: "Polygon", coordinates: [[...ring, ring[0]]] },
        };
      }),
    }),
    [zones],
  );

  const driversFC = useMemo<FC>(
    () => ({
      type: "FeatureCollection",
      features: drivers.map((d) => ({
        type: "Feature",
        properties: { status: d.status },
        geometry: { type: "Point", coordinates: [d.longitude, d.latitude] },
      })),
    }),
    [drivers],
  );

  const { pickupsFC, routesFC } = useMemo(() => {
    const byId = new Map(drivers.map((d) => [d.driver_id, d]));
    const pickups: any[] = [];
    const routes: any[] = [];
    for (const r of rides) {
      if (r.status !== "IN_PROGRESS") {
        pickups.push({
          type: "Feature",
          properties: { id: r.ride_id, status: r.status },
          geometry: { type: "Point", coordinates: [r.pickup_lng, r.pickup_lat] },
        });
      }
      const drv = r.driver_id ? byId.get(r.driver_id) : undefined;
      if (!drv) continue;
      let target: [number, number] | null = null;
      if (r.status === "ASSIGNED" || r.status === "DRIVER_EN_ROUTE") target = [r.pickup_lng, r.pickup_lat];
      else if (r.status === "IN_PROGRESS") target = [r.dest_lng, r.dest_lat];
      if (target) {
        routes.push({
          type: "Feature",
          properties: { id: r.ride_id },
          geometry: { type: "LineString", coordinates: [[drv.longitude, drv.latitude], target] },
        });
      }
    }
    return {
      pickupsFC: { type: "FeatureCollection", features: pickups } as FC,
      routesFC: { type: "FeatureCollection", features: routes } as FC,
    };
  }, [rides, drivers]);

  // ---- create the map once ----
  useEffect(() => {
    const map = new maplibregl.Map({
      container: container.current!,
      style: STYLE,
      center: CENTER,
      zoom: 11.3,
      attributionControl: { compact: true },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-left");

    map.on("load", () => {
      for (const name of ["zones", "routes", "drivers", "pickups"]) {
        map.addSource(name, { type: "geojson", data: EMPTY as any });
      }
      map.addLayer({ id: "zones-fill", type: "fill", source: "zones", paint: { "fill-color": SURGE_COLOR, "fill-opacity": 0.42 } });
      map.addLayer({ id: "zones-line", type: "line", source: "zones", paint: { "line-color": "#ffffff", "line-opacity": 0.14, "line-width": 1 } });
      map.addLayer({
        id: "zones-selected", type: "line", source: "zones",
        filter: ["==", ["get", "id"], ""] as any,
        paint: { "line-color": "#ffffff", "line-width": 2.5 },
      });
      map.addLayer({
        id: "routes", type: "line", source: "routes",
        paint: { "line-color": "#ffd43b", "line-width": 2, "line-dasharray": [2, 2] },
      });
      map.addLayer({
        id: "drivers", type: "circle", source: "drivers",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, 3, 15, 7] as any,
          "circle-color": DRIVER_COLOR, "circle-stroke-color": "#0b0f14", "circle-stroke-width": 1,
        },
      });
      map.addLayer({
        id: "pickups", type: "circle", source: "pickups",
        paint: { "circle-radius": 6, "circle-color": RIDE_COLOR, "circle-stroke-color": "#ffffff", "circle-stroke-width": 1.5 },
      });
      map.addLayer({
        id: "pickups-selected", type: "circle", source: "pickups",
        filter: ["==", ["get", "id"], ""] as any,
        paint: { "circle-radius": 12, "circle-color": "rgba(0,0,0,0)", "circle-stroke-color": "#ffffff", "circle-stroke-width": 2 },
      });

      map.on("click", "zones-fill", (e) => {
        if (map.queryRenderedFeatures(e.point, { layers: ["pickups"] }).length) return; // a ride was clicked instead
        const id = e.features?.[0]?.properties?.id;
        if (id) handlers.current.onSelectZone(id);
      });
      map.on("click", "pickups", (e) => {
        const id = e.features?.[0]?.properties?.id;
        if (id) handlers.current.onSelectRide(id);
      });
      for (const layer of ["zones-fill", "pickups"]) {
        map.on("mouseenter", layer, () => (map.getCanvas().style.cursor = "pointer"));
        map.on("mouseleave", layer, () => (map.getCanvas().style.cursor = ""));
      }
      setReady(true);
    });

    mapRef.current = map;
    return () => map.remove();
  }, []);

  // ---- push new data into the map ----
  const push = (name: string, data: FC) =>
    (mapRef.current?.getSource(name) as maplibregl.GeoJSONSource | undefined)?.setData(data as any);

  useEffect(() => { if (ready) push("zones", zonesFC); }, [ready, zonesFC]);
  useEffect(() => { if (ready) push("drivers", driversFC); }, [ready, driversFC]);
  useEffect(() => { if (ready) push("pickups", pickupsFC); }, [ready, pickupsFC]);
  useEffect(() => { if (ready) push("routes", routesFC); }, [ready, routesFC]);
  useEffect(() => {
    if (!ready) return;
    mapRef.current?.setFilter("zones-selected", ["==", ["get", "id"], selectedZone ?? ""] as any);
    mapRef.current?.setFilter("pickups-selected", ["==", ["get", "id"], selectedRide ?? ""] as any);
  }, [ready, selectedZone, selectedRide]);

  return <div ref={container} className="map" />;
}