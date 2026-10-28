"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  GeoJSON,
} from "react-leaflet";
import L, { PathOptions, Map as LeafletMap } from "leaflet";
import "leaflet/dist/leaflet.css";

/* =====================================================
   🧩 TYPES
===================================================== */

interface LocationItem {
  title: string;
  category: string;
  latitude: number | string | null;
  longitude: number | string | null;
  cluster?: string;
  zone?: string;
  sub_cluster?: string;
  country_code?: string;
  affluence_tier?: string;
  urban_lifecycle_stage?: string;
  population?: number;
  state?: string;
  link?: string;

  total_reviews?: number | null;
  sentiment_score?: number | null; // may be null from DB
}

interface Props {
  data: LocationItem[];
  selectedZone?: string;
  height?: string;
}

/* =====================================================
   🎨 SENTIMENT COLOR (1–5 scale assumed)
===================================================== */

const getSentimentColor = (score?: number | null) => {
  if (typeof score !== "number") return "#64748b"; // gray (no reviews)
  if (score >= 4) return "#16a34a"; // strong positive
  if (score >= 3) return "#84cc16"; // mild positive
  if (score >= 2) return "#f59e0b"; // neutral
  return "#ef4444"; // negative
};

/* =====================================================
   🏦 CATEGORY BASE STYLE
===================================================== */

const getCategoryBase = (category: string) => {
  const cat = category?.toLowerCase();

  if (cat?.includes("atm"))
    return { color: "#10b981", emoji: "💳" };

  if (cat?.includes("exchange"))
    return { color: "#f59e0b", emoji: "💱" };

  return { color: "#2563eb", emoji: "🏦" };
};

/* =====================================================
   🎯 CREATE MARKER ICON
===================================================== */

const createIcon = (
  fillColor: string,
  emoji: string,
  borderColor: string
) =>
  new L.DivIcon({
    html: `
      <div style="
        background:${fillColor};
        width:38px;
        height:38px;
        border-radius:50%;
        display:flex;
        align-items:center;
        justify-content:center;
        color:white;
        font-size:17px;
        box-shadow:0 6px 14px rgba(0,0,0,0.25);
        border:4px solid ${borderColor};
      ">
        ${emoji}
      </div>
    `,
    className: "",
    iconSize: [38, 38],
    iconAnchor: [19, 38],
  });

/* =====================================================
   🗺 COMPONENT
===================================================== */

