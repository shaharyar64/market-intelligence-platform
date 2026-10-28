"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import L, { PathOptions, Map as LeafletMap } from "leaflet";
import "leaflet/dist/leaflet.css";

/* ===============================
   SSR SAFE REACT LEAFLET IMPORTS
================================ */

const MapContainer = dynamic(
  () => import("react-leaflet").then((m) => m.MapContainer),
  { ssr: false }
);

const TileLayer = dynamic(
  () => import("react-leaflet").then((m) => m.TileLayer),
  { ssr: false }
);

const Marker = dynamic(
  () => import("react-leaflet").then((m) => m.Marker),
  { ssr: false }
);

const Popup = dynamic(
  () => import("react-leaflet").then((m) => m.Popup),
  { ssr: false }
);

const GeoJSON = dynamic(
  () => import("react-leaflet").then((m) => m.GeoJSON),
  { ssr: false }
);

/* =====================================================
   TYPES
===================================================== */

interface Restaurant {
  latitude: number;
  longitude: number;
  name: string;
  cuisine: string;
  rating: number | null;
  price_range: string | null;
  horeca_type: string | null;
  place_id: string;
  total_reviews: number | null;
  google_maps_url: string;
}

interface Props {
  data: Restaurant[];
  height?: string;
}

/* =====================================================
   RATING COLOR
===================================================== */

const getRatingColor = (rating?: number | null) => {
  if (!rating) return "#64748b";
  if (rating >= 4.5) return "#16a34a";
  if (rating >= 4) return "#84cc16";
  if (rating >= 3) return "#f59e0b";
  return "#ef4444";
};

/* =====================================================
   CREATE MARKER
===================================================== */

const createIcon = (rating?: number | null) =>
  new L.DivIcon({
    html: `
      <div style="
        background:#0f172a;
        width:36px;
        height:36px;
        border-radius:50%;
        display:flex;
        align-items:center;
        justify-content:center;
        color:white;
        font-size:16px;
        border:4px solid ${getRatingColor(rating)};
        box-shadow:0 6px 14px rgba(0,0,0,0.25);
      ">
        🍽️
      </div>
    `,
    className: "",
    iconSize: [36, 36],
    iconAnchor: [18, 36],
  });

/* =====================================================
   COMPONENT
===================================================== */

export default function HorecaMap({
  data,
  height = "750px",
}: Props) {
  const [geoData, setGeoData] = useState<any>(null);
  const mapRef = useRef<LeafletMap | null>(null);

  /* ==============================
     LOAD RIYADH GEOJSON
  ============================== */

  useEffect(() => {
    async function loadGeo() {
      try {
        const res = await fetch("/riyadh.geojson");
        const json = await res.json();
        setGeoData(json);
      } catch (err) {
        console.error("Failed to load GeoJSON", err);
      }
    }

    loadGeo();
  }, []);

  /* ==============================
     VALID DATA
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
     MAP CENTER
  ============================== */

  const first = validData[0];

  const center: [number, number] = first
    ? [first.latitude, first.longitude]
    : [24.7136, 46.6753];

  /* ==============================
     DISTRICT STYLE
  ============================== */

  const styleFeature = (): PathOptions => ({
    color: "#0f172a",
    weight: 1.5,
    dashArray: "4 4",
    fillOpacity: 0.05,
  });

  /* ==============================
     SSR SAFETY
  ============================== */

  if (typeof window === "undefined") return null;

  /* ==============================
     RENDER
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
          <GeoJSON data={geoData} style={styleFeature} />
        )}

        {validData.map((item) => {
          const icon = createIcon(item.rating);

          return (
            <Marker
              key={item.place_id}
              position={[item.latitude, item.longitude]}
              icon={icon}
            >
              <Popup>
                <div className="w-[250px] space-y-2">
                  <h3 className="font-semibold text-slate-900 text-sm">
                    📌 {item.name}
                  </h3>

                  <div>
                    <span className="font-mono font-bold">
                      Cuisine:
                    </span>{" "}
                    <span className="text-xs text-slate-500 capitalize">
                      {item.cuisine}
                    </span>
                  </div>

                  {item.horeca_type && (
                    <div>
                      <span className="font-mono font-bold">
                        Type:
                      </span>{" "}
                      <span className="text-xs text-slate-500">
                        {item.horeca_type}
                      </span>
                    </div>
                  )}

                  {item.price_range && (
                    <div>
                      <span className="font-mono font-bold">
                        Price:
                      </span>{" "}
                      <span className="text-xs text-slate-500">
                        {item.price_range}
                      </span>
                    </div>
                  )}

                  {typeof item.total_reviews === "number" && (
                    <div>
                      <span className="font-mono font-bold">
                        Reviews:
                      </span>{" "}
                      <span className="text-xs text-slate-500">
                        {item.total_reviews}
                      </span>
                    </div>
                  )}

                  {item.rating !== null && (
                    <div>
                      <span className="font-mono font-bold">
                        Rating:
                      </span>{" "}
                      <span
                        className="text-xs font-semibold"
                        style={{
                          color: getRatingColor(item.rating),
                        }}
                      >
                        ⭐ {item.rating} / 5
                      </span>
                    </div>
                  )}

                  {item.google_maps_url && (
                    <a
                      href={item.google_maps_url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <button className="bg-[#0f172a] text-white px-2 py-1 rounded text-xs w-full cursor-pointer">
                        Visit on Google Maps
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