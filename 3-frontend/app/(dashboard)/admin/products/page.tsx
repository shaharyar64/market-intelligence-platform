"use client";

import { useEffect, useState } from "react";
import DashboardTopbar from "@/components/layout/DashboardTopbar";
import { getMe, getProducts, createProduct, updateProduct, type Product } from "@/lib/user";
import { LayoutGrid, Plus, Search, Loader2, X, Lock, Pencil, Hash } from "lucide-react";

/* ─── modal ──────────────────────────────────────────────────────────── */
function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.45)", backdropFilter: "blur(4px)" }}>
      <div className="w-full max-w-md max-h-[85vh] rounded-2xl shadow-2xl flex flex-col" style={{ background: "var(--dropdown-bg)", border: "1px solid var(--card-bd)" }}>
        <div className="flex items-center justify-between px-6 pt-6 pb-5 flex-shrink-0" style={{ background: "var(--dropdown-bg)" }}>
          <h2 style={{ color: "var(--title-tx)" }} className="text-base font-semibold">{title}</h2>
          <button onClick={onClose} style={{ color: "var(--muted-tx)" }} className="hover:text-red-500 transition-colors"><X size={18} /></button>
        </div>
        <div className="px-6 pb-6 overflow-y-auto">
          {children}
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mb-4">
      <label style={{ color: "var(--muted-tx)" }} className="block text-xs font-medium mb-1.5">{label}</label>
      {children}
    </div>
  );
}

function Input({ style, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input {...props}
      style={{ background: "var(--dropdown-bg-2)", border: "1px solid var(--card-bd)", color: "var(--title-tx)", ...style }}
      className="w-full px-3 py-2.5 rounded-xl text-sm outline-none focus:border-blue-500 transition-colors placeholder:text-[var(--muted-tx)] disabled:opacity-50"
    />
  );
}

type Form = { key: string; label: string; tagline: string; icon: string; color: string; sort_order: string; is_active?: boolean };

const EMPTY: Form = { key: "", label: "", tagline: "", icon: "", color: "", sort_order: "0", is_active: true };

/* ─── product card ───────────────────────────────────────────────────── */
function ProductCard({ product, onEdit }: { product: Product; onEdit: (p: Product) => void }) {
  return (
    <div className="chart-card rounded-2xl p-5 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
          style={{ background: product.color || "rgba(99,102,241,0.12)" }}
        >
          <LayoutGrid size={18} style={{ color: product.color ? "#fff" : "#6366f1" }} />
        </div>
        <div className="flex items-center gap-2">
          <span style={{ background: "#ede9fe", color: "#6d28d9" }} className="text-xs font-semibold px-2 py-0.5 rounded-full">{product.key}</span>
          <button
            onClick={() => onEdit(product)}
            style={{ color: "var(--muted-tx)" }}
            className="hover:text-indigo-500 transition-colors p-1 rounded-lg hover:bg-[var(--card-bg-2)]"
          >
            <Pencil size={13} />
          </button>
        </div>
      </div>

      <div>
        <h3 style={{ color: "var(--title-tx)" }} className="font-semibold text-sm mb-1">{product.label}</h3>
        {product.tagline && <p style={{ color: "var(--muted-tx)" }} className="text-xs leading-relaxed">{product.tagline}</p>}
        {!product.tagline && <p style={{ color: "var(--muted-tx)" }} className="text-xs italic opacity-60">No tagline set — using frontend default</p>}
      </div>

      <div className="flex items-center gap-2 mt-auto pt-3" style={{ borderTop: "1px solid var(--card-bd)" }}>
        <Hash size={11} style={{ color: "var(--muted-tx)" }} />
        <span style={{ color: "var(--muted-tx)" }} className="text-xs">Order {product.sort_order}</span>
        {product.is_active === false && (
          <span style={{ background: "#fee2e2", color: "#b91c1c" }} className="text-[10px] font-semibold px-2 py-0.5 rounded-full ml-auto">Inactive</span>
        )}
      </div>
    </div>
  );
}

