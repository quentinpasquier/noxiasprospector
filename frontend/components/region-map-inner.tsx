"use client";

import "leaflet/dist/leaflet.css";

import * as React from "react";
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMap } from "react-leaflet";
import L from "leaflet";

import deptData from "@/lib/dept-centroids.json";

type DeptId = keyof typeof deptData.departments;

const DEFAULT_CENTER: L.LatLngExpression = [
  deptData.default_center.lat,
  deptData.default_center.lon,
];
const DEFAULT_ZOOM = deptData.default_center.zoom;

type DeptStat = {
  id: string;
  count: number;
  lat: number;
  lon: number;
  label: string;
  city: string;
};

function computeDeptStats(selectedDepartments: string[]): DeptStat[] {
  const counts = new Map<string, number>();
  for (const dept of selectedDepartments) {
    counts.set(dept, (counts.get(dept) ?? 0) + 1);
  }
  const stats: DeptStat[] = [];
  for (const [id, count] of counts) {
    const meta = deptData.departments[id as DeptId];
    if (!meta) continue;
    stats.push({ id, count, lat: meta.lat, lon: meta.lon, label: meta.label, city: meta.city });
  }
  return stats;
}

function FitBounds({ stats }: { stats: DeptStat[] }): null {
  const map = useMap();
  React.useEffect(() => {
    if (stats.length === 0) {
      map.setView(DEFAULT_CENTER, DEFAULT_ZOOM);
      return;
    }
    const bounds = L.latLngBounds(stats.map((s) => [s.lat, s.lon]));
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 9 });
  }, [stats, map]);
  return null;
}

export function RegionMapInner({
  selectedDepartments,
}: {
  selectedDepartments: string[];
}): JSX.Element {
  const stats = React.useMemo(
    () => computeDeptStats(selectedDepartments),
    [selectedDepartments],
  );
  const maxCount = Math.max(1, ...stats.map((s) => s.count));

  return (
    <MapContainer
      center={DEFAULT_CENTER}
      zoom={DEFAULT_ZOOM}
      scrollWheelZoom
      className="h-full w-full"
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {stats.map((s) => {
        // 12 -> 32 px radius proportional to communes selected.
        const radius = 12 + Math.round((s.count / maxCount) * 20);
        return (
          <CircleMarker
            key={s.id}
            center={[s.lat, s.lon]}
            radius={radius}
            pathOptions={{
              color: "hsl(221 83% 53%)",
              fillColor: "hsl(221 83% 53%)",
              fillOpacity: 0.35,
              weight: 2,
            }}
          >
            <Tooltip direction="top" offset={[0, -8]} opacity={1} permanent>
              <div className="text-xs">
                <div className="font-semibold">
                  {s.label} ({s.id})
                </div>
                <div className="text-muted-foreground">
                  {s.count} commune{s.count > 1 ? "s" : ""}
                </div>
              </div>
            </Tooltip>
          </CircleMarker>
        );
      })}
      <FitBounds stats={stats} />
    </MapContainer>
  );
}
