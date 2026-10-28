import { NextResponse } from "next/server";

const UAE_BANK_BRAND_HEALTH_CHAT_URL =
  process.env.UAE_BANK_BRAND_HEALTH_CHAT_URL || "https://assistant.example.com/uae-bank-brand-health/chat";

export async function POST(request: Request) {
  try {
    const body: unknown = await request.json();
    const response = await fetch(UAE_BANK_BRAND_HEALTH_CHAT_URL, {
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
        detail: error instanceof Error ? error.message : "UAE Bank Brand Health chat service is unavailable",
      },
      { status: 502 }
    );
  }
}
