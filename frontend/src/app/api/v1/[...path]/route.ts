import type { NextRequest } from "next/server";

// AI readings take 30-90 s; allow the proxy to wait for the Flask backend.
export const maxDuration = 180;

const BACKEND = process.env.VISCAN_API_URL ?? "http://127.0.0.1:5050";
const PASS_THROUGH = ["content-type", "content-disposition"];

async function forward(request: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  const target = new URL(`/api/v1/${path.map(encodeURIComponent).join("/")}`, BACKEND);
  target.search = request.nextUrl.search;

  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  if (process.env.VISCAN_API_KEY) headers.set("x-api-key", process.env.VISCAN_API_KEY);

  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body: hasBody ? await request.arrayBuffer() : undefined,
      cache: "no-store",
    });
    const out = new Headers();
    for (const name of PASS_THROUGH) {
      const value = upstream.headers.get(name);
      if (value) out.set(name, value);
    }
    return new Response(await upstream.arrayBuffer(), { status: upstream.status, headers: out });
  } catch {
    return Response.json(
      { error: `The VIScan API is not reachable at ${BACKEND}. Start the Flask backend and try again.` },
      { status: 502 },
    );
  }
}

export { forward as GET, forward as POST };
