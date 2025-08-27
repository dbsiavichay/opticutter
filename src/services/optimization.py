import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import redis.asyncio as aioredis

from config import config
from src.models.schemas import (
    BoardLayout,
    CacheEntry,
    CostSummary,
    Material,
    MaterialCostSummary,
    OptimizationSummary,
    OptimizeRequest,
    OptimizeResponse,
    PlacedCut,
    WastePiece,
)
from src.utils.hash import canonicalize_optimize_payload, hash_optimize_request

# Redis keys
CACHE_KEY_PREFIX = "opt:"
INDEX_ZSET_KEY = "opt:index"  # score = timestamp, member = request_hash
META_KEY_PREFIX = "optmeta:"


class RedisCache:
    def __init__(self, url: str):
        self._redis = aioredis.from_url(url, decode_responses=True)

    async def close(self):
        try:
            await self._redis.aclose()
        except Exception:
            pass

    async def get(self, key: str) -> Optional[str]:
        try:
            return await self._redis.get(key)
        except Exception:
            return None

    async def set(self, key: str, value: str, ttl: int):
        try:
            await self._redis.set(key, value, ex=ttl)
        except Exception:
            pass

    async def zadd(self, key: str, score: float, member: str):
        try:
            await self._redis.zadd(key, {member: score})
        except Exception:
            pass

    async def zrevrange(self, key: str, start: int, stop: int) -> List[str]:
        try:
            return await self._redis.zrevrange(key, start, stop)
        except Exception:
            return []

    async def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        raw = await self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    async def set_json(self, key: str, value: Dict[str, Any], ttl: int):
        try:
            await self.set(key, json.dumps(value), ttl)
        except Exception:
            pass


cache = RedisCache(config.REDIS_URL)


class Rect:
    __slots__ = ("x", "y", "w", "h")

    def __init__(self, x: int, y: int, w: int, h: int):
        self.x = x
        self.y = y
        self.w = w
        self.h = h

    def area(self) -> int:
        return max(self.w, 0) * max(self.h, 0)

    def fits(self, w: int, h: int) -> bool:
        return w <= self.w and h <= self.h

    def split_after_place(self, pw: int, ph: int, kerf: int) -> List["Rect"]:
        """Assumes the placed rect is anchored at (self.x, self.y).
        Returns two non-overlapping guillotine rectangles: right and bottom, respecting kerf.
        """
        rects: List[Rect] = []
        # Right remainder: to the right of the placed piece, same y, height = ph
        right_x = self.x + pw + kerf
        right_w = (self.x + self.w) - right_x
        if right_w > 0 and ph > 0:
            rects.append(Rect(right_x, self.y, right_w, ph))
        # Bottom remainder: below the placed piece, full width of original free rect
        bottom_y = self.y + ph + kerf
        bottom_h = (self.y + self.h) - bottom_y
        if bottom_h > 0:
            rects.append(Rect(self.x, bottom_y, self.w, bottom_h))
        return rects


