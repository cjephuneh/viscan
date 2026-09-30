import type { NextRequest } from "next/server";
import { forwardToAvatar } from "@/lib/avatar-proxy";

// `/api/v1/reports/*` belongs to ai-avatar (video reports), not the interpreter.
// This is more specific than `../[...path]`, so Next picks it first.
async function forward(request: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return forwardToAvatar(request, `/api/v1/reports/${path.map(encodeURIComponent).join("/")}`);
}

export { forward as GET, forward as POST };
