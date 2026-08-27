# -*- coding: utf-8 -*-
"""GPS Intelligence — route auditing and dispatch planning.

Direct Python port of the StarX/holodBot Node.js engine (src/server/routing.js +
src/server/routeEngine.js). Deliberately framework-agnostic — no Odoo ORM import here,
just plain Python over lists/dicts/tuples — so it stays testable on its own and mirrors
how the original was designed (routing.js never touched Google Sheets/Supabase either).

The solver is nearest-neighbour + 2-opt, NOT OR-Tools (a C++/Python library that would
be its own deployment dependency). For the stop counts this deals with — one worker's
day, typically 5-20 stops — 2-opt lands within a few percent of the exact optimum,
comfortably inside the error margin of straight-line distance anyway.
"""
import math

EARTH_KM = 6371.0


def haversine_km(a, b):
    """a, b: (lat, lng) tuples. Great-circle distance in km."""
    lat1, lng1 = a
    lat2, lng2 = b
    to_rad = math.radians
    d_lat = to_rad(lat2 - lat1)
    d_lng = to_rad(lng2 - lng1)
    s = (
        math.sin(d_lat / 2) ** 2
        + math.cos(to_rad(lat1)) * math.cos(to_rad(lat2)) * math.sin(d_lng / 2) ** 2
    )
    return EARTH_KM * 2 * math.asin(math.sqrt(s))


def straight_minutes(km, avg_speed_kmh):
    """Minutes for a straight-line leg at an assumed average speed. Deliberately
    crude — it exists so "driving time" has *a* number when there's no real routing
    provider; callers must label it as an estimate, never as measured."""
    kmh = avg_speed_kmh if avg_speed_kmh and avg_speed_kmh > 0 else 30
    return (km / kmh) * 60


def build_matrix(points, avg_speed_kmh):
    """points: list of (lat, lng). Returns {"km": [[...]], "minutes": [[...]]}.
    Straight-line only — there is no Google Distance Matrix equivalent wired up here
    yet (see routing.js's `googleMatrix` for how that would plug in on the Node side)."""
    n = len(points)
    km = [[0.0] * n for _ in range(n)]
    minutes = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            d = haversine_km(points[i], points[j])
            km[i][j] = d
            minutes[i][j] = straight_minutes(d, avg_speed_kmh)
    return {"km": km, "minutes": minutes}


def total_km(order, matrix):
    d = 0.0
    for i in range(1, len(order)):
        d += matrix["km"][order[i - 1]][order[i]]
    return d


def nearest_neighbour_order(matrix, n):
    visited = [False] * n
    order = [0]
    visited[0] = True
    for _ in range(1, n):
        last = order[-1]
        best, best_d = -1, float("inf")
        for j in range(n):
            if visited[j]:
                continue
            if matrix["km"][last][j] < best_d:
                best_d, best = matrix["km"][last][j], j
        if best < 0:
            break
        order.append(best)
        visited[best] = True
    return order


def two_opt_improve(order, matrix):
    """The start is pinned (i starts at 1) — only the tail gets resequenced. This
    matches the original's design intent: "given where the day began, should the
    rest have been ordered differently", not "where should the day have begun"."""
    best = list(order)
    best_d = total_km(best, matrix)
    improved = True
    guard = 0
    while improved and guard < 60:
        guard += 1
        improved = False
        for i in range(1, len(best) - 1):
            for j in range(i + 1, len(best)):
                cand = best[:i] + list(reversed(best[i:j + 1])) + best[j + 1:]
                d = total_km(cand, matrix)
                if d < best_d - 1e-9:
                    best, best_d = cand, d
                    improved = True
    return best, best_d


def solve(points, avg_speed_kmh):
    """points: list of (lat, lng). Returns (matrix, order, km)."""
    if len(points) < 2:
        matrix = build_matrix(points, avg_speed_kmh)
        return matrix, list(range(len(points))), 0.0
    matrix = build_matrix(points, avg_speed_kmh)
    nn = nearest_neighbour_order(matrix, len(points))
    order, km = two_opt_improve(nn, matrix)
    return matrix, order, km


# ── Historical audit ────────────────────────────────────────────────────────────
# A check-in records the ARRIVAL only — there is no departure event. So the clock gap
# between two consecutive check-ins is (time spent at the first point + travel time),
# and travel time ALONE is not recoverable. That rules out a time-based detour test:
# the gap exceeds the drive estimate on essentially every leg simply because the
# worker was doing their job at the point, which would tag everything and mean
# nothing. What the data DOES support:
#   - Excessive Idle Time: the gap is far larger than the drive can explain.
#   - Route Detour: the worker drove much further than the nearest stop they had not
#     visited yet — a genuinely questionable sequencing choice.
IDLE_MIN_FLAG = 90       # minutes unexplained by driving before it reads as excessive
DETOUR_KM_FACTOR = 2.5   # leg distance vs. the nearest still-unvisited stop
DETOUR_KM_MIN = 3.0      # never flag short hops, where the ratio is noise


