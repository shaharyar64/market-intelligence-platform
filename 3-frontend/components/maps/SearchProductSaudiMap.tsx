"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import L, { type PathOptions, type Map as LeafletMap } from "leaflet";
import "leaflet/dist/leaflet.css";
import type { GeoJSON as GeoJsonObject } from "leaflet";
import type { SearchProductMapItem } from "@/lib/digitalBrandHealth";

const MapContainer = dynamic(
  () => import("react-leaflet").then((module) => module.MapContainer),
  { ssr: false }
);

const TileLayer = dynamic(
  () => import("react-leaflet").then((module) => module.TileLayer),
  { ssr: false }
);

const GeoJSON = dynamic(
  () => import("react-leaflet").then((module) => module.GeoJSON),
  { ssr: false }
);

type GeoFeature = {
  properties?: Record<string, unknown>;
};

type GeoCollection = {
  type: "FeatureCollection";
  features?: GeoFeature[];
} & GeoJsonObject;

type Props = {
  data: SearchProductMapItem[];
  height?: string;
};

type CategoryScore = {
  category: string;
  score: number;
};

type RegionInfo = {
  code: string;
  name: string;
  score: number | null;
  categories: CategoryScore[];
};

function getScoreColor(score: number | null) {
  if (score === null) return "#e5e7eb";
  if (score >= 70) return "#166534";
  if (score >= 60) return "#16a34a";
  if (score >= 50) return "#84cc16";
  if (score >= 40) return "#facc15";
  if (score >= 30) return "#f97316";
  return "#ef4444";
}

function formatScore(score: number | null) {
  return score === null ? "No data" : score.toFixed(2);
}

function getRegionLabel(score: number | null) {
  if (score === null) return "No score available";
  if (score >= 70) return "Very strong";
  if (score >= 60) return "Strong";
  if (score >= 50) return "Healthy";
  if (score >= 40) return "Moderate";
  if (score >= 30) return "Developing";
  return "Low";
}

function normalizeName(value: unknown) {
  return String(value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]/gi, "")
    .toLowerCase();
}

const GEO_NAME_CODE_LOOKUP: Record<string, string> = {
  makkah: "SA-02",
  makka: "SA-02",
  makkahalmukarramah: "SA-02",
  mecca: "SA-02",
  almadinah: "SA-03",
  madinah: "SA-03",
  almadinahalmunawwarah: "SA-03",
  ashsharqiyah: "SA-04",
  eastern: "SA-04",
  easternprovince: "SA-04",
  alqassim: "SA-05",
  alquassim: "SA-05",
  qassim: "SA-05",
  qasim: "SA-05",
  algassi: "SA-05",
  hail: "SA-06",
  haiil: "SA-06",
  jizan: "SA-09",
  jazan: "SA-09",
  qizan: "SA-09",
};

function resolveFeatureCode(feature?: GeoFeature) {
  const isoCode = String(feature?.properties?.ISO_1 ?? "");
  if (/^SA-\d+$/i.test(isoCode)) return isoCode.toUpperCase();

  const names = [
    feature?.properties?.NAME_1,
    ...String(feature?.properties?.VARNAME_1 ?? "").split("|"),
  ];

  for (const name of names) {
    const code = GEO_NAME_CODE_LOOKUP[normalizeName(name)];
    if (code) return code;
  }

  return isoCode;
}