class BoardBin:
    def __init__(
        self,
        material: Material,
        index: int,
        kerf: int,
        trims: Tuple[int, int, int, int],
    ):
        self.material = material
        self.index = index
        left, top, right, bottom = trims
        usable_w = max(material.width - (left + right), 0)
        usable_h = max(material.height - (top + bottom), 0)
        self.usable_w = usable_w
        self.usable_h = usable_h
        self.origin_x = left
        self.origin_y = top
        self.free_rects: List[Rect] = [
            Rect(self.origin_x, self.origin_y, usable_w, usable_h)
        ]
        self.placed: List[PlacedCut] = []
        self.kerf = kerf

    def try_place(self, w: int, h: int, label: Optional[str]) -> Optional[PlacedCut]:
        # Choose smallest area free rect that fits to reduce fragmentation
        candidate_idx = -1
        candidate: Optional[Rect] = None
        candidate_score = None
        for i, r in enumerate(self.free_rects):
            if r.fits(w, h):
                score = r.area()
                if candidate is None or score < candidate_score:  # type: ignore
                    candidate = r
                    candidate_idx = i
                    candidate_score = score
        if candidate is None:
            return None
        # Place at top-left of candidate
        px, py = candidate.x, candidate.y
        placed = PlacedCut(x=px, y=py, width=w, height=h, label=label)
        # remove candidate and split
        del self.free_rects[candidate_idx]
        self.free_rects.extend(candidate.split_after_place(w, h, self.kerf))
        self._merge_free_rects()
        self.placed.append(placed)
        return placed

    def _merge_free_rects(self):
        # simple merge: remove contained rects
        pruned: List[Rect] = []
        for r in self.free_rects:
            if not any(
                (r is not o)
                and (r.x >= o.x)
                and (r.y >= o.y)
                and (r.x + r.w <= o.x + o.w)
                and (r.y + r.h <= o.y + o.h)
                for o in self.free_rects
            ):
                pruned.append(r)
        self.free_rects = pruned

    def utilization(self) -> float:
        area_used = sum(p.width * p.height for p in self.placed)
        area_total = max(self.usable_w, 0) * max(self.usable_h, 0)
        return (area_used / area_total) * 100.0 if area_total > 0 else 0.0

    def waste_pieces(self) -> List[WastePiece]:
        waste: List[WastePiece] = []
        for r in self.free_rects:
            if r.w > 0 and r.h > 0:
                waste.append(
                    WastePiece(x=r.x, y=r.y, width=r.w, height=r.h, reusable=True)
                )
        return waste


class Optimizer:
    def __init__(self, req: OptimizeRequest):
        self.req = req
        self.kerf = req.cutting_parameters.kerf
        self.trims = (
            req.cutting_parameters.left_trim,
            req.cutting_parameters.top_trim,
            req.cutting_parameters.right_trim,
            req.cutting_parameters.bottom_trim,
        )
        self.materials = {m.code: m for m in req.materials}

    def run(self) -> Tuple[List[BoardLayout], CostSummary, OptimizationSummary]:
        start = datetime.now(timezone.utc)
        # Expand cuts by quantity
        items: List[
            Tuple[str, int, int, Optional[str], Optional[str]]
        ] = []  # (material, w, h, label, force_grain)
        for c in self.req.cuts:
            for _ in range(c.quantity):
                items.append(
                    (
                        c.material,
                        c.width,
                        c.height,
                        c.label,
                        (c.force_grain.value if c.force_grain else None),
                    )
                )
        # sort by material then by decreasing max(w,h) then area
        items.sort(key=lambda t: (t[0], -max(t[1], t[2]), -(t[1] * t[2])))

        # boards_layout: List[BoardLayout] = []
        boards_by_material: dict[str, List[BoardBin]] = {
            code: [] for code in self.materials.keys()
        }

        for mat_code, w, h, label, force in items:
            mat = self.materials[mat_code]
            placed = None
            # Orientation candidates
            candidates: List[Tuple[int, int]] = [(w, h)]
            allow_rotate = force is None or force == "none"
            if allow_rotate and (w != h):
                candidates.append((h, w))
            # Try place on existing boards first, preferring reuse of waste
            for bw, bh in candidates:
                for bin in boards_by_material[mat_code]:
                    placed = bin.try_place(bw, bh, label)
                    if placed:
                        break
                if placed:
                    break
            # If not placed, open a new board and try again
            if not placed:
                bin = BoardBin(
                    mat,
                    index=len(boards_by_material[mat_code]) + 1,
                    kerf=self.kerf,
                    trims=self.trims,
                )
                boards_by_material[mat_code].append(bin)
                for bw, bh in candidates:
                    placed = bin.try_place(bw, bh, label)
                    if placed:
                        break
            if not placed:
                raise ValueError(
                    f"Unable to place cut {label or ''} {w}x{h} on material {mat_code}"
                )

        # Build layouts and costs
        layout_list: List[BoardLayout] = []
        total_boards_used = 0
        material_costs: List[MaterialCostSummary] = []
        total_cost = 0.0
        total_usable_area = 0
        total_used_area = 0

        for mat_code, bins in boards_by_material.items():
            if not bins:
                continue
            mat = self.materials[mat_code]
            for i, bin in enumerate(bins):
                used_area = sum(p.width * p.height for p in bin.placed)
                board_usable_area = bin.usable_w * bin.usable_h
                total_usable_area += board_usable_area
                total_used_area += used_area
                layout_list.append(
                    BoardLayout(
                        material=mat_code,
                        index=i + 1,
                        cuts_placed=bin.placed,
                        utilization_percentage=bin.utilization(),
                        waste_pieces=bin.waste_pieces(),
                    )
                )
            count = len(bins)
            total_boards_used += count
            cost = count * float(mat.price)
            total_cost += cost
            material_costs.append(
                MaterialCostSummary(
                    material=mat_code,
                    boards_used=count,
                    unit_cost=float(mat.price),
                    total_cost=cost,
                )
            )

        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        summary = OptimizationSummary(
            project_name=self.req.project_name,
            total_boards_used=total_boards_used,
            total_cost=total_cost,
            total_waste_percentage=(1.0 - (total_used_area / max(total_usable_area, 1)))
            * 100.0,
            optimization_time=f"{elapsed:.3f}s",
        )
        cost_summary = CostSummary(
            materials=material_costs, total_material_cost=total_cost
        )
        return layout_list, cost_summary, summary


