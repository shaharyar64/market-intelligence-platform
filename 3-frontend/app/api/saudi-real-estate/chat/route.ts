import { NextResponse } from "next/server";

// TODO: point at a dedicated saudi-real-estate chat backend once one exists.
// Reusing the same stopgap host digital-brand-health/real-estate use for now.
const SAUDI_REAL_ESTATE_CHAT_URL = "http://localhost:5003/chat";

export async function POST(request: Request) {
  try {
    const body: unknown = await request.json();
    const response = await fetch(SAUDI_REAL_ESTATE_CHAT_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    const responseBody = await response.text();

    return new NextResponse(responseBody, {
      status: response.status,
      headers: {
        "Content-Type": response.headers.get("content-type") || "application/json",
      },
    });
  } catch (error) {
    return NextResponse.json(
      {
        detail: error instanceof Error ? error.message : "Saudi Real Estate chat service is unavailable",
      },
      { status: 502 }
    );
  }
}
