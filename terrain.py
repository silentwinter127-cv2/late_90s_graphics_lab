# SPDX-License-Identifier: GPL-3.0-or-later
"""
02 — Terrain Lab: 4-Stage Composable Procedural Heightfield & Mesh Generator (v2.1).
CRITICAL FIX:
- Updates `SDS_Terrain` mesh in-place using `mesh.clear_geometry()` + `mesh.from_pydata()`
  instead of calling `bpy.data.meshes.remove()`, completely eliminating
  `ReferenceError: StructRNA of type Mesh has been removed` when switching presets
  or regenerating terrain in Terrain Lab!
- Adds `KARST_DOMES` (群峰花岗岩穹顶 — Ref Image 4) with 9 multi-depth clustered granite domes.
"""

import math
from typing import List, Tuple, Dict, Any

try:
    import bpy
except ImportError:
    bpy = None


def _hash2d(ix: int, iy: int, seed: int) -> float:
    n = (ix * 374761393 + iy * 668265263 + seed * 1442695041) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    n = n ^ (n >> 16)
    return (n & 0x7FFFFFFF) / float(0x7FFFFFFF)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _smoothstep(t: float) -> float:
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def value_noise_2d(x: float, y: float, seed: int) -> float:
    ix = math.floor(x)
    iy = math.floor(y)
    fx = x - ix
    fy = y - iy
    u = _smoothstep(fx)
    v = _smoothstep(fy)

    n00 = _hash2d(ix, iy, seed)
    n10 = _hash2d(ix + 1, iy, seed)
    n01 = _hash2d(ix, iy + 1, seed)
    n11 = _hash2d(ix + 1, iy + 1, seed)

    nx0 = _lerp(n00, n10, u)
    nx1 = _lerp(n01, n11, u)
    return _lerp(nx0, nx1, v) * 2.0 - 1.0


def voronoi_ridge_2d(x: float, y: float, seed: int) -> Tuple[float, float]:
    ix = math.floor(x)
    iy = math.floor(y)
    f1 = 10.0
    f2 = 10.0

    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            cx = ix + dx
            cy = iy + dy
            jx = _hash2d(cx, cy, seed + 101)
            jy = _hash2d(cx, cy, seed + 202)
            px = cx + jx
            py = cy + jy
            dist = math.hypot(x - px, y - py)
            if dist < f1:
                f2 = f1
                f1 = dist
            elif dist < f2:
                f2 = dist

    f1_clamped = min(1.0, max(0.0, f1))
    ridge = min(1.0, max(0.0, f2 - f1))
    return f1_clamped, ridge


def fbm_2d(
    x: float,
    y: float,
    seed: int,
    octaves: int = 5,
    persistence: float = 0.50,
    lacunarity: float = 2.05,
    ridged: bool = False,
) -> float:
    total = 0.0
    amplitude = 1.0
    frequency = 1.0
    max_amp = 0.0

    for i in range(max(1, octaves)):
        rx = x * frequency * 0.98 - y * frequency * 0.19
        ry = x * frequency * 0.19 + y * frequency * 0.98
        n = value_noise_2d(rx, ry, seed + i * 313)
        if ridged:
            n = 1.0 - abs(n)
            n = n * n
        else:
            n = (n + 1.0) * 0.5
        total += n * amplitude
        max_amp += amplitude
        amplitude *= persistence
        frequency *= lacunarity

    return total / max(1e-6, max_amp)


