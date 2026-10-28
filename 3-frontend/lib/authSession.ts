const API = process.env.NEXT_PUBLIC_API_URL;

if (!API) {
  throw new Error("NEXT_PUBLIC_API_URL is missing");
}

let accessToken: string | null = null;
let activeRefresh: Promise<string> | null = null;

export function setAccessToken(token: string): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function clearAccessToken(): void {
  accessToken = null;
}

export function refreshAccessToken(): Promise<string> {
  if (activeRefresh) return activeRefresh;

  activeRefresh = fetch(`${API}/auth/refresh`, {
    method: "POST",
    credentials: "include",
  })
    .then(async (response) => {
      if (!response.ok) throw new Error("Refresh failed");
      const data = await response.json();
      if (!data.access_token) throw new Error("Refresh response is missing an access token");
      setAccessToken(data.access_token);
      return data.access_token as string;
    })
    .finally(() => {
      activeRefresh = null;
    });

  return activeRefresh;
}

export async function logoutUser(): Promise<void> {
  clearAccessToken();
  const response = await fetch(`${API}/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
  if (!response.ok) throw new Error("Logout failed");
}