/* ─── page ───────────────────────────────────────────────────────────── */
export default function AdminProductsPage() {
  const [authorized, setAuthorized] = useState<boolean | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [editProduct, setEditProduct] = useState<Product | null>(null);
  const [form, setForm] = useState<Form>(EMPTY);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const load = () => getProducts().then((p) => setProducts(p.sort((a, b) => a.sort_order - b.sort_order))).catch(() => {});

  useEffect(() => {
    getMe()
      .then((me) => {
        if (me.role?.toUpperCase() !== "ADMIN") { setAuthorized(false); setLoading(false); return; }
        setAuthorized(true);
        setLoading(true);
        load().finally(() => setLoading(false));
      })
      .catch(() => { setAuthorized(false); setLoading(false); });
  }, []);

  const filtered = products.filter((p) =>
    p.label.toLowerCase().includes(search.toLowerCase()) ||
    p.key.toLowerCase().includes(search.toLowerCase())
  );

  const openEdit = (product: Product) => {
    setEditProduct(product);
    setForm({
      key: product.key,
      label: product.label,
      tagline: product.tagline ?? "",
      icon: product.icon ?? "",
      color: product.color ?? "",
      sort_order: String(product.sort_order),
      is_active: product.is_active ?? true,
    });
    setError("");
  };

  const handleEdit = async () => {
    if (!editProduct || !form.label) { setError("Label is required."); return; }
    setSaving(true); setError("");
    try {
      await updateProduct(editProduct.id, {
        label: form.label,
        tagline: form.tagline || undefined,
        icon: form.icon || undefined,
        color: form.color || undefined,
        sort_order: Number(form.sort_order) || 0,
        is_active: form.is_active,
      });
      await load();
      setEditProduct(null);
      setForm(EMPTY);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to update product");
    } finally { setSaving(false); }
  };

  const handleCreate = async () => {
    if (!form.key || !form.label) { setError("Key and label are required."); return; }
    setSaving(true); setError("");
    try {
      await createProduct({
        key: form.key,
        label: form.label,
        tagline: form.tagline || undefined,
        icon: form.icon || undefined,
        color: form.color || undefined,
        sort_order: Number(form.sort_order) || 0,
      });
      await load();
      setCreateOpen(false);
      setForm(EMPTY);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create product");
    } finally { setSaving(false); }
  };

  if (authorized === false) {
    return (
      <div className="w-full bg-transparent min-h-full">
        <DashboardTopbar title="Admin Panel" />
        <div className="flex flex-col items-center justify-center min-h-[70vh] gap-4">
          <div className="w-16 h-16 rounded-2xl flex items-center justify-center" style={{ background: "#fee2e2" }}>
            <Lock size={28} style={{ color: "#dc2626" }} />
          </div>
          <h2 style={{ color: "var(--title-tx)" }} className="text-xl font-bold">Access Denied</h2>
          <p style={{ color: "var(--muted-tx)" }} className="text-sm text-center max-w-xs">
            You need Admin privileges to access this page.
          </p>
        </div>
      </div>
    );
  }

  if (authorized === null) {
    return (
      <div className="w-full bg-transparent min-h-full">
        <DashboardTopbar title="Admin Panel" />
        <div className="flex items-center justify-center min-h-[70vh]">
          <Loader2 size={28} style={{ color: "var(--muted-tx)" }} className="animate-spin" />
        </div>
      </div>
    );
  }

  return (
    <div className="w-full bg-transparent min-h-full">
      <DashboardTopbar title="Admin Panel" />
      <div className="p-8">

        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 style={{ color: "var(--title-tx)" }} className="text-2xl font-bold">Products</h1>
            <p style={{ color: "var(--muted-tx)" }} className="text-sm mt-1">
              {products.length} product{products.length !== 1 ? "s" : ""} — the main categories services are grouped under on the landing page
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search size={14} style={{ color: "var(--muted-tx)" }} className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search products…"
                style={{ background: "var(--card-bg)", border: "1px solid var(--card-bd)", color: "var(--title-tx)", backdropFilter: "var(--blur)" }}
                className="pl-9 pr-4 py-2 rounded-xl text-sm outline-none focus:border-blue-500 placeholder:text-[var(--muted-tx)] w-52"
              />
            </div>
            <button
              onClick={() => { setCreateOpen(true); setForm(EMPTY); setError(""); }}
              className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 transition-colors"
            >
              <Plus size={15} /> New Product
            </button>
          </div>
        </div>

        {/* Grid */}
        {loading ? (
          <div className="flex items-center justify-center py-32"><Loader2 style={{ color: "var(--muted-tx)" }} className="animate-spin" size={28} /></div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-32 gap-3">
            <LayoutGrid size={40} style={{ color: "var(--card-bd)" }} />
            <p style={{ color: "var(--muted-tx)" }} className="text-sm">{search ? "No products match your search" : "No products yet — create your first one"}</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {filtered.map((p) => <ProductCard key={p.id} product={p} onEdit={openEdit} />)}
          </div>
        )}
      </div>

      {/* ── Edit Product Modal ── */}
      {editProduct && (
        <Modal title="Edit Product" onClose={() => { setEditProduct(null); setForm(EMPTY); setError(""); }}>
          {error && <p className="text-red-500 text-xs mb-4 bg-red-50 rounded-lg px-3 py-2">{error}</p>}
          <Field label="Key (immutable)"><Input value={form.key} disabled /></Field>
          <Field label="Label *"><Input placeholder="e.g. BrandIQ" value={form.label} onChange={(e) => setForm((p) => ({ ...p, label: e.target.value }))} /></Field>
          <Field label="Tagline">
            <textarea
              placeholder="Short description shown under the product name…"
              value={form.tagline} onChange={(e) => setForm((p) => ({ ...p, tagline: e.target.value }))} rows={2}
              style={{ background: "var(--dropdown-bg-2)", border: "1px solid var(--card-bd)", color: "var(--title-tx)" }}
              className="w-full px-3 py-2.5 rounded-xl text-sm outline-none focus:border-blue-500 resize-none placeholder:text-[var(--muted-tx)]"
            />
          </Field>
          <Field label="Icon key"><Input placeholder="e.g. bar-chart" value={form.icon} onChange={(e) => setForm((p) => ({ ...p, icon: e.target.value }))} /></Field>
          <Field label="Color (hex)"><Input placeholder="#6d28d9" value={form.color} onChange={(e) => setForm((p) => ({ ...p, color: e.target.value }))} /></Field>
          <Field label="Sort order"><Input type="number" value={form.sort_order} onChange={(e) => setForm((p) => ({ ...p, sort_order: e.target.value }))} /></Field>
          <div className="flex items-center gap-2 mb-4">
            <input
              type="checkbox"
              checked={form.is_active ?? true}
              onChange={(e) => setForm((p) => ({ ...p, is_active: e.target.checked }))}
              className="w-4 h-4 rounded cursor-pointer"
            />
            <label style={{ color: "var(--muted-tx)" }} className="text-xs font-medium cursor-pointer">Active</label>
          </div>
          <div className="flex gap-3 mt-6">
            <button onClick={() => { setEditProduct(null); setForm(EMPTY); setError(""); }} style={{ color: "var(--muted-tx)", border: "1px solid var(--card-bd)" }} className="flex-1 py-2.5 rounded-xl text-sm hover:bg-[var(--card-bg-2)] transition-colors">Cancel</button>
            <button onClick={handleEdit} disabled={saving} className="flex-1 py-2.5 rounded-xl text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 transition-colors flex items-center justify-center gap-2">
              {saving && <Loader2 size={14} className="animate-spin" />} Save Changes
            </button>
          </div>
        </Modal>
      )}

      {/* ── Create Product Modal ── */}
      {createOpen && (
        <Modal title="Create New Product" onClose={() => setCreateOpen(false)}>
          {error && <p className="text-red-500 text-xs mb-4 bg-red-50 rounded-lg px-3 py-2">{error}</p>}
          <Field label="Key * (immutable slug, e.g. &quot;visualiq&quot;)"><Input placeholder="e.g. visualiq" value={form.key} onChange={(e) => setForm((p) => ({ ...p, key: e.target.value }))} /></Field>
          <Field label="Label *"><Input placeholder="e.g. VisualIQ" value={form.label} onChange={(e) => setForm((p) => ({ ...p, label: e.target.value }))} /></Field>
          <Field label="Tagline">
            <textarea
              placeholder="Short description shown under the product name…"
              value={form.tagline} onChange={(e) => setForm((p) => ({ ...p, tagline: e.target.value }))} rows={2}
              style={{ background: "var(--dropdown-bg-2)", border: "1px solid var(--card-bd)", color: "var(--title-tx)" }}
              className="w-full px-3 py-2.5 rounded-xl text-sm outline-none focus:border-blue-500 resize-none placeholder:text-[var(--muted-tx)]"
            />
          </Field>
          <Field label="Icon key"><Input placeholder="e.g. bar-chart" value={form.icon} onChange={(e) => setForm((p) => ({ ...p, icon: e.target.value }))} /></Field>
          <Field label="Color (hex)"><Input placeholder="#6d28d9" value={form.color} onChange={(e) => setForm((p) => ({ ...p, color: e.target.value }))} /></Field>
          <Field label="Sort order"><Input type="number" value={form.sort_order} onChange={(e) => setForm((p) => ({ ...p, sort_order: e.target.value }))} /></Field>
          <div className="flex gap-3 mt-6">
            <button onClick={() => setCreateOpen(false)} style={{ color: "var(--muted-tx)", border: "1px solid var(--card-bd)" }} className="flex-1 py-2.5 rounded-xl text-sm hover:bg-[var(--card-bg-2)] transition-colors">Cancel</button>
            <button onClick={handleCreate} disabled={saving} className="flex-1 py-2.5 rounded-xl text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 transition-colors flex items-center justify-center gap-2">
              {saving && <Loader2 size={14} className="animate-spin" />} Create Product
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
