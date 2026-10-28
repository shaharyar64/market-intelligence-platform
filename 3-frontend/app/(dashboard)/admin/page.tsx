"use client";

import { useEffect, useState } from "react";
import DashboardTopbar from "@/components/layout/DashboardTopbar";
import {
  getMe, getUsers, createUser, updateUser, deleteUser,
  getServices, getUserServices, assignServicesToUser,
  type User, type Service, type CreateUserPayload, type UpdateUserPayload,
} from "@/lib/user";
import { Plus, Pencil, Trash2, Shield, ShieldOff, UserCog, X, Check, Loader2, Search, Lock } from "lucide-react";

const isAdmin = (u: User) => u.role?.toUpperCase() === "ADMIN";

/* ─── shared modal ───────────────────────────────────────────────────── */
function Modal({ title, onClose, children, width = "max-w-md" }: {
  title: string; onClose: () => void; children: React.ReactNode; width?: string;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.45)", backdropFilter: "blur(4px)" }}>
      <div className={`w-full ${width} max-h-[85vh] rounded-2xl shadow-2xl flex flex-col`} style={{ background: "var(--dropdown-bg)", border: "1px solid var(--card-bd)" }}>
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

/* ─── form field ─────────────────────────────────────────────────────── */
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mb-4">
      <label style={{ color: "var(--muted-tx)" }} className="block text-xs font-medium mb-1.5">{label}</label>
      {children}
    </div>
  );
}

function Input({ ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input {...props}
      style={{ background: "var(--dropdown-bg-2)", border: "1px solid var(--card-bd)", color: "var(--title-tx)" }}
      className="w-full px-3 py-2.5 rounded-xl text-sm outline-none focus:border-blue-500 transition-colors placeholder:text-[var(--muted-tx)]"
    />
  );
}

/* ─── badges ─────────────────────────────────────────────────────────── */
function RoleBadge({ isAdmin }: { isAdmin: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold"
      style={isAdmin ? { background: "#ede9fe", color: "#6d28d9" } : { background: "var(--card-bg-2)", color: "var(--muted-tx)", border: "1px solid var(--card-bd)" }}>
      {isAdmin ? <Shield size={11} /> : <ShieldOff size={11} />}
      {isAdmin ? "Admin" : "User"}
    </span>
  );
}

function StatusBadge({ active }: { active: boolean }) {
  return (
    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold"
      style={active ? { background: "#dcfce7", color: "#166534" } : { background: "#fee2e2", color: "#991b1b" }}>
      <span className="w-1.5 h-1.5 rounded-full inline-block" style={{ background: active ? "#16a34a" : "#dc2626" }} />
      {active ? "Active" : "Inactive"}
    </span>
  );
}

