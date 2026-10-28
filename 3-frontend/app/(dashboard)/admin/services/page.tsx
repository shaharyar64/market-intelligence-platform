"use client";

import { useEffect, useState } from "react";
import DashboardTopbar from "@/components/layout/DashboardTopbar";
import { getMe, getServices, createService, updateService, deleteService, getProducts, type Service, type Product } from "@/lib/user";
import { Plus, Puzzle, Search, Loader2, X, Globe, Code2, Tag, Lock, Pencil, Trash2, LayoutGrid, MapPin } from "lucide-react";

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
      className="w-full px-3 py-2.5 rounded-xl text-sm outline-none focus:border-blue-500 transition-colors placeholder:text-[var(--muted-tx)]"
    />
  );
}

type CreateForm = { name: string; code: string; description: string; route: string; icon: string; is_active?: boolean; product: string; category: string; country: string };

const EMPTY: CreateForm = { name: "", code: "", description: "", route: "", icon: "", is_active: true, product: "", category: "", country: "" };

function Select({ style, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select {...props}
      style={{ background: "var(--dropdown-bg-2)", border: "1px solid var(--card-bd)", color: "var(--title-tx)", ...style }}
      className="w-full px-3 py-2.5 rounded-xl text-sm outline-none focus:border-blue-500 transition-colors"
    />
  );
}

/* ─── service card ───────────────────────────────────────────────────── */
function ServiceCard({ service, products, onEdit }: { service: Service; products: Product[]; onEdit: (s: Service) => void }) {
  const productLabel = products.find((p) => p.key === service.product)?.label ?? service.product;

  return (
    <div className="chart-card rounded-2xl p-5 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: "rgba(99,102,241,0.12)" }}>
          <Puzzle size={18} style={{ color: "#6366f1" }} />
        </div>
        <div className="flex items-center gap-2">
          <span style={{ background: "#ede9fe", color: "#6d28d9" }} className="text-xs font-semibold px-2 py-0.5 rounded-full">{service.code}</span>
          <button
            onClick={() => onEdit(service)}
            style={{ color: "var(--muted-tx)" }}
            className="hover:text-indigo-500 transition-colors p-1 rounded-lg hover:bg-[var(--card-bg-2)]"
          >
            <Pencil size={13} />
          </button>
        </div>
      </div>

      <div>
        <h3 style={{ color: "var(--title-tx)" }} className="font-semibold text-sm mb-1">{service.name}</h3>
        {service.description && <p style={{ color: "var(--muted-tx)" }} className="text-xs leading-relaxed">{service.description}</p>}
      </div>

      {productLabel && (
        <div className="flex items-center gap-1.5 flex-wrap">
          <span style={{ background: "rgba(99,102,241,0.12)", color: "#4338ca" }} className="text-[11px] font-semibold px-2 py-0.5 rounded-full">{productLabel}</span>
          {service.category && <span style={{ background: "var(--card-bg-2)", color: "var(--muted-tx)" }} className="text-[11px] px-2 py-0.5 rounded-full">{service.category}</span>}
          {service.country && <span style={{ background: "var(--card-bg-2)", color: "var(--muted-tx)" }} className="text-[11px] px-2 py-0.5 rounded-full">{service.country}</span>}
        </div>
      )}

      <div className="space-y-1.5 mt-auto pt-3" style={{ borderTop: "1px solid var(--card-bd)" }}>
        {service.route && (
          <div className="flex items-center gap-2">
            <Globe size={11} style={{ color: "var(--muted-tx)" }} />
            <span style={{ color: "var(--muted-tx)" }} className="text-xs font-mono truncate">{service.route}</span>
          </div>
        )}
        {service.icon && (
          <div className="flex items-center gap-2">
            <Tag size={11} style={{ color: "var(--muted-tx)" }} />
            <span style={{ color: "var(--muted-tx)" }} className="text-xs truncate">{service.icon}</span>
          </div>
        )}
      </div>
    </div>
  );
}

/** product/category/country must be all set or all empty — mirrors the backend's 422 rule. */
function resolveGrouping(form: CreateForm): { product: string | null; category: string | null; country: string | null } | null {
  if (!form.product) return { product: null, category: null, country: null };
  if (!form.category || !form.country) return null;
  return { product: form.product, category: form.category, country: form.country };
}