function buildPopupHtml(region: RegionInfo) {
  const color = getScoreColor(region.score);

  return `
    <div style="
      min-width: 210px;
      padding: 2px;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    ">
      <div style="
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:12px;
        margin-bottom:10px;
      ">
        <div>
          <div style="font-size:13px;font-weight:800;color:#0f172a;line-height:1.25;">
            ${region.name}
          </div>
          <div style="margin-top:3px;font-size:11px;font-weight:700;color:#64748b;">
            ${region.code}
          </div>
        </div>
        <div style="
          height:34px;
          min-width:54px;
          border-radius:12px;
          background:${color}1f;
          color:${color};
          display:flex;
          align-items:center;
          justify-content:center;
          font-size:16px;
          font-weight:900;
          border:1px solid ${color}40;
        ">
          ${formatScore(region.score)}
        </div>
      </div>
      <div style="
        height:7px;
        border-radius:999px;
        background:#e5e7eb;
        overflow:hidden;
      ">
        <div style="
          height:100%;
          width:${region.score === null ? 0 : Math.min(Math.max(region.score, 0), 100)}%;
          background:${color};
          border-radius:999px;
        "></div>
      </div>
      <div style="margin-top:9px;font-size:12px;font-weight:700;color:#334155;">
        ${getRegionLabel(region.score)} search index
      </div>
      ${
        region.categories.length > 0
          ? `
      <div style="margin-top:11px;padding-top:9px;border-top:1px solid #e5e7eb;">
        ${region.categories
          .map(
            (item) => `
        <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;padding:3px 0;">
          <span style="font-size:11.5px;font-weight:700;color:#334155;">${item.category}</span>
          <span style="font-size:11.5px;font-weight:800;color:#0f172a;">${item.score.toFixed(2)}</span>
        </div>`
          )
          .join("")}
      </div>`
          : ""
      }
    </div>
  `;
}

