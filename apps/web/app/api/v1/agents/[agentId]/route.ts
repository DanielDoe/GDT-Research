import { NextResponse } from "next/server";
import catalog from "@/lib/agents/catalog.json";

export async function GET(
  _request: Request,
  context: { params: Promise<{ agentId: string }> },
) {
  const { agentId } = await context.params;
  const card = catalog.agents.find((agent) => agent.agent_id === agentId);
  const subagents = (catalog.details as Record<string, unknown>)[agentId];
  if (!card || !subagents) {
    return NextResponse.json({ detail: `Unknown agent '${agentId}'.` }, { status: 404 });
  }
  return NextResponse.json({ card, subagents });
}