/* ─── page ───────────────────────────────────────────────────────────── */
export default function AdminUsersPage() {
  const [authorized, setAuthorized] = useState<boolean | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // modals
  const [createOpen, setCreateOpen] = useState(false);
  const [editUser, setEditUser] = useState<User | null>(null);
  const [deleteUser_, setDeleteUser_] = useState<User | null>(null);
  const [servicesUser, setServicesUser] = useState<User | null>(null);
  const [userServiceIds, setUserServiceIds] = useState<string[]>([]);

  // forms
  const [createForm, setCreateForm] = useState<CreateUserPayload>({ email: "", full_name: "", is_admin_user: false });
  const [editForm, setEditForm] = useState<UpdateUserPayload>({});

  const loadUsers = () => getUsers().then(setUsers).catch(() => {});

  useEffect(() => {
    // Check if current user is admin before loading anything
    getMe()
      .then((me) => {
        if (!isAdmin(me)) { setAuthorized(false); setLoading(false); return; }
        setAuthorized(true);
        setLoading(true);
        Promise.all([loadUsers(), getServices().then(setServices)])
          .finally(() => setLoading(false));
      })
      .catch(() => { setAuthorized(false); setLoading(false); });
  }, []);

  const filtered = users.filter((u) =>
    u.full_name.toLowerCase().includes(search.toLowerCase()) ||
    u.email.toLowerCase().includes(search.toLowerCase())
  );

  /* create */
  const handleCreate = async () => {
    if (!createForm.email || !createForm.full_name) { setError("Email and name are required."); return; }
    setSaving(true); setError("");
    try {
      await createUser(createForm);
      await loadUsers();
      setCreateOpen(false);
      setCreateForm({ email: "", full_name: "", is_admin_user: false });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create user");
    } finally { setSaving(false); }
  };

  /* edit */
  const openEdit = (user: User) => {
    setEditUser(user);
    setEditForm({ full_name: user.full_name, is_active: user.is_active, is_admin_user: isAdmin(user) });
    setError("");
  };
  const handleEdit = async () => {
    if (!editUser) return;
    setSaving(true); setError("");
    try {
      await updateUser(editUser.id, editForm);
      await loadUsers();
      setEditUser(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to update user");
    } finally { setSaving(false); }
  };

  /* delete */
  const handleDelete = async () => {
    if (!deleteUser_) return;
    setSaving(true);
    try {
      await deleteUser(deleteUser_.id);
      await loadUsers();
      setDeleteUser_(null);
    } catch { } finally { setSaving(false); }
  };

  /* services */
  const openServices = async (user: User) => {
    setServicesUser(user);
    try {
      const assigned = await getUserServices(user.id);
      setUserServiceIds(assigned.map((s) => s.id));
    } catch { setUserServiceIds([]); }
  };
  const handleSaveServices = async () => {
    if (!servicesUser) return;
    setSaving(true);
    try {
      await assignServicesToUser(servicesUser.id, userServiceIds);
      setServicesUser(null);
    } catch { } finally { setSaving(false); }
  };

  const toggle = (id: string) =>
    setUserServiceIds((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);

  const stats = [
    { label: "Total Users",    value: users.length,                              color: "#6366f1" },
    { label: "Active",         value: users.filter((u) => u.is_active).length,   color: "#16a34a" },
    { label: "Inactive",       value: users.filter((u) => !u.is_active).length,  color: "#dc2626" },
    { label: "Admins",         value: users.filter(isAdmin).length,                   color: "#8b5cf6" },
  ];

  /* ── access denied ── */
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
            You need Admin privileges to access this page. Contact an administrator.
          </p>
        </div>
      </div>
    );
  }

  /* ── loading auth check ── */
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

        {/* Stats */}
        <div className="grid grid-cols-4 gap-4 mb-8">
          {stats.map((s) => (
            <div key={s.label} className="chart-card rounded-2xl p-5 flex items-center gap-4">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: `${s.color}20` }}>
                <span style={{ color: s.color, fontWeight: 800, fontSize: 16 }}>{s.value}</span>
              </div>
              <div>
                <div style={{ color: "var(--title-tx)" }} className="text-xl font-bold">{s.value}</div>
                <div style={{ color: "var(--muted-tx)" }} className="text-xs">{s.label}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Table card */}
        <div className="chart-card rounded-2xl p-6">
          {/* Toolbar */}
          <div className="flex items-center justify-between mb-5 gap-4">
            <h2 style={{ color: "var(--title-tx)" }} className="text-base font-semibold">Users</h2>
            <div className="flex items-center gap-3">
              <div className="relative">
                <Search size={14} style={{ color: "var(--muted-tx)" }} className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                <input
                  value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search users…"
                  style={{ background: "var(--card-bg-2)", border: "1px solid var(--card-bd)", color: "var(--title-tx)" }}
                  className="pl-9 pr-4 py-2 rounded-xl text-sm outline-none focus:border-blue-500 placeholder:text-[var(--muted-tx)] w-56"
                />
              </div>
              <button
                onClick={() => { setCreateOpen(true); setError(""); setCreateForm({ email: "", full_name: "", is_admin_user: false }); }}
                className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 transition-colors"
              >
                <Plus size={15} /> New User
              </button>
            </div>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-20"><Loader2 style={{ color: "var(--muted-tx)" }} className="animate-spin" /></div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--card-bd)" }}>
                    {["Name", "Email", "Role", "Status", "Created", "Actions"].map((h) => (
                      <th key={h} style={{ color: "var(--muted-tx)" }} className="text-left py-3 px-4 text-xs font-semibold uppercase tracking-wider">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.length === 0 ? (
                    <tr><td colSpan={6} style={{ color: "var(--muted-tx)" }} className="text-center py-12 text-sm">No users found</td></tr>
                  ) : filtered.map((user) => (
                    <tr key={user.id} style={{ borderBottom: "1px solid var(--card-bd)" }} className="hover:bg-[var(--card-bg-2)] transition-colors">
                      <td className="py-3.5 px-4 font-medium" style={{ color: "var(--title-tx)" }}>{user.full_name}</td>
                      <td className="py-3.5 px-4" style={{ color: "var(--body-tx)" }}>{user.email}</td>
                      <td className="py-3.5 px-4"><RoleBadge isAdmin={isAdmin(user)} /></td>
                      <td className="py-3.5 px-4"><StatusBadge active={user.is_active} /></td>
                      <td className="py-3.5 px-4 text-xs" style={{ color: "var(--muted-tx)" }}>
                        {user.created_at ? new Date(user.created_at).toLocaleDateString() : "—"}
                      </td>
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-1">
                          <button title="Assign Services" onClick={() => openServices(user)}
                            style={{ color: "var(--muted-tx)" }} className="p-1.5 rounded-lg hover:bg-indigo-100 hover:text-indigo-600 transition-colors">
                            <UserCog size={15} />
                          </button>
                          <button title="Edit" onClick={() => openEdit(user)}
                            style={{ color: "var(--muted-tx)" }} className="p-1.5 rounded-lg hover:bg-blue-100 hover:text-blue-600 transition-colors">
                            <Pencil size={15} />
                          </button>
                          <button title="Delete" onClick={() => setDeleteUser_(user)}
                            style={{ color: "var(--muted-tx)" }} className="p-1.5 rounded-lg hover:bg-red-100 hover:text-red-600 transition-colors">
                            <Trash2 size={15} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* ── Create User Modal ── */}
      {createOpen && (
        <Modal title="Create New User" onClose={() => setCreateOpen(false)}>
          {error && <p className="text-red-500 text-xs mb-4 bg-red-50 rounded-lg px-3 py-2">{error}</p>}
          <Field label="Full Name"><Input placeholder="John Doe" value={createForm.full_name} onChange={(e) => setCreateForm((p) => ({ ...p, full_name: e.target.value }))} /></Field>
          <Field label="Email"><Input type="email" placeholder="john@example.com" value={createForm.email} onChange={(e) => setCreateForm((p) => ({ ...p, email: e.target.value }))} /></Field>
          <Field label="Role">
            <label className="flex items-center gap-3 cursor-pointer">
              <div
                onClick={() => setCreateForm((p) => ({ ...p, is_admin_user: !p.is_admin_user }))}
                className="w-10 h-6 rounded-full relative transition-colors cursor-pointer"
                style={{ background: createForm.is_admin_user ? "#6366f1" : "var(--card-bd)" }}
              >
                <span className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-transform duration-200 ${createForm.is_admin_user ? "translate-x-5" : "translate-x-1"}`} />
              </div>
              <span style={{ color: "var(--body-tx)" }} className="text-sm">Admin user</span>
            </label>
          </Field>
          <div className="flex gap-3 mt-6">
            <button onClick={() => setCreateOpen(false)} style={{ color: "var(--muted-tx)", border: "1px solid var(--card-bd)" }} className="flex-1 py-2.5 rounded-xl text-sm hover:bg-[var(--card-bg-2)] transition-colors">Cancel</button>
            <button onClick={handleCreate} disabled={saving} className="flex-1 py-2.5 rounded-xl text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 transition-colors flex items-center justify-center gap-2">
              {saving && <Loader2 size={14} className="animate-spin" />} Create User
            </button>
          </div>
        </Modal>
      )}

      {/* ── Edit User Modal ── */}
      {editUser && (
        <Modal title={`Edit — ${editUser.full_name}`} onClose={() => setEditUser(null)}>
          {error && <p className="text-red-500 text-xs mb-4 bg-red-50 rounded-lg px-3 py-2">{error}</p>}
          <Field label="Full Name"><Input value={editForm.full_name ?? ""} onChange={(e) => setEditForm((p) => ({ ...p, full_name: e.target.value }))} /></Field>
          <Field label="Status">
            <label className="flex items-center gap-3 cursor-pointer">
              <div onClick={() => setEditForm((p) => ({ ...p, is_active: !p.is_active }))}
                className="w-10 h-6 rounded-full relative transition-colors cursor-pointer"
                style={{ background: editForm.is_active ? "#16a34a" : "var(--card-bd)" }}>
                <span className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-transform duration-200 ${editForm.is_active ? "translate-x-5" : "translate-x-1"}`} />
              </div>
              <span style={{ color: "var(--body-tx)" }} className="text-sm">{editForm.is_active ? "Active" : "Inactive"}</span>
            </label>
          </Field>
          <Field label="Role">
            <label className="flex items-center gap-3 cursor-pointer">
              <div onClick={() => setEditForm((p) => ({ ...p, is_admin_user: !p.is_admin_user }))}
                className="w-10 h-6 rounded-full relative transition-colors cursor-pointer"
                style={{ background: editForm.is_admin_user ? "#6366f1" : "var(--card-bd)" }}>
                <span className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-transform duration-200 ${editForm.is_admin_user ? "translate-x-5" : "translate-x-1"}`} />
              </div>
              <span style={{ color: "var(--body-tx)" }} className="text-sm">Admin user</span>
            </label>
          </Field>
          <div className="flex gap-3 mt-6">
            <button onClick={() => setEditUser(null)} style={{ color: "var(--muted-tx)", border: "1px solid var(--card-bd)" }} className="flex-1 py-2.5 rounded-xl text-sm hover:bg-[var(--card-bg-2)] transition-colors">Cancel</button>
            <button onClick={handleEdit} disabled={saving} className="flex-1 py-2.5 rounded-xl text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 transition-colors flex items-center justify-center gap-2">
              {saving && <Loader2 size={14} className="animate-spin" />} Save Changes
            </button>
          </div>
        </Modal>
      )}

      {/* ── Delete Confirm Modal ── */}
      {deleteUser_ && (
        <Modal title="Delete User" onClose={() => setDeleteUser_(null)}>
          <p style={{ color: "var(--body-tx)" }} className="text-sm mb-6">
            Are you sure you want to delete <strong style={{ color: "var(--title-tx)" }}>{deleteUser_.full_name}</strong>? This action cannot be undone.
          </p>
          <div className="flex gap-3">
            <button onClick={() => setDeleteUser_(null)} style={{ color: "var(--muted-tx)", border: "1px solid var(--card-bd)" }} className="flex-1 py-2.5 rounded-xl text-sm hover:bg-[var(--card-bg-2)] transition-colors">Cancel</button>
            <button onClick={handleDelete} disabled={saving} className="flex-1 py-2.5 rounded-xl text-sm font-semibold text-white bg-red-600 hover:bg-red-700 disabled:opacity-50 transition-colors flex items-center justify-center gap-2">
              {saving && <Loader2 size={14} className="animate-spin" />} Delete
            </button>
          </div>
        </Modal>
      )}

      {/* ── Assign Services Modal ── */}
      {servicesUser && (
        <Modal title={`Services — ${servicesUser.full_name}`} onClose={() => setServicesUser(null)} width="max-w-lg">
          <p style={{ color: "var(--muted-tx)" }} className="text-xs mb-4">Toggle which services this user can access.</p>
          <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
            {services.length === 0 ? (
              <p style={{ color: "var(--muted-tx)" }} className="text-sm text-center py-6">No services available</p>
            ) : services.map((svc) => {
              const assigned = userServiceIds.includes(svc.id);
              return (
                <button key={svc.id} onClick={() => toggle(svc.id)}
                  className="w-full flex items-center justify-between p-3.5 rounded-xl transition-colors text-left"
                  style={{ background: assigned ? "#ede9fe" : "var(--card-bg-2)", border: `1px solid ${assigned ? "#c4b5fd" : "var(--card-bd)"}` }}>
                  <div>
                    <div style={{ color: assigned ? "#6d28d9" : "var(--title-tx)" }} className="text-sm font-semibold">{svc.name}</div>
                    {svc.description && <div style={{ color: "var(--muted-tx)" }} className="text-xs mt-0.5">{svc.description}</div>}
                    <div style={{ color: "var(--muted-tx)" }} className="text-xs font-mono mt-0.5">{svc.code}</div>
                  </div>
                  <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 ml-4 ${assigned ? "bg-indigo-600" : ""}`}
                    style={assigned ? {} : { border: "2px solid var(--card-bd)" }}>
                    {assigned && <Check size={12} color="white" />}
                  </div>
                </button>
              );
            })}
          </div>
          <div className="flex gap-3 mt-5">
            <button onClick={() => setServicesUser(null)} style={{ color: "var(--muted-tx)", border: "1px solid var(--card-bd)" }} className="flex-1 py-2.5 rounded-xl text-sm hover:bg-[var(--card-bg-2)] transition-colors">Cancel</button>
            <button onClick={handleSaveServices} disabled={saving} className="flex-1 py-2.5 rounded-xl text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 transition-colors flex items-center justify-center gap-2">
              {saving && <Loader2 size={14} className="animate-spin" />} Save Services
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