export default function SearchProductSaudiMap({
  data,
  height = "560px",
}: Props) {
  const [geoData, setGeoData] = useState<GeoCollection | null>(null);
  const mapRef = useRef<LeafletMap | null>(null);

  useEffect(() => {
    let active = true;

    fetch("/saudi-arabia-provinces.json")
      .then((response) => response.json())
      .then((json) => {
        if (!active) return;
        setGeoData(json);
      })
      .catch(() => {
        if (!active) return;
        setGeoData(null);
      });

    return () => {
      active = false;
    };
  }, []);

  const scoreByCode = useMemo(() => {
    const grouped = new Map<
      string,
      {
        total: number;
        count: number;
        name: string;
        categories: Map<string, { total: number; count: number }>;
      }
    >();

    data.forEach((item) => {
      if (!item.geo_code || !Number.isFinite(item.score)) return;
      const geoCode = item.geo_code.toUpperCase();

      const current = grouped.get(geoCode) ?? {
        total: 0,
        count: 0,
        name: item.geo_name,
        categories: new Map(),
      };
      current.total += item.score;
      current.count += 1;
      current.name = item.geo_name || current.name;

      const breakdownLabel = item.category || item.keyword;
      if (breakdownLabel) {
        const categoryStats = current.categories.get(breakdownLabel) ?? {
          total: 0,
          count: 0,
        };
        categoryStats.total += item.score;
        categoryStats.count += 1;
        current.categories.set(breakdownLabel, categoryStats);
      }

      grouped.set(geoCode, current);
    });

    const normalized = new Map<
      string,
      { score: number; name: string; categories: CategoryScore[] }
    >();
    grouped.forEach((value, key) => {
      const categories: CategoryScore[] = Array.from(
        value.categories.entries()
      )
        .map(([category, stats]) => ({
          category,
          score: stats.total / stats.count,
        }))
        .sort((a, b) => b.score - a.score);

      normalized.set(key, {
        score: value.total / value.count,
        name: value.name,
        categories,
      });
    });

    return normalized;
  }, [data]);

  const geoJsonKey = useMemo(
    () =>
      Array.from(scoreByCode.entries())
        .map(([code, item]) => `${code}:${item.score.toFixed(2)}`)
        .sort()
        .join("|"),
    [scoreByCode]
  );

  const styleFeature = (feature?: GeoFeature): PathOptions => {
    const code = resolveFeatureCode(feature);
    const region = scoreByCode.get(code);
    const score = region?.score ?? null;

    return {
      fillColor: getScoreColor(score),
      fillOpacity: score === null ? 0.28 : 0.78,
      color: "#ffffff",
      weight: 1.4,
      opacity: 1,
    };
  };

  const getRegionInfo = (feature: GeoFeature): RegionInfo => {
    const code = resolveFeatureCode(feature);
    const fallbackName = String(feature.properties?.NAME_1 ?? "Province");
    const region = scoreByCode.get(code);

    return {
      code,
      name: region?.name ?? fallbackName,
      score: region?.score ?? null,
      categories: region?.categories ?? [],
    };
  };

  const onEachFeature = (feature: GeoFeature, layer: L.Layer) => {
    const pathLayer = layer as L.Path;
    const region = getRegionInfo(feature);

    pathLayer.on({
      mouseover: () => {
        pathLayer.setStyle({
          fillOpacity: region.score === null ? 0.42 : 0.92,
          color: "#0f172a",
          weight: 2.4,
        });
        pathLayer.bringToFront();
      },
      mouseout: () => {
        pathLayer.setStyle(styleFeature(feature));
      },
      click: (event: L.LeafletMouseEvent) => {
        L.popup({
          closeButton: false,
          autoPan: true,
          className: "search-map-popup",
          offset: [0, -4],
        })
          .setLatLng(event.latlng)
          .setContent(buildPopupHtml(region))
          .openOn(event.target._map);

        if ("getBounds" in pathLayer && mapRef.current) {
          const bounds = (pathLayer as L.Polygon).getBounds();
          mapRef.current.fitBounds(bounds, {
            maxZoom: 6,
            padding: [28, 28],
            animate: true,
          });
        }
      },
    });
  };

  const topRegion = data
    .filter((item) => Number.isFinite(item.score))
    .sort((a, b) => b.score - a.score)[0];

  return (
    <div className="grid gap-6 lg:grid-cols-[1.55fr_0.45fr]">
      <div
        className="search-saudi-map overflow-hidden rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] shadow-sm"
        style={{ height }}
      >
        <MapContainer
          center={[23.8859, 45.0792]}
          zoom={5}
          minZoom={4}
          maxZoom={8}
          scrollWheelZoom={false}
          style={{ height: "100%", width: "100%" }}
          ref={mapRef}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {geoData && (
            <GeoJSON
              key={`${geoJsonKey}-${geoData.features?.length ?? 0}`}
              data={geoData}
              style={styleFeature}
              onEachFeature={onEachFeature}
            />
          )}
        </MapContainer>
      </div>

      <style jsx global>{`
        .search-saudi-map .leaflet-interactive {
          outline: none;
          transition:
            fill-opacity 160ms ease,
            stroke-width 160ms ease,
            stroke 160ms ease;
        }

        .search-saudi-map .leaflet-container {
          background: #eef6fb;
          font-family:
            Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
            "Segoe UI", sans-serif;
        }

        .search-map-popup .leaflet-popup-content-wrapper {
          border-radius: 16px;
          border: 1px solid rgba(148, 163, 184, 0.28);
          background: rgba(255, 255, 255, 0.94);
          box-shadow: 0 18px 46px rgba(15, 23, 42, 0.18);
          backdrop-filter: blur(14px);
        }

        .search-map-popup .leaflet-popup-content {
          margin: 12px;
        }

        .search-map-popup .leaflet-popup-tip {
          background: rgba(255, 255, 255, 0.94);
          box-shadow: 0 8px 22px rgba(15, 23, 42, 0.12);
        }
      `}</style>

      <div className="rounded-2xl border border-[var(--card-bd)] bg-[var(--card-bg-2)] p-5 shadow-sm">
        <p className="text-xs font-bold uppercase tracking-wide text-[var(--muted-tx)]">
          Top Region
        </p>
        <p className="mt-2 text-xl font-bold text-[var(--title-tx)]">
          {topRegion?.geo_name ?? "-"}
        </p>
        <p className="mt-1 text-sm font-semibold text-[var(--muted-tx)]">
          {topRegion ? `${topRegion.score.toFixed(2)} score` : "No map data"}
        </p>
        {(topRegion?.category || topRegion?.keyword) && (
          <p className="mt-1 text-xs font-semibold text-[var(--muted-tx)]">
            {topRegion.category || topRegion.keyword}
          </p>
        )}

        <div className="mt-6 space-y-3">
          {[
            ["70+", "#166534"],
            ["60-69", "#16a34a"],
            ["50-59", "#84cc16"],
            ["40-49", "#facc15"],
            ["30-39", "#f97316"],
            ["<30", "#ef4444"],
          ].map(([label, color]) => (
            <div key={label} className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span
                  className="h-3 w-3 rounded-full"
                  style={{ background: color }}
                />
                <span className="text-sm font-medium text-[var(--body-tx)]">
                  {label}
                </span>
              </div>
              <span className="text-xs font-semibold text-[var(--muted-tx)]">
                Score
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