/* ─── page ───────────────────────────────────────────────────────────── */
export default function AdminServicesPage() {
  const [authorized, setAuthorized] = useState<boolean | null>(null);
  const [services, setServices] = useState<Service[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [editService, setEditService] = useState<Service | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<Service | null>(null);
  const [form, setForm] = useState<CreateForm>(EMPTY);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const load = () => Promise.all([getServices().then(setServices), getProducts().then(setProducts)]);

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

  const filtered = services.filter((s) =>
    s.name.toLowerCase().includes(search.toLowerCase()) ||
    s.code.toLowerCase().includes(search.toLowerCase())
  );

  const openEdit = (svc: Service) => {
    setEditService(svc);
    setForm({
      name: svc.name, code: svc.code, description: svc.description ?? "", route: svc.route ?? "", icon: svc.icon ?? "", is_active: svc.is_active ?? true,
      product: svc.product ?? "", category: svc.category ?? "", country: svc.country ?? "",
    });
    setError("");
  };

  const handleEdit = async () => {
    if (!editService || !form.name || !form.code) { setError("Name and code are required."); return; }
    const grouping = resolveGrouping(form);
    if (!grouping) { setError("Category and Country are required when a Product is set."); return; }
    setSaving(true); setError("");
    try {
      await updateService(editService.id, { name: form.name, code: form.code, description: form.description || undefined, route: form.route || undefined, icon: form.icon || undefined, is_active: form.is_active, ...grouping });
      await load();
      setEditService(null);
      setForm(EMPTY);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to update service");
    } finally { setSaving(false); }
  };

  const handleCreate = async () => {
    if (!form.name || !form.code) { setError("Name and code are required."); return; }
    const grouping = resolveGrouping(form);
    if (!grouping) { setError("Category and Country are required when a Product is set."); return; }
    setSaving(true); setError("");
    try {
      await createService({ name: form.name, code: form.code, description: form.description || undefined, route: form.route || undefined, icon: form.icon || undefined, ...grouping });
      await load();
      setCreateOpen(false);
      setForm(EMPTY);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create service");
    } finally { setSaving(false); }
  };

  const handleDelete = async () => {
    if (!deleteConfirm) return;
    setSaving(true);
    try {
      await deleteService(deleteConfirm.id);
      await load();
      setDeleteConfirm(null);
      setEditService(null);
      setForm(EMPTY);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to delete service");
      setSaving(false);
    }
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
            <h1 style={{ color: "var(--title-tx)" }} className="text-2xl font-bold">Services</h1>
            <p style={{ color: "var(--muted-tx)" }} className="text-sm mt-1">{services.length} service{services.length !== 1 ? "s" : ""} registered</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search size={14} style={{ color: "var(--muted-tx)" }} className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search services…"
                style={{ background: "var(--card-bg)", border: "1px solid var(--card-bd)", color: "var(--title-tx)", backdropFilter: "var(--blur)" }}
                className="pl-9 pr-4 py-2 rounded-xl text-sm outline-none focus:border-blue-500 placeholder:text-[var(--muted-tx)] w-52"
              />
            </div>
            <button
              onClick={() => { setCreateOpen(true); setForm(EMPTY); setError(""); }}
              className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 transition-colors"
            >
              <Plus size={15} /> New Service
            </button>
          </div>
        </div>

        {/* Grid */}
        {loading ? (
          <div className="flex items-center justify-center py-32"><Loader2 style={{ color: "var(--muted-tx)" }} className="animate-spin" size={28} /></div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-32 gap-3">
            <Puzzle size={40} style={{ color: "var(--card-bd)" }} />
            <p style={{ color: "var(--muted-tx)" }} className="text-sm">{search ? "No services match your search" : "No services yet — create your first one"}</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {filtered.map((svc) => <ServiceCard key={svc.id} service={svc} products={products} onEdit={openEdit} />)}
          </div>
        )}
      </div>

      {/* ── Edit Service Modal ── */}
      {editService && (
        <Modal title="Edit Service" onClose={() => { setEditService(null); setForm(EMPTY); setError(""); }}>
          {error && <p className="text-red-500 text-xs mb-4 bg-red-50 rounded-lg px-3 py-2">{error}</p>}
          <Field label="Service Name *"><Input placeholder="e.g. Pricing Analysis" value={form.name} onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))} /></Field>
          <Field label="Code *">
            <div className="relative">
              <Code2 size={13} style={{ color: "var(--muted-tx)" }} className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <Input placeholder="e.g. PRICING" value={form.code} onChange={(e) => setForm((p) => ({ ...p, code: e.target.value }))}
                style={{ paddingLeft: "2.25rem" }} />
            </div>
          </Field>
          <Field label="Description">
            <textarea
              placeholder="Short description of this service…"
              value={form.description} onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))} rows={2}
              style={{ background: "var(--dropdown-bg-2)", border: "1px solid var(--card-bd)", color: "var(--title-tx)" }}
              className="w-full px-3 py-2.5 rounded-xl text-sm outline-none focus:border-blue-500 resize-none placeholder:text-[var(--muted-tx)]"
            />
          </Field>
          <Field label="Route">
            <div className="relative">
              <Globe size={13} style={{ color: "var(--muted-tx)" }} className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <Input placeholder="/pricing" value={form.route} onChange={(e) => setForm((p) => ({ ...p, route: e.target.value }))}
                style={{ paddingLeft: "2.25rem" }} />
            </div>
          </Field>
          <Field label="Icon">
            <Input placeholder="e.g. BarChart2" value={form.icon} onChange={(e) => setForm((p) => ({ ...p, icon: e.target.value }))} />
          </Field>
          <Field label="Product">
            <div className="relative">
              <LayoutGrid size={13} style={{ color: "var(--muted-tx)" }} className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none z-10" />
              <Select value={form.product} onChange={(e) => setForm((p) => ({ ...p, product: e.target.value, ...(e.target.value ? {} : { category: "", country: "" }) }))} style={{ paddingLeft: "2.25rem" }}>
                <option value="">None / ungrouped</option>
                {products.map((prod) => <option key={prod.id} value={prod.key}>{prod.label}</option>)}
              </Select>
            </div>
          </Field>
          <Field label="Category">
            <Input placeholder="e.g. Banking" value={form.category} onChange={(e) => setForm((p) => ({ ...p, category: e.target.value }))} disabled={!form.product} />
          </Field>
          <Field label="Country">
            <div className="relative">
              <MapPin size={13} style={{ color: "var(--muted-tx)" }} className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <Input placeholder="e.g. Saudi Arabia" value={form.country} onChange={(e) => setForm((p) => ({ ...p, country: e.target.value }))}
                style={{ paddingLeft: "2.25rem" }} disabled={!form.product} />
            </div>
          </Field>
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
            <button onClick={() => { setEditService(null); setForm(EMPTY); setError(""); }} style={{ color: "var(--muted-tx)", border: "1px solid var(--card-bd)" }} className="flex-1 py-2.5 rounded-xl text-sm hover:bg-[var(--card-bg-2)] transition-colors">Cancel</button>
            <button onClick={() => setDeleteConfirm(editService)} style={{ color: "#ef4444", border: "1px solid #ef4444" }} className="px-4 py-2.5 rounded-xl text-sm hover:bg-red-50 transition-colors flex items-center justify-center gap-1">
              <Trash2 size={14} /> Delete
            </button>
            <button onClick={handleEdit} disabled={saving} className="flex-1 py-2.5 rounded-xl text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 transition-colors flex items-center justify-center gap-2">
              {saving && <Loader2 size={14} className="animate-spin" />} Save Changes
            </button>
          </div>
        </Modal>
      )}

      {/* ── Create Service Modal ── */}
      {createOpen && (
        <Modal title="Create New Service" onClose={() => setCreateOpen(false)}>
          {error && <p className="text-red-500 text-xs mb-4 bg-red-50 rounded-lg px-3 py-2">{error}</p>}
          <Field label="Service Name *"><Input placeholder="e.g. Pricing Analysis" value={form.name} onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))} /></Field>
          <Field label="Code *">
            <div className="relative">
              <Code2 size={13} style={{ color: "var(--muted-tx)" }} className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <Input placeholder="e.g. PRICING" value={form.code} onChange={(e) => setForm((p) => ({ ...p, code: e.target.value }))}
                style={{ paddingLeft: "2.25rem" }} />
            </div>
          </Field>
          <Field label="Description">
            <textarea
              placeholder="Short description of this service…"
              value={form.description} onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))} rows={2}
              style={{ background: "var(--dropdown-bg-2)", border: "1px solid var(--card-bd)", color: "var(--title-tx)" }}
              className="w-full px-3 py-2.5 rounded-xl text-sm outline-none focus:border-blue-500 resize-none placeholder:text-[var(--muted-tx)]"
            />
          </Field>
          <Field label="Route">
            <div className="relative">
              <Globe size={13} style={{ color: "var(--muted-tx)" }} className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <Input placeholder="/pricing" value={form.route} onChange={(e) => setForm((p) => ({ ...p, route: e.target.value }))}
                style={{ paddingLeft: "2.25rem" }} />
            </div>
          </Field>
          <Field label="Icon">
            <Input placeholder="e.g. BarChart2" value={form.icon} onChange={(e) => setForm((p) => ({ ...p, icon: e.target.value }))} />
          </Field>
          <Field label="Product">
            <div className="relative">
              <LayoutGrid size={13} style={{ color: "var(--muted-tx)" }} className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none z-10" />
              <Select value={form.product} onChange={(e) => setForm((p) => ({ ...p, product: e.target.value, ...(e.target.value ? {} : { category: "", country: "" }) }))} style={{ paddingLeft: "2.25rem" }}>
                <option value="">None / ungrouped</option>
                {products.map((prod) => <option key={prod.id} value={prod.key}>{prod.label}</option>)}
              </Select>
            </div>
          </Field>
          <Field label="Category">
            <Input placeholder="e.g. Banking" value={form.category} onChange={(e) => setForm((p) => ({ ...p, category: e.target.value }))} disabled={!form.product} />
          </Field>
          <Field label="Country">
            <div className="relative">
              <MapPin size={13} style={{ color: "var(--muted-tx)" }} className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <Input placeholder="e.g. Saudi Arabia" value={form.country} onChange={(e) => setForm((p) => ({ ...p, country: e.target.value }))}
                style={{ paddingLeft: "2.25rem" }} disabled={!form.product} />
            </div>
          </Field>
          <div className="flex gap-3 mt-6">
            <button onClick={() => setCreateOpen(false)} style={{ color: "var(--muted-tx)", border: "1px solid var(--card-bd)" }} className="flex-1 py-2.5 rounded-xl text-sm hover:bg-[var(--card-bg-2)] transition-colors">Cancel</button>
            <button onClick={handleCreate} disabled={saving} className="flex-1 py-2.5 rounded-xl text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 transition-colors flex items-center justify-center gap-2">
              {saving && <Loader2 size={14} className="animate-spin" />} Create Service
            </button>
          </div>
        </Modal>
      )}

      {/* ── Delete Confirmation Modal ── */}
      {deleteConfirm && (
        <Modal title="Delete Service" onClose={() => setDeleteConfirm(null)}>
          <p style={{ color: "var(--body-tx)" }} className="text-sm mb-4">
            Are you sure you want to delete <strong>{deleteConfirm.name}</strong>? This action cannot be undone.
          </p>
          <div className="flex gap-3 mt-6">
            <button onClick={() => setDeleteConfirm(null)} style={{ color: "var(--muted-tx)", border: "1px solid var(--card-bd)" }} className="flex-1 py-2.5 rounded-xl text-sm hover:bg-[var(--card-bg-2)] transition-colors">Cancel</button>
            <button onClick={handleDelete} disabled={saving} className="flex-1 py-2.5 rounded-xl text-sm font-semibold text-white bg-red-600 hover:bg-red-700 disabled:opacity-50 transition-colors flex items-center justify-center gap-2">
              {saving && <Loader2 size={14} className="animate-spin" />} Delete Service
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
