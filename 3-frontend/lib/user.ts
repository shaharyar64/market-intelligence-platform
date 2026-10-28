import { apiFetch } from "./apiClient";

const BASE = "/api/v1";


// ==============================
// 🧠 TYPES (SINGLE SOURCE OF TRUTH)
// ==============================

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at?: string;
}

// A product's `key` slug (e.g. "brandiq") — dynamic now that products are
// admin-managed via /admin/products, not a fixed set of four.
export type ProductKey = string;

export interface Product {
  id: string;
  key: string; // immutable slug, e.g. "brandiq" — what Service.product references
  label: string;
  tagline?: string | null;
  icon?: string | null;
  color?: string | null;
  sort_order: number;
  is_active?: boolean;
}

export interface Service {
  id: string;
  name: string;
  description?: string;
  code: string;
  route?: string;
  icon?: string;
  is_active?: boolean;
  // Product-suite grouping, set by the backend. Absent on services that
  // don't belong to one of the four IQ products (e.g. Horeca, EV, Admin).
  product?: ProductKey;
  category?: string;  // e.g. "Banking", "Real Estate", "Pricing", "F&B"
  country?: string;   // e.g. "Saudi Arabia", "UAE, Bahrain"
}

export interface CreateUserPayload {
  email: string;
  full_name: string;
  is_admin_user: boolean;
}

export interface UpdateUserPayload {
  full_name?: string;
  is_active?: boolean;
  is_admin_user?: boolean;
}

export interface AssignServicesPayload {
  service_ids: string[];
}


// ==============================
// 👤 AUTH
// ==============================

export async function getMe(): Promise<User> {
  const res = await apiFetch("/auth/me");

  if (!res.ok) throw new Error("Failed to fetch user");

  return res.json();
}


// ==============================
// 👥 USERS
// ==============================

export async function getUsers(): Promise<User[]> {
  const res = await apiFetch(`${BASE}/admin/users`);

  if (!res.ok) throw new Error("Failed to fetch users");

  return res.json();
}

export async function getUser(userId: string): Promise<User> {
  const res = await apiFetch(`${BASE}/admin/users/${userId}`);

  if (!res.ok) throw new Error("Failed to fetch user");

  return res.json();
}

export async function createUser(
  payload: CreateUserPayload
): Promise<{ message: string }> {
  const res = await apiFetch(`${BASE}/admin/users`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

  if (!res.ok) throw new Error("Failed to create user");

  return res.json();
}

export async function updateUser(
  userId: string,
  payload: UpdateUserPayload
): Promise<{ message: string }> {
  const params = new URLSearchParams();
  if (payload.full_name    !== undefined) params.append("full_name",    payload.full_name);
  if (payload.is_active    !== undefined) params.append("is_active",    String(payload.is_active));
  if (payload.is_admin_user !== undefined) params.append("is_admin_user", String(payload.is_admin_user));

  const res = await apiFetch(`${BASE}/admin/users/${userId}?${params.toString()}`, {
    method: "PUT",
  });

  if (!res.ok) throw new Error("Failed to update user");

  return res.json();
}

export async function deleteUser(
  userId: string
): Promise<{ message: string }> {
  const res = await apiFetch(`${BASE}/admin/users/${userId}`, {
    method: "DELETE",
  });

  if (!res.ok) throw new Error("Failed to delete user");

  return res.json();
}


// ==============================
// 🧩 PRODUCTS
// ==============================

export async function getProducts(): Promise<Product[]> {
  const res = await apiFetch(`${BASE}/admin/products`);

  if (!res.ok) throw new Error("Failed to fetch products");

  return res.json();
}

export async function createProduct(
  payload: {
    key: string;
    label: string;
    tagline?: string;
    icon?: string;
    color?: string;
    sort_order?: number;
  }
): Promise<{ message: string }> {
  const res = await apiFetch(`${BASE}/admin/products`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

  if (!res.ok) throw new Error("Failed to create product");

  return res.json();
}

export async function updateProduct(
  id: string,
  payload: Partial<{
    label: string;
    tagline: string;
    icon: string;
    color: string;
    sort_order: number;
    is_active: boolean;
  }>
): Promise<{ message: string }> {
  const res = await apiFetch(`${BASE}/admin/products/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });

  if (!res.ok) throw new Error("Failed to update product");

  return res.json();
}


// ==============================
// 🧠 SERVICES
// ==============================

export async function getServices(): Promise<Service[]> {
  const res = await apiFetch(`${BASE}/admin/services`);

  if (!res.ok) throw new Error("Failed to fetch services");

  return res.json();
}

export async function createService(
  payload: {
    name: string;
    code: string;
    description?: string;
    route?: string;
    icon?: string;
    product?: ProductKey | null;
    category?: string | null;
    country?: string | null;
  }
): Promise<{ message: string }> {
  const res = await apiFetch(`${BASE}/admin/services`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

  if (!res.ok) throw new Error("Failed to create service");

  return res.json();
}


export async function updateService(
  id: string,
  payload: {
    name?: string;
    code?: string;
    description?: string;
    route?: string;
    icon?: string;
    is_active?: boolean;
    product?: ProductKey | null;
    category?: string | null;
    country?: string | null;
  }
): Promise<{ message: string }> {
  const res = await apiFetch(`${BASE}/admin/services/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });

  if (!res.ok) throw new Error("Failed to update service");

  return res.json();
}

export async function deleteService(id: string): Promise<{ message: string }> {
  const res = await apiFetch(`${BASE}/admin/services/${id}`, {
    method: "DELETE",
  });

  if (!res.ok) throw new Error("Failed to delete service");

  return res.json();
}


// ==============================
// 🔗 USER ↔ SERVICES
// ==============================

export async function assignServicesToUser(
  userId: string,
  serviceIds: string[]
): Promise<{ message: string }> {
  const res = await apiFetch(`${BASE}/admin/users/${userId}/services`, {
    method: "POST",
    body: JSON.stringify({
      service_ids: serviceIds,
    }),
  });

  if (!res.ok) throw new Error("Failed to assign services");

  return res.json();
}

export async function getUserServices(
  userId: string
): Promise<Service[]> {
  const res = await apiFetch(`${BASE}/admin/users/${userId}/services`);

  if (!res.ok) throw new Error("Failed to fetch user services");

  return res.json();
}


// ==============================
// 👤 CURRENT USER SERVICES
// ==============================

export async function getMyServices(): Promise<Service[]> {
  const res = await apiFetch(`${BASE}/admin/me/services`);

  if (!res.ok) throw new Error("Failed to fetch my services");

  return res.json();
}