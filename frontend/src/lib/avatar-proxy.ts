import type { NextRequest } from "next/server";

/**
 * Forwards a request to the ai-avatar service (video reports + embeddable player).
 *
 * In production nginx routes `/api/v1/reports/*` and `/player/*` straight to
 * ai-avatar, so these handlers only run in local development (no gateway).
 */
const AVATAR = process.env.VISCAN_AVATAR_URL ?? "http://127.0.0.1:9090";
const PASS_THROUGH = ["content-type", "content-disposition", "cache-control"];

export async function forwardToAvatar(request: NextRequest, pathname: string) {
  const target = new URL(pathname, AVATAR);
  target.search = request.nextUrl.search;

  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  const accept = request.headers.get("accept");
  if (accept) headers.set("accept", accept);

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
      { error: `The video report service is not reachable at ${AVATAR}. Start ai-avatar and try again.` },
      { status: 502 },
    );
  }
}
