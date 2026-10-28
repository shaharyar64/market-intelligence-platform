import {
  clearAccessToken,
  getAccessToken,
  refreshAccessToken,
} from "./authSession";

const API = process.env.NEXT_PUBLIC_API_URL;

if (!API) {
  throw new Error("NEXT_PUBLIC_API_URL is missing");
}

export async function apiFetch(endpoint: string, options: RequestInit = {}) {
  let token = getAccessToken();
  let refreshed = false;

  if (!token) {
    try {
      token = await refreshAccessToken();
      refreshed = true;
    } catch {
      handleSessionExpired();
    }
  }

  let response = await sendRequest(endpoint, options, token);

  if (response.status === 401 && !refreshed) {
    try {
      token = await refreshAccessToken();
      refreshed = true;
      response = await sendRequest(endpoint, options, token);
    } catch {
      handleSessionExpired();
    }
  }

  if (response.status === 401) handleSessionExpired();
  return response;
}

function sendRequest(endpoint: string, options: RequestInit, token: string | null) {
  const isFormData = options.body instanceof FormData;
  const headers: Record<string, string> = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    ...(options.headers as Record<string, string>),
  };

  if (token) headers.Authorization = `Bearer ${token}`;

  return fetch(`${API}${endpoint}`, {
    ...options,
    credentials: "include",
    headers,
  });
}

function handleSessionExpired(): never {
  clearAccessToken();

  if (typeof window !== "undefined" && window.location.pathname !== "/login") {
    window.location.assign("/login");
  }
  throw new Error("Session expired");
}
