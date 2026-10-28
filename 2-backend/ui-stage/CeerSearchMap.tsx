"use client";

import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import L, { type Map as LeafletMap, type PathOptions } from "leaflet";
import type { GeoJsonObject } from "geojson";
import type { SearchRegion } from "@/lib/ceerCampaign";
import {
  regionalSearchScores,
  saudiProvinceCode,
} from "@/lib/ceerCampaignAnalysis";

const MapContainer = dynamic(
  () => import("react-leaflet").then((module) => module.MapContainer),
  { ssr: false },
);
const GeoJSON = dynamic(
  () => import("react-leaflet").then((module) => module.GeoJSON),
  { ssr: false },
);

type GeoFeature = { properties?: Record<string, unknown> };
type GeoCollection = {
  type: "FeatureCollection";
  features?: GeoFeature[];
} & GeoJsonObject;
type Region = {
  score: number | null;
  name: string;
  keyword: string;
  code: string;
};

function scoreColor(score: number | null) {
  if (score === null) return "#e5ecee";
  if (score >= 80) return "#076b68";
  if (score >= 60) return "#178e88";
  if (score >= 40) return "#62bcb7";
  if (score >= 20) return "#aadbd8";
  return "#d8efed";
}

function featureCode(feature?: GeoFeature) {
  return saudiProvinceCode(feature?.properties);
}

function tooltip(region: Region) {
  const content = document.createElement("div");
  const name = document.createElement("strong");
  name.textContent = region.name;
  const score = document.createElement("span");
  score.textContent = `${region.keyword} · ${region.score?.toFixed(1) ?? "No data"}`;
  score.style.display = "block";
  score.style.marginTop = "3px";
  score.style.fontSize = "12px";
  content.append(name, score);
  return content;
}

export default function CeerSearchMap({ data }: { data: SearchRegion[] }) {
  const [geoData, setGeoData] = useState<GeoCollection | null>(null);
  const [map, setMap] = useState<LeafletMap | null>(null);
  const scoreByCode = useMemo(() => regionalSearchScores(data), [data]);

  useEffect(() => {
    let active = true;
    fetch("/saudi-arabia-provinces.json")
      .then((response) => response.json())
      .then((value: GeoCollection) => {
        if (active) setGeoData(value);
      })
      .catch(() => {
        if (active) setGeoData(null);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!geoData || !map) return;
    map.fitBounds(L.geoJSON(geoData).getBounds(), {
      padding: [18, 28],
      animate: false,
    });
  }, [geoData, map]);

  const geoJsonKey = useMemo(
    () =>
      [...scoreByCode.entries()]
        .map(([code, region]) => `${code}:${region.score.toFixed(2)}`)
        .sort()
        .join("|"),
    [scoreByCode],
  );
  const regionFor = (feature?: GeoFeature): Region => {
    const code = featureCode(feature);
    const score = scoreByCode.get(code);
    return {
      code,
      score: score?.score ?? null,
      name: score?.name ?? String(feature?.properties?.NAME_1 ?? "Province"),
      keyword: score?.keyword ?? "Search interest",
    };
  };
  const styleFeature = (feature?: GeoFeature): PathOptions => {
    const region = regionFor(feature);
    return {
      fillColor: scoreColor(region.score),
      fillOpacity: region.score === null ? 0.34 : 0.82,
      color: "#ffffff",
      weight: 1.4,
      opacity: 1,
    };
  };
  const onEachFeature = (feature: GeoFeature, layer: L.Layer) => {
    const path = layer as L.Path;
    const region = regionFor(feature);
    path.bindTooltip(tooltip(region), { sticky: true, direction: "top" });
    path.on({
      mouseover: () => {
        path.setStyle({ color: "#17333b", weight: 2.4, fillOpacity: 0.95 });
        path.bringToFront();
      },
      mouseout: () => path.setStyle(styleFeature(feature)),
      click: () => {
        if ("getBounds" in path && map)
          map.fitBounds((path as L.Polygon).getBounds(), {
            maxZoom: 9,
            padding: [24, 24],
            animate: true,
          });
      },
    });
  };

  return (
    <div className="ceer-search-map overflow-hidden rounded-2xl border border-[var(--ceer-line)] bg-[var(--ceer-soft)]">
      <MapContainer
        center={[23.8859, 45.0792]}
        zoom={5}
        minZoom={4}
        maxZoom={9}
        zoomControl={false}
        scrollWheelZoom={false}
        style={{ height: 540, width: "100%" }}
        ref={setMap}
        aria-label="Google Trends interest by Saudi province"
      >
        {geoData ? (
          <GeoJSON
            key={`${geoJsonKey}-${geoData.features?.length ?? 0}`}
            data={geoData}
            style={styleFeature}
            onEachFeature={onEachFeature}
          />
        ) : null}
      </MapContainer>
      <style jsx global>{`
        .ceer-search-map .leaflet-interactive {
          outline: none;
          transition:
            fill-opacity 160ms ease,
            stroke 160ms ease;
        }
        .ceer-search-map .leaflet-container {
          background: var(--ceer-soft);
          font-family: Inter, ui-sans-serif, system-ui, sans-serif;
        }
      `}</style>
    </div>
  );
}