def tag_leg(dwell_min, km, nearest_unvisited_km):
    tags = []
    if dwell_min >= IDLE_MIN_FLAG:
        tags.append("Excessive Idle Time")
    if nearest_unvisited_km is not None and km > max(DETOUR_KM_MIN, nearest_unvisited_km * DETOUR_KM_FACTOR):
        tags.append("Route Detour")
    return tags


def audit_worker_day(stops, avg_speed_kmh):
    """stops: list of {"ms": epoch_millis, "time": "HH:MM", "coord": (lat,lng),
    "point": name} sorted or not (sorted here). Mirrors holodBot's auditAgentDay /
    StarX's auditWorkerDay exactly, minus the fuel-cost estimate (no per-tenant fuel
    price config in this module — add it back if a customer asks)."""
    stops = sorted(stops, key=lambda s: s["ms"])
    if len(stops) < 2:
        return {
            "stops": stops, "legs": [], "actual_km": 0.0, "optimal_km": 0.0,
            "efficiency_pct": None, "wasted_km": 0.0, "optimal_order": [],
            "note": "not_enough_points",
        }

    points = [s["coord"] for s in stops]
    matrix = build_matrix(points, avg_speed_kmh)
    actual_order = list(range(len(stops)))  # already chronological
    actual_km = total_km(actual_order, matrix)
    nn = nearest_neighbour_order(matrix, len(points))
    optimal_order, optimal_km = two_opt_improve(nn, matrix)

    legs = []
    driving_min = dwell_min_total = 0.0
    for i in range(1, len(stops)):
        prev, cur = stops[i - 1], stops[i]
        actual_min = (cur["ms"] - prev["ms"]) / 60000.0
        expected_min = matrix["minutes"][i - 1][i]
        dwell = max(0.0, actual_min - expected_min)
        driving_min += min(actual_min, expected_min)
        dwell_min_total += dwell

        nearest_unvisited_km = None
        for j in range(i, len(stops)):
            d = matrix["km"][i - 1][j]
            if nearest_unvisited_km is None or d < nearest_unvisited_km:
                nearest_unvisited_km = d
        km = matrix["km"][i - 1][i]
        legs.append({
            "seq": i, "from_point": prev["point"], "to_point": cur["point"],
            "departure": prev["time"], "arrival": cur["time"],
            "km": km, "actual_min": actual_min, "expected_min": expected_min,
            "dwell_min": dwell, "nearest_unvisited_km": nearest_unvisited_km,
            "tags": tag_leg(dwell, km, nearest_unvisited_km),
        })

    efficiency_pct = (optimal_km / actual_km * 100) if actual_km > 0 else None
    wasted_km = max(0.0, actual_km - optimal_km)

    return {
        "stops": stops, "legs": legs,
        "actual_km": actual_km, "optimal_km": optimal_km,
        "efficiency_pct": efficiency_pct, "wasted_km": wasted_km,
        "optimal_order": optimal_order, "driving_min": driving_min,
        "dwell_min": dwell_min_total,
    }


# ── Forward planner ─────────────────────────────────────────────────────────────
def plan_route(stops, start_time_str, avg_speed_kmh):
    """stops: list of {"point_id", "name", "address", "coord": (lat,lng)}.
    Start is pinned to the first entry — the caller (the wizard) controls where the
    day begins by the order it hands stops in."""
    routable = [s for s in stops if s.get("coord")]
    if len(routable) < 2:
        return {
            "stops": [dict(s, sequence=i + 1, eta="") for i, s in enumerate(routable)],
            "total_km": 0.0, "total_min": 0.0, "skipped": len(stops) - len(routable),
        }

    points = [s["coord"] for s in routable]
    matrix, order, km = solve(points, avg_speed_kmh)

    try:
        h, m = start_time_str.split(":")
        start_min = int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        start_min = 9 * 60

    def hhmm(mins):
        t = int(round(mins)) % 1440
        return "%02d:%02d" % (t // 60, t % 60)

    clock, total_min = start_min, 0.0
    out = []
    for pos, idx in enumerate(order):
        if pos > 0:
            leg_min = matrix["minutes"][order[pos - 1]][idx]
            clock += leg_min
            total_min += leg_min
        s = routable[idx]
        out.append({
            "sequence": pos + 1, "point_id": s.get("point_id", ""),
            "name": s.get("name", ""), "address": s.get("address", ""),
            "coord": s["coord"], "eta": hhmm(clock),
        })

    return {"stops": out, "total_km": km, "total_min": total_min, "skipped": len(stops) - len(routable)}
