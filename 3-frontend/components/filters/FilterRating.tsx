"use client";

interface Props {
  label: string;
  min: number;
  max: number;
  value: number;
  onChange: (value: number) => void;
}

export default function FilterRating({ label, min, max, value, onChange }: Props) {
  return (
    <div
      style={{ background: "var(--card-bg-2)", border: "1px solid var(--card-bd)", backdropFilter: "var(--blur)", WebkitBackdropFilter: "var(--blur)" }}
      className="flex flex-col gap-3 p-4 rounded-xl shadow-lg"
    >
      <label style={{ color: "var(--body-tx)" }} className="text-sm">
        {label}:{" "}
        <span style={{ color: "var(--title-tx)" }} className="font-semibold">
          {value}+
        </span>
      </label>
      <input
        type="range"
        min={min}
        max={max}
        step={0.5}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full cursor-pointer accent-blue-500"
      />
    </div>
  );
}