def smooth_falloff(val: float, edge0: float, edge1: float) -> float:
    t = max(0.0, min(1.0, (val - edge0) / max(1e-6, edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def _stage_a_base_height(
    nx: float,
    ny: float,
    mode: str,
    scale: float,
    detail_norm: float,
    sharpness_norm: float,
    seed: int,
) -> float:
    if mode == "CHECKER_PLANE":
        return 0.0

    octaves = int(2 + round(detail_norm * 4))
    persistence = 0.42 + detail_norm * 0.18
    sx = nx * scale
    sy = ny * scale

    base_fbm = fbm_2d(sx, sy, seed, octaves=octaves, persistence=persistence, ridged=False)
    ridged_fbm = fbm_2d(sx * 1.15, sy * 1.15, seed + 77, octaves=octaves, persistence=persistence, ridged=True)
    f1, vor_ridge = voronoi_ridge_2d(sx * 0.85, sy * 0.85, seed + 333)

    h = _lerp(base_fbm, ridged_fbm, sharpness_norm * 0.78)
    h = _lerp(h, (1.0 - vor_ridge) * 0.45 + h * 0.55, sharpness_norm * 0.35)

    r = math.hypot(nx, ny)

    if mode == "FRACTAL_MOUNTAINS":
        shore_mask = smooth_falloff(ny, -0.42, -0.12)
        hero_peak = math.exp(-(((nx + 0.04) ** 2) / 0.065 + ((ny - 0.12) ** 2) / 0.075)) * 1.35
        right_knoll = math.exp(-(((nx - 0.48) ** 2) / 0.07 + ((ny - 0.02) ** 2) / 0.08)) * 0.72
        left_knoll = math.exp(-(((nx + 0.58) ** 2) / 0.08 + ((ny - 0.05) ** 2) / 0.09)) * 0.68
        back_peaks = (
            math.exp(-(((nx - 0.28) ** 2) / 0.08 + ((ny - 0.52) ** 2) / 0.09)) * 0.95
            + math.exp(-(((nx - 0.72) ** 2) / 0.09 + ((ny - 0.48) ** 2) / 0.10)) * 0.90
        )
        foothill_shelf = 0.24 * shore_mask
        peaks_env = max(hero_peak, right_knoll, left_knoll, back_peaks)
        h = shore_mask * (foothill_shelf * (0.5 + 0.5 * base_fbm) + peaks_env * (0.42 + 0.78 * h))

    elif mode == "KARST_DOMES":
        # Ref Image 4 (`9lFBJ8s...jpg`): Clustered steep granite domes across foreground, midground & far distance
        shore_mask = smooth_falloff(ny, -0.52, -0.22)
        domes = [
            # (cx, cy, radius_sq, height_mult)
            (-0.12, -0.18, 0.032, 0.52),
            (0.42, -0.16, 0.038, 0.64),
            (-0.62, -0.05, 0.045, 0.82),
            (-0.26, 0.06, 0.036, 0.78),
            (0.28, 0.08, 0.034, 0.70),
            (0.75, 0.04, 0.045, 0.85),
            (-0.48, 0.36, 0.055, 1.12),
            (0.06, 0.42, 0.062, 1.08),
            (-0.82, 0.48, 0.070, 1.05),
            (-0.18, 0.68, 0.065, 1.02),
        ]
        dome_val = 0.0
        for cx, cy, r_sq, hm in domes:
            d2 = (nx - cx) ** 2 + (ny - cy) ** 2
            # Steep sided, rounded top granite dome envelope
            bell = math.exp(-((d2 / r_sq) ** 1.35)) * hm
            if bell > dome_val:
                dome_val = bell
        valley_bench = 0.18 * shore_mask * (0.6 + 0.4 * base_fbm)
        h = shore_mask * (valley_bench + dome_val * (0.68 + 0.38 * h))

    elif mode == "ISOLATED_PEAKS":
        # Ref Image 1 (`dT6cACN...jpg`): Dramatic central jagged volcanic island spire + distant left spire
        island_apron = math.exp(-(((nx - 0.02) ** 2) / 0.20 + ((ny - 0.05) ** 2) / 0.16)) * 0.28
        main_spire = math.exp(-(((nx - 0.02) ** 2) / 0.042 + ((ny - 0.08) ** 2) / 0.042)) * 1.45
        sub_spire = math.exp(-(((nx + 0.18) ** 2) / 0.025 + ((ny + 0.02) ** 2) / 0.025)) * 0.78
        distant_left_spire = math.exp(-(((nx + 0.68) ** 2) / 0.035 + ((ny - 0.55) ** 2) / 0.035)) * 1.05
        envelope = max(island_apron, main_spire, sub_spire, distant_left_spire)
        h = envelope * (0.35 + 0.85 * (h ** (1.20 - 0.25 * sharpness_norm)))

    elif mode == "BASIN_CRATER":
        ring = math.exp(-((r - 0.58) ** 2) / 0.08)
        bowl = max(0.0, 1.0 - (r / 0.50) ** 2) * 0.55
        h = max(0.0, h * (0.35 + 0.95 * ring) - bowl)

    elif mode == "CANYON_CLIFFS":
        meander = 0.25 * math.sin(ny * 3.2)
        canyon_dist = abs(nx - meander)
        canyon_wall = smooth_falloff(canyon_dist, 0.10, 0.42)
        h = (0.20 + 0.80 * h) * canyon_wall

    elif mode == "COASTAL_ARCHIPELAGO":
        island_mask = max(0.0, 1.0 - (r * 0.88) ** 2)
        bay = smooth_falloff(math.hypot(nx, ny + 0.42), 0.18, 0.65)
        h = h * island_mask * bay

    elif mode == "FLOATING_ISLANDS":
        c1 = math.exp(-(((nx) ** 2 + (ny - 0.08) ** 2) / 0.16))
        c2 = math.exp(-(((nx + 0.48) ** 2 + (ny - 0.22) ** 2) / 0.10))
        c3 = math.exp(-(((nx - 0.48) ** 2 + (ny + 0.22) ** 2) / 0.10))
        cluster = max(c1, c2 * 0.9, c3 * 0.85)
        h = max(0.0, (h * cluster - 0.16) * 1.5)

    return max(0.0, min(1.5, h))


def _stage_b_sculpt_grid(
    grid: List[List[float]],
    res: int,
    erosion_norm: float,
    sharpness_norm: float,
    terrace_steps: int,
    plateau_clip: float,
    seed: int,
) -> List[List[float]]:
    out = [row[:] for row in grid]

    power = max(0.65, 1.40 - sharpness_norm * 0.55)
    clip_val = max(0.25, min(1.5, plateau_clip))
    for y in range(res):
        for x in range(res):
            v = max(0.0, out[y][x])
            v = v ** power
            if v > clip_val:
                v = clip_val + (v - clip_val) * 0.1
            out[y][x] = v

    if erosion_norm > 0.02:
        iterations = max(1, int(round(erosion_norm * 3)))
        talus = 0.020
        rate = 0.24 * erosion_norm
        for _ in range(iterations):
            nxt = [row[:] for row in out]
            for y in range(1, res - 1):
                for x in range(1, res - 1):
                    c = out[y][x]
                    lowest = min(
                        out[y - 1][x], out[y + 1][x], out[y][x - 1], out[y][x + 1]
                    )
                    diff = c - lowest
                    if diff > talus:
                        ch = 0.65 + 0.5 * _hash2d(x, y, seed + 909)
                        nxt[y][x] = max(lowest, c - (diff - talus) * rate * ch)
            out = nxt

    if terrace_steps > 1:
        steps = float(terrace_steps)
        for y in range(res):
            for x in range(res):
                v = out[y][x]
                stepped = math.floor(v * steps) / steps
                out[y][x] = _lerp(v, stepped, 0.78)

    return out


def compute_heightfield_data(
    res: int = 128,
    size: float = 44.0,
    mode: str = "FRACTAL_MOUNTAINS",
    relief_pct: float = 64.0,
    detail_pct: float = 54.0,
    erosion_pct: float = 36.0,
    sharpness_pct: float = 66.0,
    scale: float = 2.6,
    terrace_steps: int = 0,
    plateau_clip: float = 1.0,
    seed: int = 1997,
) -> Dict[str, Any]:
    res = max(8, int(res))
    relief_norm = max(0.0, min(1.5, relief_pct / 100.0))
    detail_norm = max(0.0, min(1.0, detail_pct / 100.0))
    erosion_norm = max(0.0, min(1.0, erosion_pct / 100.0))
    sharpness_norm = max(0.0, min(1.0, sharpness_pct / 100.0))

    raw_grid: List[List[float]] = [[0.0] * res for _ in range(res)]
    for y in range(res):
        ny = (y / float(res - 1)) * 2.0 - 1.0
        for x in range(res):
            nx = (x / float(res - 1)) * 2.0 - 1.0
            raw_grid[y][x] = _stage_a_base_height(
                nx, ny, mode, scale, detail_norm, sharpness_norm, seed
            )

    sculpted = _stage_b_sculpt_grid(
        raw_grid, res, erosion_norm, sharpness_norm, terrace_steps, plateau_clip, seed
    )

    s_min = min(min(r) for r in sculpted)
    s_max = max(max(r) for r in sculpted)
    s_span = max(1e-5, s_max - s_min)

    max_height = 14.5 * relief_norm
    if mode == "CHECKER_PLANE" or relief_norm < 0.01:
        base_z_offset = 0.0
    elif mode == "FLOATING_ISLANDS":
        base_z_offset = 1.6
    elif mode == "ISOLATED_PEAKS":
        base_z_offset = -0.35 * max(0.35, relief_norm)
    else:
        base_z_offset = -0.85 * max(0.35, relief_norm)

    verts: List[Tuple[float, float, float]] = []
    altitudes: List[float] = []
    slopes: List[float] = []

    half = size * 0.5
    cell_size = size / float(res - 1)

    z_grid: List[List[float]] = [[0.0] * res for _ in range(res)]
    min_z = 1e9
    max_z = -1e9
    for y in range(res):
        for x in range(res):
            norm_v = (sculpted[y][x] - s_min) / s_span if mode != "CHECKER_PLANE" else 0.0
            z = norm_v * max_height + base_z_offset
            z_grid[y][x] = z
            if z < min_z:
                min_z = z
            if z > max_z:
                max_z = z

    z_span = max(1e-4, max_z - min_z)

    for y in range(res):
        py = -half + y * cell_size
        for x in range(res):
            px = -half + x * cell_size
            pz = z_grid[y][x]
            verts.append((px, py, pz))

            alt = (pz - min_z) / z_span
            altitudes.append(max(0.0, min(1.0, alt)))

            x0 = max(0, x - 1)
            x1 = min(res - 1, x + 1)
            y0 = max(0, y - 1)
            y1 = min(res - 1, y + 1)
            dzdx = (z_grid[y][x1] - z_grid[y][x0]) / max(1e-5, (x1 - x0) * cell_size)
            dzdy = (z_grid[y1][x] - z_grid[y0][x]) / max(1e-5, (y1 - y0) * cell_size)
            grad = math.hypot(dzdx, dzdy)
            slope_norm = min(1.0, grad / 2.2)
            slopes.append(slope_norm)

    faces: List[Tuple[int, ...]] = []
    for y in range(res - 1):
        row_start = y * res
        next_row = (y + 1) * res
        for x in range(res - 1):
            v0 = row_start + x
            v1 = row_start + x + 1
            v2 = next_row + x + 1
            v3 = next_row + x
            if res <= 32:
                # Explicit PS1 triangle pairs with alternating diagonal for authentic angular facets
                if (x + y) % 2 == 0:
                    faces.append((v0, v1, v2))
                    faces.append((v0, v2, v3))
                else:
                    faces.append((v0, v1, v3))
                    faces.append((v1, v2, v3))
            else:
                faces.append((v0, v1, v2, v3))

    return {
        "verts": verts,
        "faces": faces,
        "altitudes": altitudes,
        "slopes": slopes,
        "min_z": min_z,
        "max_z": max_z,
        "resolution": res,
    }


def _resolution_from_enum(res_enum: str) -> int:
    mapping = {
        "RES_16": 16,
        "RES_24": 24,
        "RES_64": 64,
        "RES_128": 128,
        "RES_192": 192,
        "RES_256": 256,
    }
    return mapping.get(res_enum, 128)


def _ensure_rock_scatter_geonodes(props: Any, terrain_mat: Any = None) -> Any:
    if bpy is None:
        return None

    group_name = "SDS_Terrain_Rocks_GN"
    node_group = bpy.data.node_groups.get(group_name)
    if node_group is None:
        node_group = bpy.data.node_groups.new(group_name, "GeometryNodeTree")

    nodes = node_group.nodes
    links = node_group.links
    nodes.clear()

    if hasattr(node_group, "interface"):
        for item in list(node_group.interface.items_tree):
            node_group.interface.remove(item)
        node_group.interface.new_socket(
            name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry"
        )
        node_group.interface.new_socket(
            name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry"
        )
    else:
        node_group.inputs.clear()
        node_group.outputs.clear()
        node_group.inputs.new("NodeSocketGeometry", "Geometry")
        node_group.outputs.new("NodeSocketGeometry", "Geometry")

    n_in = nodes.new("NodeGroupInput")
    n_in.location = (-680, 0)
    n_out = nodes.new("NodeGroupOutput")
    n_out.location = (680, 0)

    n_join = nodes.new("GeometryNodeJoinGeometry")
    n_join.location = (440, 0)

    try:
        n_dist = nodes.new("GeometryNodeDistributePointsOnFaces")
        n_dist.location = (-360, -180)
        density_val = max(0.0, float(getattr(props, "rock_density", 8.0))) * 0.0012
        if "Density" in n_dist.inputs:
            n_dist.inputs["Density"].default_value = density_val
        if "Seed" in n_dist.inputs:
            n_dist.inputs["Seed"].default_value = int(getattr(props, "seed", 1997))

        n_ico = nodes.new("GeometryNodeMeshIcoSphere")
        n_ico.location = (-360, -380)
        if "Radius" in n_ico.inputs:
            n_ico.inputs["Radius"].default_value = 0.85
        if "Subdivisions" in n_ico.inputs:
            n_ico.inputs["Subdivisions"].default_value = 1

        n_set_mat = nodes.new("GeometryNodeSetMaterial")
        n_set_mat.location = (-120, -380)
        if terrain_mat is not None and "Material" in n_set_mat.inputs:
            n_set_mat.inputs["Material"].default_value = terrain_mat

        n_inst = nodes.new("GeometryNodeInstanceOnPoints")
        n_inst.location = (140, -220)

        links.new(n_in.outputs[0], n_join.inputs["Geometry"])
        links.new(n_in.outputs[0], n_dist.inputs["Mesh"])
        links.new(n_dist.outputs["Points"], n_inst.inputs["Points"])
        links.new(n_ico.outputs["Mesh"], n_set_mat.inputs["Geometry"])
        links.new(n_set_mat.outputs["Geometry"], n_inst.inputs["Instance"])
        links.new(n_inst.outputs["Instances"], n_join.inputs["Geometry"])
        links.new(n_join.outputs["Geometry"], n_out.inputs[0])
    except Exception:
        links.new(n_in.outputs[0], n_out.inputs[0])

    return node_group


def generate_or_update_terrain(context: Any, props: Any, collection: Any, terrain_mat: Any = None) -> Any:
    """
    Stage D: Builds or updates `SDS_Terrain` in-place using `mesh.clear_geometry()`.
    Never removes `Mesh` datablocks, guaranteeing zero `StructRNA has been removed` errors!
    """
    if bpy is None:
        return None

    res = _resolution_from_enum(getattr(props, "mesh_resolution", "RES_128"))
    data = compute_heightfield_data(
        res=res,
        size=44.0,
        mode=getattr(props, "terrain_mode", "FRACTAL_MOUNTAINS"),
        relief_pct=getattr(props, "terrain_relief", 64.0),
        detail_pct=getattr(props, "fractal_detail", 54.0),
        erosion_pct=getattr(props, "erosion_strength", 36.0),
        sharpness_pct=getattr(props, "sharpness", 66.0),
        scale=getattr(props, "terrain_scale", 2.6),
        terrace_steps=getattr(props, "terrace_steps", 0),
        plateau_clip=getattr(props, "plateau_clip", 1.0),
        seed=getattr(props, "seed", 1997),
    )

    mesh_name = "SDS_Terrain_Mesh"
    obj_name = "SDS_Terrain"

    obj = bpy.data.objects.get(obj_name)
    if obj is not None and obj.type == "MESH" and obj.data is not None:
        mesh = obj.data
        if hasattr(mesh, "clear_geometry"):
            mesh.clear_geometry()
    else:
        mesh = bpy.data.meshes.get(mesh_name)
        if mesh is not None and hasattr(mesh, "clear_geometry"):
            mesh.clear_geometry()
        else:
            mesh = bpy.data.meshes.new(mesh_name)

    mesh.from_pydata(data["verts"], [], data["faces"])
    mesh.update()
    try:
        from . import dreamspace
        dreamspace.cache_base_vertices(mesh)
    except Exception:
        pass

    flat_shaded = (
        bool(getattr(props, "flat_shaded_terrain", False))
        or getattr(props, "era_pipeline", "") == "PS1_1998_LSD"
        or getattr(props, "shading_interpolation", "") == "FLAT_FACETED"
        or res <= 32
    )
    for poly in mesh.polygons:
        poly.use_smooth = not flat_shaded

    try:
        if hasattr(mesh, "color_attributes"):
            existing_attr = mesh.color_attributes.get("sds_data")
            if existing_attr is not None:
                mesh.color_attributes.remove(existing_attr)
            col_attr = mesh.color_attributes.new(
                name="sds_data", type="FLOAT_COLOR", domain="POINT"
            )
            for idx, (alt, slp) in enumerate(zip(data["altitudes"], data["slopes"])):
                col_attr.data[idx].color = (alt, slp, 1.0 - slp, 1.0)
    except Exception:
        pass

    if obj is None:
        obj = bpy.data.objects.new(obj_name, mesh)
        collection.objects.link(obj)
    else:
        if obj.data is not mesh:
            obj.data = mesh
        if obj.name not in collection.objects:
            try:
                collection.objects.link(obj)
            except Exception:
                pass

    if terrain_mat is not None:
        if len(obj.data.materials) == 0:
            obj.data.materials.append(terrain_mat)
        else:
            obj.data.materials[0] = terrain_mat

    mod_name = "SDS_RockScatter"
    existing_mod = obj.modifiers.get(mod_name)
    if getattr(props, "scatter_rocks", False) and getattr(props, "rock_density", 0.0) > 0.5:
        gn_group = _ensure_rock_scatter_geonodes(props, terrain_mat=terrain_mat)
        if gn_group is not None:
            if existing_mod is None:
                existing_mod = obj.modifiers.new(name=mod_name, type="NODES")
            existing_mod.node_group = gn_group
    elif existing_mod is not None:
        obj.modifiers.remove(existing_mod)

    return obj
