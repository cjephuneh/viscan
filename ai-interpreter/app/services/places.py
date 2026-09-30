"""Nearby pharmacies from OpenStreetMap (Overpass API) - free, no API key."""

import json
import math
import time
import urllib.parse
import urllib.request

_CACHE: dict[tuple, tuple[float, list[dict]]] = {}
CACHE_SECONDS = 600
USER_AGENT = "VIScan/1.0 (cervical screening decision support)"


class PlacesUnavailable(RuntimeError):
    pass


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _address(tags: dict) -> str | None:
    parts = [tags.get("addr:housenumber"), tags.get("addr:street"), tags.get("addr:suburb"), tags.get("addr:city")]
    text = " ".join(p for p in parts if p)
    return text or tags.get("addr:full")


def _query(urls: list[str], query: str) -> dict:
    body = urllib.parse.urlencode({"data": query}).encode()
    last_error = None
    for url in urls:
        request = urllib.request.Request(url.strip(), data=body, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=25) as resp:
                return json.load(resp)
        except Exception as exc:
            last_error = exc
    raise PlacesUnavailable(f"OpenStreetMap lookup failed: {last_error}")


def nearby_pharmacies(lat: float, lng: float, radius_m: int, urls: list[str], limit: int = 40) -> list[dict]:
    key = (round(lat, 3), round(lng, 3), radius_m)
    cached = _CACHE.get(key)
    if cached and time.time() - cached[0] < CACHE_SECONDS:
        return cached[1]

    query = (
        f'[out:json][timeout:20];'
        f'(node["amenity"="pharmacy"](around:{radius_m},{lat},{lng});'
        f'way["amenity"="pharmacy"](around:{radius_m},{lat},{lng}););'
        f'out center {limit * 2};'
    )
    data = _query(urls, query)

    places = []
    for el in data.get("elements", []):
        p_lat = el.get("lat") or (el.get("center") or {}).get("lat")
        p_lng = el.get("lon") or (el.get("center") or {}).get("lon")
        if p_lat is None or p_lng is None:
            continue
        tags = el.get("tags", {})
        places.append({
            "id": f"osm-{el['type']}-{el['id']}",
            "name": tags.get("name") or tags.get("brand") or "Pharmacy (unnamed)",
            "latitude": p_lat,
            "longitude": p_lng,
            "distance_km": round(haversine_km(lat, lng, p_lat, p_lng), 2),
            "address": _address(tags),
            "phone": tags.get("phone") or tags.get("contact:phone"),
            "opening_hours": tags.get("opening_hours"),
            "dispensing": tags.get("dispensing"),
            "osm_url": f"https://www.openstreetmap.org/{el['type']}/{el['id']}",
        })
    places.sort(key=lambda p: p["distance_km"])
    seen, unique = set(), []
    for place in places:
        key_ = (place["name"].lower(), round(place["latitude"], 3), round(place["longitude"], 3))
        if key_ not in seen:
            seen.add(key_)
            unique.append(place)
    places = unique[:limit]
    _CACHE[key] = (time.time(), places)
    return places
