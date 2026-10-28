const API = process.env.NEXT_PUBLIC_API_URL;

if (!API) {
  throw new Error("NEXT_PUBLIC_API_URL is missing");
}

export async function loginUser(email: string, password: string) {
  return postJson("/auth/login", { email, password }, "Login failed");
}


export async function forgotPassword(email: string) {
  return postJson(
    "/auth/forgot-password",
    { email },
    "Failed to send reset email.",
    "No account found with this email.",
  );
}

export async function resetPassword(token: string, newPassword: string) {
  return postJson(
    "/auth/reset-password",
    { token, new_password: newPassword },
    "Password reset failed",
  );
}

export async function setupPassword(token: string, newPassword: string) {
  return postJson(
    "/auth/setup-password",
    { token, new_password: newPassword },
    "Password setup failed",
  );
}

export async function completeNewPassword(
  email: string,
  newPassword: string,
  session: string
) {
  return postJson(
    "/auth/complete-new-password",
    { email, new_password: newPassword, session },
    "Password update failed",
  );
}

async function postJson(
  endpoint: string,
  body: Record<string, string>,
  fallbackMessage: string,
  notFoundMessage?: string,
) {
  const res = await fetch(`${API}${endpoint}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    if (res.status === 404 && notFoundMessage) {
      throw new Error(notFoundMessage);
    }
    const error = await res.json().catch(() => ({}));
    throw new Error(error.message || error.detail || fallbackMessage);
  }

  return res.json();
}