async def optimize_with_cache(payload: Dict[str, Any]) -> OptimizeResponse:
    req = OptimizeRequest(**payload)
    canonical = canonicalize_optimize_payload(req)
    h = hash_optimize_request(canonical)
    key = f"{CACHE_KEY_PREFIX}{h}"
    # Attempt cache hit
    cached_raw = await cache.get(key)
    if cached_raw:
        try:
            data = json.loads(cached_raw)
            resp = OptimizeResponse(**data)
            resp.cached = True
            resp.request_hash = h
            return resp
        except Exception:
            pass
    # Compute
    optimizer = Optimizer(req)
    boards_layout, cost_summary, summary = optimizer.run()
    resp = OptimizeResponse(
        optimization_summary=summary,
        cost_summary=cost_summary,
        boards_layout=boards_layout,
        cached=False,
        request_hash=h,
    )
    # Store in cache and index
    now = datetime.now(timezone.utc).isoformat()
    entry = CacheEntry(request_hash=h, timestamp_utc=now, result=resp)
    ttl = int(getattr(config, "OPT_RESULT_TTL_SECONDS", 259200))
    try:
        await cache.set(key, json.dumps(resp.model_dump()), ttl)
        await cache.set_json(f"{META_KEY_PREFIX}{h}", entry.model_dump(), ttl)
        await cache.zadd(
            INDEX_ZSET_KEY, score=datetime.now(timezone.utc).timestamp(), member=h
        )
    except Exception:
        pass
    return resp


async def get_cached_by_hash(h: str) -> Optional[CacheEntry]:
    data = await cache.get_json(f"{META_KEY_PREFIX}{h}")
    if not data:
        # try rebuild from main cache if exists
        raw = await cache.get(f"{CACHE_KEY_PREFIX}{h}")
        if not raw:
            return None
        try:
            resp = OptimizeResponse(**json.loads(raw))
            entry = CacheEntry(
                request_hash=h,
                timestamp_utc=datetime.now(timezone.utc).isoformat(),
                result=resp,
            )
            return entry
        except Exception:
            return None
    return CacheEntry(**data)


async def list_recent_optimizations(
    offset: int = 0, limit: int = 10
) -> List[CacheEntry]:
    # zrevrange is inclusive stop index
    hashes = await cache.zrevrange(INDEX_ZSET_KEY, offset, offset + limit - 1)
    items: List[CacheEntry] = []
    for h in hashes:
        item = await get_cached_by_hash(h)
        if item:
            items.append(item)
    return items
