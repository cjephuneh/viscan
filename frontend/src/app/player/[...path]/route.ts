import type { NextRequest } from "next/server";
import { forwardToAvatar } from "@/lib/avatar-proxy";

// Embeddable video-report player page served by ai-avatar (used in an <iframe>).
async function forward(request: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return forwardToAvatar(request, `/player/${path.map(encodeURIComponent).join("/")}`);
}

export { forward as GET };