export default function LocationMap({
  data,
  selectedZone,
  height = "800px",
}: Props) {
  const [geoData, setGeoData] = useState<any>(null);

  const mapRef = useRef<LeafletMap | null>(null);
  const geoJsonRef = useRef<L.GeoJSON>(null);

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
     ✅ Filter Valid Coordinates
  ============================== */

  const validData = useMemo(() => {
    return data.filter(
      (item) =>
        item.latitude !== null &&
        item.longitude !== null &&
        !isNaN(Number(item.latitude)) &&
        !isNaN(Number(item.longitude))
    );
  }, [data]);

  /* ==============================
     📍 Center Logic
  ============================== */

  const firstValid = validData[0];

  const center: [number, number] = firstValid
    ? [Number(firstValid.latitude), Number(firstValid.longitude)]
    : [25.2048, 55.2708]; // Dubai fallback

  /* ==============================
     🎨 Boundary Coloring
  ============================== */

  const colorMap = useMemo(() => {
    if (!geoData?.features) return {};

    const colors = [
      "#2563eb",
      "#9333ea",
      "#f59e0b",
      "#10b981",
      "#ef4444",
      "#06b6d4",
      "#f43f5e",
      "#84cc16",
    ];

    const map: Record<string, string> = {};
    let index = 0;

    geoData.features.forEach((feature: any) => {
      const name = feature.properties?.CNAME_E;
      if (name && !map[name]) {
        map[name] = colors[index % colors.length];
        index++;
      }
    });

    return map;
  }, [geoData]);

  const styleFeature = (feature: any): PathOptions => {
    const name = feature.properties?.CNAME_E;

    return {
      color: colorMap[name] || "#2563eb",
      weight: 2,
      dashArray: "4 4",
      fillOpacity: 0.05,
    };
  };

  /* ==============================
     🎯 Highlight Selected Zone
  ============================== */

  useEffect(() => {
    if (!geoJsonRef.current || !mapRef.current) return;

    const map = mapRef.current;
    let selectedLayer: any = null;

    geoJsonRef.current.eachLayer((layer: any) => {
      const featureName = layer.feature?.properties?.CNAME_E;

      layer.setStyle({
        weight: 2,
        color: colorMap[featureName] || "#2563eb",
        fillOpacity: 0.05,
        dashArray: "4 4",
      });

      if (
        selectedZone &&
        featureName?.toUpperCase().trim() ===
          selectedZone.toUpperCase().trim()
      ) {
        selectedLayer = layer;
      }
    });

    if (selectedLayer) {
      selectedLayer.setStyle({
        weight: 5,
        color: "#000",
        fillColor:
          colorMap[selectedLayer.feature?.properties?.CNAME_E] ||
          "#2563eb",
        fillOpacity: 0.4,
        dashArray: undefined,
      });

      map.flyToBounds(selectedLayer.getBounds(), {
        padding: [60, 60],
        duration: 1.6,
      });
    }
  }, [selectedZone, colorMap]);

  /* ==============================
     🚀 Render
  ============================== */

  return (
    <div className="rounded-2xl overflow-hidden shadow-xl border border-slate-200 bg-white">
      <MapContainer
        ref={mapRef}
        center={center}
        zoom={11}
        scrollWheelZoom
        style={{ height, width: "100%" }}
      >
        <TileLayer
          attribution="© OpenStreetMap contributors"
          url="https://{s}.tile.openstreetmap.de/{z}/{x}/{y}.png"
        />

        {geoData && (
          <GeoJSON
            ref={geoJsonRef}
            data={geoData}
            style={styleFeature}
          />
        )}

        {validData.map((item, index) => {
          const { color, emoji } = getCategoryBase(
            item.category
          );

          const icon = createIcon(
            color,
            emoji,
            getSentimentColor(item.sentiment_score)
          );

          const hasSentiment =
            typeof item.sentiment_score === "number";

          return (
            <Marker
              key={index}
              position={[
                Number(item.latitude),
                Number(item.longitude),
              ]}
              icon={icon}
            >
              <Popup>
                <div className="w-[250px] space-y-2">
                  <h3 className="font-semibold text-slate-900 text-sm">
                    📌 {item.title}
                  </h3>

                  <div>
                    <span className="font-mono font-bold">
                      Category:{" "}
                    </span>
                    <span className="text-xs text-slate-500 capitalize">
                      {item.category}
                    </span>
                  </div>

                  {item.zone && (
                    <div>
                      <span className="font-mono font-bold">
                        Zone:{" "}
                      </span>
                      <span className="text-xs text-slate-500">
                        {item.zone}
                      </span>
                    </div>
                  )}

                  {item.population && (
                    <div>
                      <span className="font-mono font-bold">
                        Population:{" "}
                      </span>
                      <span className="text-xs text-slate-500">
                        {item.population.toLocaleString()}
                      </span>
                    </div>
                  )}

                  {typeof item.total_reviews === "number" && (
                    <div>
                      <span className="font-mono font-bold">
                        Reviews:{" "}
                      </span>
                      <span className="text-xs text-slate-500">
                        {item.total_reviews}
                      </span>
                    </div>
                  )}

                  {hasSentiment ? (
                    <div>
                      <span className="font-mono font-bold">
                        Sentiment:{" "}
                      </span>
                      <span
                        className="text-xs font-semibold"
                        style={{
                          color: getSentimentColor(
                            item.sentiment_score
                          ),
                        }}
                      >
                        {item.sentiment_score!.toFixed(2)} / 5
                      </span>
                    </div>
                  ) : (
                    <div className="text-xs text-slate-400 italic">
                      No reviews yet
                    </div>
                  )}

                  {item.link && (
                    <a
                      href={item.link}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <button className="bg-[#0f172a] text-white px-2 py-1 rounded text-xs w-full cursor-pointer">
                        Visit
                      </button>
                    </a>
                  )}
                </div>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>
    </div>
  );
}