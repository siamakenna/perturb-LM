import { NextResponse } from "next/server";
import { MockSearchProvider } from "@/lib/search/mock-provider";
import { searchRequestSchema } from "@/lib/search/validation";

export async function POST(request: Request) {
  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ error: "Malformed JSON request." }, { status: 400 });
  }

  const parsed = searchRequestSchema.safeParse(payload);
  if (!parsed.success) {
    return NextResponse.json(
      { error: parsed.error.issues.map((issue) => issue.message).join(" ") },
      { status: 400 },
    );
  }

  const provider = new MockSearchProvider();
  const response = await provider.search(parsed.data.query);
  return NextResponse.json(response);
}
