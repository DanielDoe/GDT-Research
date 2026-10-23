import { NextResponse } from "next/server";
import catalog from "@/lib/agents/catalog.json";

export function GET() {
  return NextResponse.json({ agents: catalog.agents });
}
