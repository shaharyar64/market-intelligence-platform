"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  MapContainer,
  TileLayer,
  GeoJSON,
} from "react-leaflet";
import L, { PathOptions, Map as LeafletMap } from "leaflet";
import "leaflet/dist/leaflet.css";

/* =====================================================
   🧩 TYPES
===================================================== */

interface LocationItem {
  cluster?: string;
  zone?: string;
  sub_cluster?: string;
  country_code?: string;
  affluence_tier?: string;
  urban_lifecycle_stage?: string;
  population?: number;
  state?: string;
}

interface Props {
  data: LocationItem[];
  height?: string;
}

/* =====================================================
   🗺 COMPONENT
===================================================== */

export default function PopulationDensityMap({
  data,
  height = "800px",
}: Props) {
  const [geoData, setGeoData] = useState<any>(null);
  const mapRef = useRef<LeafletMap | null>(null);

  /* ==============================
     📦 Load GeoJSON
  ============================== */

  useEffect(() => {
    async function loadGeo() {
      const res = await fetch("/dubai.geojson");
      const json = await res.json();
      setGeoData(json);
    }
    loadGeo();
  }, []);

  /* ==============================
     🧠 Aggregate Zone Data
  ============================== */

  const zoneData = useMemo(() => {
    const map: Record<string, LocationItem[]> = {};

    data.forEach((item) => {
      if (!item.zone) return;

      const key = item.zone.toUpperCase().trim();

      if (!map[key]) {
        map[key] = [];
      }

      map[key].push(item);
    });

    return map;
  }, [data]);

  /* ==============================
     🎨 Density Color Scale
  ============================== */

  const getColor = (value: number) => {
    if (!value) return "#f3f4f6";
    if (value > 500000) return "#7f1d1d";
    if (value > 300000) return "#b91c1c";
    if (value > 150000) return "#ef4444";
    if (value > 80000) return "#f97316";
    if (value > 30000) return "#facc15";
    return "#84cc16";
  };

  /* ==============================
     🎨 Style Feature
  ============================== */

  const styleFeature = (feature: any): PathOptions => {
    const zoneName = feature.properties?.CNAME_E;
    const normalized = zoneName?.toUpperCase().trim();

    const items = zoneData[normalized] || [];
    const totalPopulation = items.reduce(
      (sum, item) => sum + (item.population || 0),
      0
    );

    return {
      fillColor: getColor(totalPopulation),
      weight: 1,
      color: "#111827",
      fillOpacity: 0.7,
    };
  };

  /* ==============================
     📊 Popup Per Zone
  ============================== */

  const onEachFeature = (feature: any, layer: L.Layer) => {
    const zoneName = feature.properties?.CNAME_E;
    const normalized = zoneName?.toUpperCase().trim();

    const items = zoneData[normalized] || [];

    const totalPopulation = items.reduce(
      (sum, item) => sum + (item.population || 0),
      0
    );

    const uniqueClusters = [
      ...new Set(items.map((i) => i.cluster).filter(Boolean)),
    ];

    const uniqueSubClusters = [
      ...new Set(items.map((i) => i.sub_cluster).filter(Boolean)),
    ];

    const uniqueAffluence = [
      ...new Set(items.map((i) => i.affluence_tier).filter(Boolean)),
    ];

    const uniqueLifecycle = [
      ...new Set(items.map((i) => i.urban_lifecycle_stage).filter(Boolean)),
    ];

    const uniqueStates = [
      ...new Set(items.map((i) => i.state).filter(Boolean)),
    ];

    const uniqueCountries = [
      ...new Set(items.map((i) => i.country_code).filter(Boolean)),
    ];

    layer.bindPopup(`
      <div style="font-size:13px; width:250px;">
        <strong style="font-size:14px;">${zoneName}</strong>
        <hr style="margin:6px 0;" />
        <div><strong>Total Population:</strong> ${totalPopulation.toLocaleString()}</div>
        <div><strong>Clusters:</strong> ${uniqueClusters.join(", ") || "-"}</div>
        <div><strong>Sub Clusters:</strong> ${uniqueSubClusters.join(", ") || "-"}</div>
        <div><strong>Affluence Tier:</strong> ${uniqueAffluence.join(", ") || "-"}</div>
        <div><strong>Urban Lifecycle:</strong> ${uniqueLifecycle.join(", ") || "-"}</div>
        <div><strong>State:</strong> ${uniqueStates.join(", ") || "-"}</div>
        <div><strong>Country:</strong> ${uniqueCountries.join(", ") || "-"}</div>
      </div>
    `);
  };

  /* ==============================
     🚀 Render
  ============================== */

  return (
    <div className="rounded-2xl overflow-hidden shadow-xl border border-slate-200 bg-white">
      <MapContainer
        ref={mapRef}
        center={[25.2048, 55.2708]}
        zoom={10}
        scrollWheelZoom
        style={{ height, width: "100%" }}
      >
        <TileLayer
          attribution="© OpenStreetMap contributors"
          url="https://{s}.tile.openstreetmap.de/{z}/{x}/{y}.png"
        />

        {geoData && (
          <GeoJSON
            data={geoData}
            style={styleFeature}
            onEachFeature={onEachFeature}
          />
        )}
      </MapContainer>
    </div>
  );
}