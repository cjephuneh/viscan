from __future__ import annotations

import math
from typing import Any

import httpx
from flask import current_app

from app.errors import APIError
from app.models import Facility


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def calculate_distance(
    origin_latitude: float,
    origin_longitude: float,
    destination_latitude: float,
    destination_longitude: float,
) -> dict[str, Any]:
    distance_km = haversine_km(
        origin_latitude, origin_longitude, destination_latitude, destination_longitude
    )
    return {
        "distance_km": round(distance_km, 3),
        "origin": {"latitude": origin_latitude, "longitude": origin_longitude},
        "destination": {
            "latitude": destination_latitude,
            "longitude": destination_longitude,
        },
        "provider": "local-haversine",
    }


def nearby_facilities(
    latitude: float, longitude: float, radius_km: float = 25.0
) -> list[dict[str, Any]]:
    provider_url = current_app.config.get("MAPS_API_URL") or ""
    api_key = current_app.config.get("MAPS_API_KEY") or ""

    if provider_url and api_key:
        return _provider_nearby(provider_url, api_key, latitude, longitude, radius_km)

    facilities = (
        Facility.query.filter_by(is_active=True)
        .filter(Facility.latitude.isnot(None), Facility.longitude.isnot(None))
        .all()
    )
    results: list[dict[str, Any]] = []
    for facility in facilities:
        distance = haversine_km(latitude, longitude, facility.latitude, facility.longitude)
        if distance <= radius_km:
            results.append(
                {
                    "id": facility.id,
                    "name": facility.name,
                    "type": facility.type,
                    "latitude": facility.latitude,
                    "longitude": facility.longitude,
                    "distance_km": round(distance, 3),
                }
            )
    results.sort(key=lambda item: item["distance_km"])
    return results


def _provider_nearby(
    provider_url: str,
    api_key: str,
    latitude: float,
    longitude: float,
    radius_km: float,
) -> list[dict[str, Any]]:
    timeout = current_app.config["EXTERNAL_TIMEOUT_SECONDS"]
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(
                provider_url.rstrip("/") + "/nearby",
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "radius_km": radius_km,
                    "api_key": api_key,
                },
            )
    except httpx.RequestError as exc:
        raise APIError("Maps provider is unavailable.", 503) from exc

    if response.status_code >= 400:
        raise APIError("Maps provider rejected the request.", 502)

    try:
        payload = response.json()
    except ValueError as exc:
        raise APIError("Maps provider returned an invalid response.", 502) from exc

    if not isinstance(payload, list):
        raise APIError("Maps provider returned an invalid response.", 502)
    return payload
