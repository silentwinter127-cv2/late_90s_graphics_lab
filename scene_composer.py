# SPDX-License-Identifier: GPL-3.0-or-later
"""
04 — Scene Lab & 1997 Whitted Raytracer Pipeline Engine (v2.1):
- Safe string-name datablock cleanup in `_clear_hero_objects` and `_setup_water_plane`
  (zero access to freed `StructRNA` references).
- Adds new 1997 hero compositions matching the 6 newly uploaded reference images:
  * `ISLAND_BIODOME` (Ref Image 1: Chrome geodesic dome + red obelisk spires + golden circular pad with neon-green crystal spikes)
  * `RUBY_MONOLITH_DESERT` (Ref Image 2: Translucent ruby glass monolith slab + vertical copper torus + chrome cylinder + floating eyeball orb)
  * `CYBER_GLASS_SLAB` (Ref Image 5: Refractive glass slab over electric blue cyber-grid)
"""

import math
from typing import Any, List, Tuple

try:
    import bpy
except ImportError:
    bpy = None

from . import terrain, materials, sky_atmosphere, dreamspace, dreamspace


COLLECTION_NAME = "Silicon Dreams Studio"
HERO_PREFIX = "SDS_Hero_"


def ensure_sds_collection(context: Any) -> Any:
    if bpy is None:
        return None
    col = bpy.data.collections.get(COLLECTION_NAME)
    if col is None:
        col = bpy.data.collections.new(COLLECTION_NAME)
    if col.name not in context.scene.collection.children:
        context.scene.collection.children.link(col)
    return col


def _setup_water_plane(context: Any, props: Any, collection: Any) -> Any:
    if bpy is None:
        return None
    water_name = "SDS_Water"
    water_mesh_name = "SDS_Water_Mesh"
    water_obj = bpy.data.objects.get(water_name)

    if not getattr(props, "enable_water", True):
        if water_obj is not None:
            bpy.data.objects.remove(water_obj, do_unlink=True)
            old_m = bpy.data.meshes.get(water_mesh_name)
            if old_m is not None and old_m.users == 0:
                bpy.data.meshes.remove(old_m)
        return None

    if water_obj is None:
        mesh = bpy.data.meshes.get(water_mesh_name)
        if mesh is not None and hasattr(mesh, "clear_geometry"):
            mesh.clear_geometry()
        else:
            mesh = bpy.data.meshes.new(water_mesh_name)
        s = 80.0
        verts = [(-s, -s, 0.0), (s, -s, 0.0), (s, s, 0.0), (-s, s, 0.0)]
        faces = [(0, 1, 2, 3)]
        mesh.from_pydata(verts, [], faces)
        mesh.update()
        water_obj = bpy.data.objects.new(water_name, mesh)
        collection.objects.link(water_obj)
    elif water_obj.name not in collection.objects:
        try:
            collection.objects.link(water_obj)
        except Exception:
            pass

    water_obj.location = (0.0, 0.0, float(getattr(props, "water_level", 0.0)))
    water_mat = materials.build_water_material(props)
    if water_mat is not None:
        if len(water_obj.data.materials) == 0:
            water_obj.data.materials.append(water_mat)
        else:
            water_obj.data.materials[0] = water_mat

    return water_obj


def _clear_hero_objects() -> None:
    """
    Safely removes all `SDS_Hero_*` objects and their zero-user meshes by string name lookup,
    never holding or inspecting a Python reference after `remove()` is called.
    """
    if bpy is None:
        return
    hero_obj_names = [o.name for o in bpy.data.objects if o.name.startswith(HERO_PREFIX)]
    candidate_mesh_names: List[str] = []
    for oname in hero_obj_names:
        obj = bpy.data.objects.get(oname)
        if obj is not None:
            if obj.type == "MESH" and obj.data is not None:
                candidate_mesh_names.append(obj.data.name)
            bpy.data.objects.remove(obj, do_unlink=True)

    for mname in set(candidate_mesh_names):
        m = bpy.data.meshes.get(mname)
        if m is not None and m.users == 0:
            bpy.data.meshes.remove(m)


def _create_pyramid_mesh(name: str, base_half: float = 1.6, height: float = 2.4) -> Any:
    mesh = bpy.data.meshes.new(name)
    b = base_half
    verts = [
        (-b, -b, 0.0),
        (b, -b, 0.0),
        (b, b, 0.0),
        (-b, b, 0.0),
        (0.0, 0.0, height),
    ]
    faces = [
        (0, 3, 2, 1),
        (0, 1, 4),
        (1, 2, 4),
        (2, 3, 4),
        (3, 0, 4),
    ]
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    for poly in mesh.polygons:
        poly.use_smooth = False
    return mesh


def _create_box_mesh(name: str, sx: float, sy: float, sz: float) -> Any:
    mesh = bpy.data.meshes.new(name)
    hx, hy = sx * 0.5, sy * 0.5
    verts = [
        (-hx, -hy, 0.0),
        (hx, -hy, 0.0),
        (hx, hy, 0.0),
        (-hx, hy, 0.0),
        (-hx, -hy, sz),
        (hx, -hy, sz),
        (hx, hy, sz),
        (-hx, hy, sz),
    ]
    faces = [
        (0, 3, 2, 1),
        (4, 5, 6, 7),
        (0, 1, 5, 4),
        (1, 2, 6, 5),
        (2, 3, 7, 6),
        (3, 0, 4, 7),
    ]
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    return mesh


def _create_cylinder_mesh(name: str, radius: float, height: float, segments: int = 32) -> Any:
    mesh = bpy.data.meshes.new(name)
    verts: List[Tuple[float, float, float]] = []
    faces: List[Tuple[int, ...]] = []
    for z in (0.0, height):
        for s in range(segments):
            ang = 2.0 * math.pi * (s / float(segments))
            verts.append((radius * math.cos(ang), radius * math.sin(ang), z))
    bot_center = len(verts)
    verts.append((0.0, 0.0, 0.0))
    top_center = len(verts)
    verts.append((0.0, 0.0, height))

    for s in range(segments):
        ns = (s + 1) % segments
        faces.append((s, ns, segments + ns, segments + s))
        faces.append((bot_center, ns, s))
        faces.append((top_center, segments + s, segments + ns))

    mesh.from_pydata(verts, [], faces)
    mesh.update()
    for poly in mesh.polygons:
        poly.use_smooth = True
    return mesh


def _create_csg_arch_side_wall_mesh(
    name: str, half_w: float, thickness: float, total_h: float, arch_r: float, arch_h: float, steps: int = 16
) -> Any:
    mesh = bpy.data.meshes.new(name)
    verts: List[Tuple[float, float, float]] = []
    faces: List[Tuple[int, ...]] = []

    y0 = -thickness * 0.5
    y1 = thickness * 0.5

    for sign in (-1.0, 1.0):
        x_outer = sign * half_w
        x_inner = sign * arch_r
        if sign < 0:
            x_min, x_max = x_outer, x_inner
        else:
            x_min, x_max = x_inner, x_outer
        base = len(verts)
        verts.extend(
            [
                (x_min, y0, 0.0),
                (x_max, y0, 0.0),
                (x_max, y1, 0.0),
                (x_min, y1, 0.0),
                (x_min, y0, arch_h),
                (x_max, y0, arch_h),
                (x_max, y1, arch_h),
                (x_min, y1, arch_h),
            ]
        )
        faces.extend(
            [
                (base + 0, base + 3, base + 2, base + 1),
                (base + 4, base + 5, base + 6, base + 7),
                (base + 0, base + 1, base + 5, base + 4),
                (base + 1, base + 2, base + 6, base + 5),
                (base + 2, base + 3, base + 7, base + 6),
                (base + 3, base + 0, base + 4, base + 7),
            ]
        )

    for i in range(steps):
        t0 = math.pi * (i / float(steps))
        t1 = math.pi * ((i + 1) / float(steps))
        ax0 = arch_r * math.cos(t0)
        az0 = arch_h + arch_r * math.sin(t0)
        ax1 = arch_r * math.cos(t1)
        az1 = arch_h + arch_r * math.sin(t1)

        base = len(verts)
        verts.extend(
            [
                (ax0, y0, az0),
                (ax1, y0, az1),
                (ax1, y0, total_h),
                (ax0, y0, total_h),
                (ax0, y1, az0),
                (ax1, y1, az1),
                (ax1, y1, total_h),
                (ax0, y1, total_h),
            ]
        )
        faces.extend(
            [
                (base + 0, base + 1, base + 2, base + 3),
                (base + 5, base + 4, base + 7, base + 6),
                (base + 0, base + 4, base + 5, base + 1),
                (base + 3, base + 2, base + 6, base + 7),
            ]
        )

    for sign in (-1.0, 1.0):
        x_edge = sign * half_w
        base = len(verts)
        verts.extend(
            [
                (sign * arch_r, y0, arch_h),
                (x_edge, y0, arch_h),
                (x_edge, y0, total_h),
                (sign * arch_r, y0, total_h),
                (sign * arch_r, y1, arch_h),
                (x_edge, y1, arch_h),
                (x_edge, y1, total_h),
                (sign * arch_r, y1, total_h),
            ]
        )
        faces.extend(
            [
                (base + 0, base + 1, base + 2, base + 3),
                (base + 5, base + 4, base + 7, base + 6),
                (base + 1, base + 5, base + 6, base + 2),
                (base + 3, base + 2, base + 6, base + 7),
            ]
        )

    mesh.from_pydata(verts, [], faces)
    mesh.update()
    for poly in mesh.polygons:
        poly.use_smooth = True
    return mesh


def _create_sphere_object(
    name: str,
    radius: float,
    location: Tuple[float, float, float],
    collection: Any,
    mat: Any,
    low_poly_prim: bool = False,
) -> Any:
    segs = 8 if low_poly_prim else 64
    rings = 5 if low_poly_prim else 32
    verts, faces = sky_atmosphere.create_uv_sphere_mesh_data(
        segments=segs, rings=rings, radius=radius
    )
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    for poly in mesh.polygons:
        poly.use_smooth = not low_poly_prim
    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    collection.objects.link(obj)
    if mat is not None:
        obj.data.materials.append(mat)
    return obj


def _create_torus_object(
    name: str,
    major_radius: float,
    minor_radius: float,
    location: Tuple[float, float, float],
    rotation: Tuple[float, float, float],
    collection: Any,
    mat: Any,
    low_poly_prim: bool = False,
) -> Any:
    maj_seg = 8 if low_poly_prim else 48
    min_seg = 4 if low_poly_prim else 24
    verts: List[Tuple[float, float, float]] = []
    faces: List[Tuple[int, int, int, int]] = []

    for i in range(maj_seg):
        u = 2.0 * math.pi * (i / float(maj_seg))
        cos_u = math.cos(u)
        sin_u = math.sin(u)
        for j in range(min_seg):
            v = 2.0 * math.pi * (j / float(min_seg))
            r = major_radius + minor_radius * math.cos(v)
            x = r * cos_u
            y = r * sin_u
            z = minor_radius * math.sin(v)
            verts.append((x, y, z))

    for i in range(maj_seg):
        ni = (i + 1) % maj_seg
        for j in range(min_seg):
            nj = (j + 1) % min_seg
            v0 = i * min_seg + j
            v1 = ni * min_seg + j
            v2 = ni * min_seg + nj
            v3 = i * min_seg + nj
            faces.append((v0, v1, v2, v3))

    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    for poly in mesh.polygons:
        poly.use_smooth = not low_poly_prim
    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    obj.rotation_euler = rotation
    collection.objects.link(obj)
    if mat is not None:
        obj.data.materials.append(mat)
    return obj


def _compose_hero_objects(context: Any, props: Any, collection: Any) -> None:
    if bpy is None:
        return

    _clear_hero_objects()

    comp = getattr(props, "hero_composition", "TERRAIN_ONLY")
    if comp == "TERRAIN_ONLY":
        return

    mat_style = getattr(props, "hero_material_style", "CHROME")
    scale_mult = float(getattr(props, "hero_scale", 1.15))
    count = max(1, int(getattr(props, "hero_count", 8)))
    seed = int(getattr(props, "seed", 1997))
    low_poly_prim = bool(getattr(props, "low_poly_primitives", False))

    if comp == "RAYTRACED_SHOWCASE":
        chrome_mat = materials.build_hero_material("CHROME", props, 0)
        blue_top_mat = materials.build_hero_material("COBALT_MARBLE_TOP", props, 0)

        half_w = 2.05 * scale_mult
        wall_t = 0.58 * scale_mult
        total_h = 4.65 * scale_mult
        arch_r = 1.35 * scale_mult
        arch_h = 2.55 * scale_mult

        wall_configs = [
            ((0.0, -half_w + wall_t * 0.5, 0.0), (0.0, 0.0, 0.0)),
            ((0.0, half_w - wall_t * 0.5, 0.0), (0.0, 0.0, 0.0)),
            ((-half_w + wall_t * 0.5, 0.0, 0.0), (0.0, 0.0, math.pi * 0.5)),
            ((half_w - wall_t * 0.5, 0.0, 0.0), (0.0, 0.0, math.pi * 0.5)),
        ]
        for idx, (loc, rot) in enumerate(wall_configs):
            wmesh = _create_csg_arch_side_wall_mesh(
                f"{HERO_PREFIX}CSGArchWallMesh_{idx}",
                half_w,
                wall_t,
                total_h,
                arch_r,
                arch_h,
            )
            wobj = bpy.data.objects.new(f"{HERO_PREFIX}CSGArchWall_{idx}", wmesh)
            wobj.location = loc
            wobj.rotation_euler = rot
            if chrome_mat:
                wobj.data.materials.append(chrome_mat)
            collection.objects.link(wobj)

        span = half_w * 2.02
        tmesh = _create_box_mesh(f"{HERO_PREFIX}ArchRoofMesh", span, span, 0.16 * scale_mult)
        tobj = bpy.data.objects.new(f"{HERO_PREFIX}ArchRoof", tmesh)
        tobj.location = (0.0, 0.0, total_h)
        if blue_top_mat:
            tobj.data.materials.append(blue_top_mat)
        collection.objects.link(tobj)

        num_spheres = max(4, count)
        ring_radius = 4.45 * scale_mult
        sph_radius = 1.22 * scale_mult
        for i in range(num_spheres):
            ang = (i / float(num_spheres)) * math.pi * 2.0 + 0.38
            sx = math.cos(ang) * ring_radius
            sy = math.sin(ang) * ring_radius
            _create_sphere_object(
                f"{HERO_PREFIX}ChromeOrb_{i}",
                sph_radius,
                (sx, sy, sph_radius),
                collection,
                chrome_mat,
                low_poly_prim=low_poly_prim,
            )

    elif comp == "ISLAND_BIODOME":
        # Ref Image 1 (`dT6cACN...jpg`): Chrome geodesic dome + 4 red obelisk spires + golden circular crystal pad
        chrome_mat = materials.build_hero_material("CHROME", props, 0)
        red_mat = materials.build_hero_material("PLASTIC", props, 1)
        gold_mat = materials.build_hero_material("PYRAMID_SAND", props, 0)
        green_crys_mat = materials.build_hero_material("NEON_GREEN_CRYSTAL", props, 0)

        # Chrome dome nestled in the front island cove
        _create_sphere_object(
            f"{HERO_PREFIX}BioDome",
            0.95 * scale_mult,
            (-0.8, -5.2, 0.45),
            collection,
            chrome_mat,
            low_poly_prim=low_poly_prim,
        )
        # 4 Red Obelisk Spires around the dome
        for idx, (ox, oy) in enumerate([(-1.9, -5.8), (0.3, -5.8), (-1.9, -4.4), (0.3, -4.4)]):
            smesh = _create_pyramid_mesh(f"{HERO_PREFIX}ObeliskMesh_{idx}", 0.14 * scale_mult, 1.35 * scale_mult)
            sobj = bpy.data.objects.new(f"{HERO_PREFIX}Obelisk_{idx}", smesh)
            sobj.location = (ox, oy, 0.2)
            if red_mat:
                sobj.data.materials.append(red_mat)
            collection.objects.link(sobj)

        # Golden circular platform on the right shore + glowing green crystal spikes
        cmesh = _create_cylinder_mesh(f"{HERO_PREFIX}CrystalPadMesh", 1.85 * scale_mult, 0.65 * scale_mult, 32)
        cobj = bpy.data.objects.new(f"{HERO_PREFIX}CrystalPad", cmesh)
        cobj.location = (5.2, -4.5, 0.05)
        if gold_mat:
            cobj.data.materials.append(gold_mat)
        collection.objects.link(cobj)

        for idx in range(7):
            ang = idx * 0.9
            r_off = (idx % 3) * 0.45
            kx = 5.2 + math.cos(ang) * r_off
            ky = -4.5 + math.sin(ang) * r_off
            kmesh = _create_pyramid_mesh(f"{HERO_PREFIX}CrystalSpikeMesh_{idx}", 0.16, 1.15)
            kobj = bpy.data.objects.new(f"{HERO_PREFIX}CrystalSpike_{idx}", kmesh)
            kobj.location = (kx, ky, 0.65 * scale_mult)
            if green_crys_mat:
                kobj.data.materials.append(green_crys_mat)
            collection.objects.link(kobj)

    elif comp == "RUBY_MONOLITH_DESERT":
        # Ref Image 2 (`qsvqqrL...jpg`): Translucent Ruby Monolith + Vertical Copper Torus + Chrome Cup + Eyeball Orb
        ruby_mat = materials.build_hero_material("RUBY_GLASS", props, 0)
        copper_mat = materials.build_hero_material("COPPER_METAL", props, 0)
        chrome_mat = materials.build_hero_material("CHROME", props, 0)
        eye_mat = materials.build_hero_material("EYEBALL_ORB", props, 0)

        # Central Translucent Ruby Glass Monolith Slab
        mmesh = _create_box_mesh(
            f"{HERO_PREFIX}RubyMonolithMesh", 2.8 * scale_mult, 0.45 * scale_mult, 4.6 * scale_mult
        )
        mobj = bpy.data.objects.new(f"{HERO_PREFIX}RubyMonolith", mmesh)
        mobj.location = (-0.2, -5.0, 0.0)
        mobj.rotation_euler = (0.0, 0.0, math.radians(-12.0))
        if ruby_mat:
            mobj.data.materials.append(ruby_mat)
        collection.objects.link(mobj)

        # Standing Copper Torus on the right
        _create_torus_object(
            f"{HERO_PREFIX}CopperTorus",
            1.45 * scale_mult,
            0.42 * scale_mult,
            (3.6, -6.2, 1.65 * scale_mult),
            (math.radians(82.0), 0.0, math.radians(-28.0)),
            collection,
            copper_mat,
            low_poly_prim=low_poly_prim,
        )

        # Chrome Cylinder / Mug on the left
        cup_mesh = _create_cylinder_mesh(f"{HERO_PREFIX}ChromeCupMesh", 0.72 * scale_mult, 1.45 * scale_mult, 32)
        cup_obj = bpy.data.objects.new(f"{HERO_PREFIX}ChromeCup", cup_mesh)
        cup_obj.location = (-3.6, -5.8, 0.0)
        if chrome_mat:
            cup_obj.data.materials.append(chrome_mat)
        collection.objects.link(cup_obj)

        # Floating Eyeball Orb in upper right sky
        _create_sphere_object(
            f"{HERO_PREFIX}EyeballOrb",
            0.92 * scale_mult,
            (2.8, -2.5, 5.2),
            collection,
            eye_mat,
            low_poly_prim=low_poly_prim,
        )

    elif comp == "CYBER_GLASS_SLAB":
        # Ref Image 5 (`Ob3AH_A...jpg`): Refractive Glass Box floating/resting on the foreground right over Cyber Grid
        glass_mat = materials.build_hero_material("GLASS", props, 0)
        gmesh = _create_box_mesh(
            f"{HERO_PREFIX}CyberGlassBoxMesh", 3.2 * scale_mult, 2.6 * scale_mult, 0.95 * scale_mult
        )
        gobj = bpy.data.objects.new(f"{HERO_PREFIX}CyberGlassBox", gmesh)
        gobj.location = (3.2, -8.5, 0.05)
        gobj.rotation_euler = (0.0, 0.0, math.radians(-18.0))
        if glass_mat:
            gobj.data.materials.append(glass_mat)
        collection.objects.link(gobj)

    elif comp == "SPHERES_PYRAMIDS":
        pyr_mat = materials.build_hero_material("PYRAMID_SAND", props, 0)
        pyr_specs = [
            ((-4.8, -5.5, 0.0), 1.45 * scale_mult, 2.2 * scale_mult, 0.25),
            ((-0.4, -4.8, 0.0), 2.15 * scale_mult, 3.1 * scale_mult, 0.18),
            ((4.2, -3.5, 0.0), 0.95 * scale_mult, 1.45 * scale_mult, -0.15),
        ]
        for idx, (loc, b_rad, h_val, rot_z) in enumerate(pyr_specs):
            pmesh = _create_pyramid_mesh(f"{HERO_PREFIX}PyramidMesh_{idx}", b_rad, h_val)
            pobj = bpy.data.objects.new(f"{HERO_PREFIX}Pyramid_{idx}", pmesh)
            pobj.location = loc
            pobj.rotation_euler = (0.0, 0.0, rot_z)
            if pyr_mat:
                pobj.data.materials.append(pyr_mat)
            collection.objects.link(pobj)

        sphere_specs = [
            ((0.3, -4.2, 4.4), 1.45 * scale_mult, "CHROME", 0),
            ((-5.2, -4.8, 2.8), 1.05 * scale_mult, "MARBLE_ORB", 1),
            ((4.2, -3.2, 2.7), 1.12 * scale_mult, "MARBLE_ORB", 2),
            ((-3.2, -1.5, 4.1), 0.72 * scale_mult, "MARBLE_ORB", 3),
            ((-3.4, 2.5, 6.2), 0.95 * scale_mult, "CHROME", 4),
            ((4.6, 1.8, 6.0), 1.05 * scale_mult, "MARBLE_ORB", 5),
            ((3.5, 0.8, 4.2), 0.55 * scale_mult, "MARBLE_ORB", 0),
            ((1.5, -1.2, 1.6), 0.35 * scale_mult, "PLASTIC", 1),
        ]
        for idx, (loc, rad, st, v_idx) in enumerate(sphere_specs[: max(3, count)]):
            smat = materials.build_hero_material(st, props, v_idx)
            _create_sphere_object(
                f"{HERO_PREFIX}Sphere_{idx}", rad, loc, collection, smat, low_poly_prim=low_poly_prim
            )

    elif comp == "CLASSIC_MONOLITH":
        main_mat = materials.build_hero_material(mat_style, props, 0)
        _create_sphere_object(
            f"{HERO_PREFIX}CoreSphere",
            1.55 * scale_mult,
            (0.0, -5.5, 2.3 * scale_mult),
            collection,
            main_mat,
            low_poly_prim=low_poly_prim,
        )
        if count >= 2:
            ring_mat = materials.build_hero_material("PLASTIC", props, 1)
            _create_torus_object(
                f"{HERO_PREFIX}OrbitRing",
                2.45 * scale_mult,
                0.20 * scale_mult,
                (0.0, -5.5, 2.3 * scale_mult),
                (math.radians(28.0), math.radians(-18.0), 0.0),
                collection,
                ring_mat,
                low_poly_prim=low_poly_prim,
            )
        for i in range(2, count):
            angle = (i / float(max(1, count - 2))) * math.pi * 1.4 - 0.7
            sx = math.sin(angle) * 5.2
            sy = -4.5 + math.cos(angle) * 3.0
            sz = 1.8 + (terrain._hash2d(i, seed, 55) * 2.2)
            sub_mat = materials.build_hero_material("MARBLE_ORB", props, i)
            _create_sphere_object(
                f"{HERO_PREFIX}Satellite_{i}",
                0.70 * scale_mult,
                (sx, sy, sz),
                collection,
                sub_mat,
                low_poly_prim=low_poly_prim,
            )

    elif comp == "AERO_BUBBLES":
        for i in range(count):
            t = i / float(max(1, count))
            bx = math.sin(t * math.pi * 2.0 + seed) * 5.5
            by = -5.5 + (i % 3) * 3.2
            bz = 1.4 + (i * 0.75)
            rad = (0.55 + (i % 3) * 0.45) * scale_mult
            gmat = materials.build_hero_material("GLASS", props, i)
            _create_sphere_object(
                f"{HERO_PREFIX}Bubble_{i}", rad, (bx, by, bz), collection, gmat, low_poly_prim=False
            )

    elif comp == "SURREAL_MEGASCALE":
        r_mat = materials.build_hero_material(mat_style, props, 0)
        _create_sphere_object(
            f"{HERO_PREFIX}MegaSphere",
            2.4 * scale_mult,
            (0.0, 2.0, 5.8),
            collection,
            r_mat,
            low_poly_prim=low_poly_prim,
        )
        _create_torus_object(
            f"{HERO_PREFIX}MegaHalo",
            4.2 * scale_mult,
            0.25 * scale_mult,
            (0.0, 2.0, 5.8),
            (math.radians(62.0), math.radians(-12.0), 0.0),
            collection,
            materials.build_hero_material("CHROME", props, 1),
            low_poly_prim=low_poly_prim,
        )


def setup_camera_framing(context: Any, props: Any, collection: Any) -> Any:
    if bpy is None:
        return None

    cam_name = "SDS_Camera"
    cam_data = bpy.data.cameras.get(cam_name)
    if cam_data is None:
        cam_data = bpy.data.cameras.new(cam_name)

    cam_obj = bpy.data.objects.get(cam_name)
    if cam_obj is None:
        cam_obj = bpy.data.objects.new(cam_name, cam_data)
        collection.objects.link(cam_obj)
    else:
        cam_obj.data = cam_data
        if cam_obj.name not in collection.objects:
            try:
                collection.objects.link(cam_obj)
            except Exception:
                pass

    preset = getattr(props, "camera_preset", "LAKE_REFLECTION")
    if preset == "BMC_LAWN_VIEW":
        cam_obj.location = (-6.2, -13.2, 1.75)
        cam_obj.rotation_euler = (math.radians(88.5), 0.0, math.radians(-22.0))
        cam_data.lens = 28.0
    elif preset == "KOWLOON_ALLEY_VIEW":
        cam_obj.location = (-0.3, -15.2, 1.65)
        cam_obj.rotation_euler = (math.radians(91.0), 0.0, math.radians(-4.0))
        cam_data.lens = 26.0
    elif preset == "ICO_BRIDGE_VIEW":
        # High-angle diagonal view looking across the ascending stone stairs, spiked iron railings & arched viaduct pier
        cam_obj.location = (6.8, -11.5, 6.2)
        cam_obj.rotation_euler = (math.radians(68.0), 0.0, math.radians(28.0))
        cam_data.lens = 28.0
    elif preset == "DC_STARFIGHTER_VIEW":
        # Third-person chase camera behind the banking Dreamcast starfighter facing the waterfall cliff arena & sluice towers
        cam_obj.location = (-1.6, -13.8, 3.1)
        cam_obj.rotation_euler = (math.radians(85.0), 0.0, math.radians(-5.0))
        cam_data.lens = 26.0
    elif preset == "LSD_TURTLE_VIEW":
        cam_obj.location = (0.0, -13.5, 1.65)
        cam_obj.rotation_euler = (math.radians(88.5), 0.0, 0.0)
        cam_data.lens = 26.0
    elif preset == "LSD_GRAY_MAN_VIEW":
        cam_obj.location = (0.0, -12.6, 1.55)
        cam_obj.rotation_euler = (math.radians(92.0), 0.0, 0.0)
        cam_data.lens = 25.0
    elif preset == "LSD_FLESH_TUNNEL_VIEW":
        cam_obj.location = (0.0, -12.8, 1.25)
        cam_obj.rotation_euler = (math.radians(89.5), 0.0, 0.0)
        cam_data.lens = 24.0
    elif preset == "LSD_GRAFFITI_VIEW":
        cam_obj.location = (0.35, -14.2, 1.35)
        cam_obj.rotation_euler = (math.radians(89.5), 0.0, math.radians(14.0))
        cam_data.lens = 25.0
    elif preset == "LSD_KANJI_GIANT_VIEW":
        cam_obj.location = (0.0, -13.2, 1.45)
        cam_obj.rotation_euler = (math.radians(95.5), 0.0, 0.0)
        cam_data.lens = 26.0
    elif preset == "LSD_KYOTO_NIGHT_VIEW":
        cam_obj.location = (0.0, -12.8, 1.48)
        cam_obj.rotation_euler = (math.radians(90.5), 0.0, 0.0)
        cam_data.lens = 28.0
    elif preset == "ICO_BRIDGE_VIEW":
        # High-angle diagonal view looking across the ascending stone stairs, spiked iron railings & arched viaduct pier
        cam_obj.location = (6.8, -11.5, 6.2)
        cam_obj.rotation_euler = (math.radians(68.0), 0.0, math.radians(28.0))
        cam_data.lens = 28.0
    elif preset == "DC_STARFIGHTER_VIEW":
        # Third-person chase camera behind the banking Dreamcast starfighter facing the waterfall cliff arena & sluice towers
        cam_obj.location = (-1.6, -13.8, 3.1)
        cam_obj.rotation_euler = (math.radians(85.0), 0.0, math.radians(-5.0))
        cam_data.lens = 26.0
    elif preset == "ICO_BRIDGE_VIEW":
        # High-angle diagonal view looking across the ascending stone stairs, spiked iron railings & arched viaduct pier
        cam_obj.location = (6.8, -11.5, 6.2)
        cam_obj.rotation_euler = (math.radians(68.0), 0.0, math.radians(28.0))
        cam_data.lens = 28.0
    elif preset == "DC_STARFIGHTER_VIEW":
        # Third-person chase camera behind the banking Dreamcast starfighter facing the waterfall cliff arena & sluice towers
        cam_obj.location = (-1.6, -13.8, 3.1)
        cam_obj.rotation_euler = (math.radians(85.0), 0.0, math.radians(-5.0))
        cam_data.lens = 26.0
    elif preset == "ICO_BRIDGE_VIEW":
        # High-angle diagonal view looking across the ascending stone stairs, spiked iron railings & arched viaduct pier
        cam_obj.location = (6.8, -11.5, 6.2)
        cam_obj.rotation_euler = (math.radians(68.0), 0.0, math.radians(28.0))
        cam_data.lens = 28.0
    elif preset == "DC_STARFIGHTER_VIEW":
        # Third-person chase camera behind the banking Dreamcast starfighter facing the waterfall cliff arena & sluice towers
        cam_obj.location = (-1.6, -13.8, 3.1)
        cam_obj.rotation_euler = (math.radians(85.0), 0.0, math.radians(-5.0))
        cam_data.lens = 26.0
    elif preset == "ICO_BRIDGE_VIEW":
        # High-angle diagonal view looking across the ascending stone stairs, spiked iron railings & arched viaduct pier
        cam_obj.location = (6.8, -11.5, 6.2)
        cam_obj.rotation_euler = (math.radians(68.0), 0.0, math.radians(28.0))
        cam_data.lens = 28.0
    elif preset == "DC_STARFIGHTER_VIEW":
        # Third-person chase camera behind the banking Dreamcast starfighter facing the waterfall cliff arena & sluice towers
        cam_obj.location = (-1.6, -13.8, 3.1)
        cam_obj.rotation_euler = (math.radians(85.0), 0.0, math.radians(-5.0))
        cam_data.lens = 26.0
    elif preset == "ICO_BRIDGE_VIEW":
        # High-angle diagonal view looking across the ascending stone stairs, spiked iron railings & arched viaduct pier
        cam_obj.location = (6.8, -11.5, 6.2)
        cam_obj.rotation_euler = (math.radians(68.0), 0.0, math.radians(28.0))
        cam_data.lens = 28.0
    elif preset == "DC_STARFIGHTER_VIEW":
        # Third-person chase camera behind the banking Dreamcast starfighter facing the waterfall cliff arena & sluice towers
        cam_obj.location = (-1.6, -13.8, 3.1)
        cam_obj.rotation_euler = (math.radians(85.0), 0.0, math.radians(-5.0))
        cam_data.lens = 26.0
    elif preset == "LAKE_REFLECTION":
        cam_obj.location = (0.0, -17.5, 2.25)
        cam_obj.rotation_euler = (math.radians(86.2), 0.0, 0.0)
        cam_data.lens = 28.0
    elif preset == "ARCH_OVERVIEW":
        cam_obj.location = (0.0, -9.8, 6.0)
        cam_obj.rotation_euler = (math.radians(64.0), 0.0, 0.0)
        cam_data.lens = 28.0
    elif preset == "LOW_HORIZON":
        cam_obj.location = (0.0, -14.5, 1.85)
        cam_obj.rotation_euler = (math.radians(89.5), 0.0, 0.0)
        cam_data.lens = 26.0
    elif preset == "MONUMENT_CENTER":
        cam_obj.location = (0.0, -13.5, 3.2)
        cam_obj.rotation_euler = (math.radians(82.0), 0.0, 0.0)
        cam_data.lens = 32.0
    elif preset == "ISLAND_COAST":
        cam_obj.location = (-1.2, -16.2, 3.4)
        cam_obj.rotation_euler = (math.radians(82.5), 0.0, math.radians(-4.0))
        cam_data.lens = 28.0
    elif preset == "AERIAL_OVERVIEW":
        cam_obj.location = (0.0, -21.0, 9.5)
        cam_obj.rotation_euler = (math.radians(66.0), 0.0, 0.0)
        cam_data.lens = 30.0

    cam_data.clip_start = 0.1
    cam_data.clip_end = 500.0
    context.scene.camera = cam_obj
    return cam_obj


def _configure_1997_render_engine(scene: Any, props: Any) -> None:
    mode = getattr(props, "render_engine_mode", "WHITTED_1997")
    if mode == "WHITTED_1997":
        try:
            scene.render.engine = "CYCLES"
            cyc = scene.cycles
            cyc.diffuse_bounces = 0
            cyc.glossy_bounces = 6
            cyc.transmission_bounces = 6
            cyc.volume_bounces = 0
            cyc.transparent_max_bounces = 6
            cyc.max_bounces = 6
            cyc.caustics_reflective = False
            cyc.caustics_refractive = False
            cyc.blur_glossy = 0.0
            cyc.samples = 24
            if hasattr(cyc, "preview_samples"):
                cyc.preview_samples = 12
            if hasattr(cyc, "use_denoising"):
                cyc.use_denoising = False
            if hasattr(cyc, "use_preview_denoising"):
                cyc.use_preview_denoising = False
            is_ps1_era = getattr(props, "era_pipeline", "") == "PS1_1998_LSD"
            if hasattr(cyc, "filter_width"):
                cyc.filter_width = 0.01 if is_ps1_era else 1.0
            if hasattr(scene.render, "filter_size"):
                scene.render.filter_size = 0.01 if is_ps1_era else 1.0
            if hasattr(cyc, "use_persistent_data"):
                cyc.use_persistent_data = False
            if hasattr(scene.render, "use_lock_interface"):
                scene.render.use_lock_interface = True
        except Exception:
            pass
    else:
        try:
            for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
                try:
                    scene.render.engine = eng
                    break
                except Exception:
                    continue
        except Exception:
            pass


def _get_or_create_compositor_tree(scene: Any, enable: bool) -> Any:
    if hasattr(scene, "use_nodes"):
        try:
            scene.use_nodes = enable
        except Exception:
            pass

    if not enable:
        return None

    nt = getattr(scene, "node_tree", None)
    if nt is not None:
        return nt

    if hasattr(scene, "compositing_node_group"):
        try:
            nt = getattr(scene, "compositing_node_group", None)
            if nt is None and bpy is not None:
                nt = bpy.data.node_groups.get("SDS_Retro_Compositor")
                if nt is None:
                    nt = bpy.data.node_groups.new("SDS_Retro_Compositor", "CompositorNodeTree")
                scene.compositing_node_group = nt
            return nt
        except Exception:
            return None

    return None


def apply_render_profile(context: Any, props: Any) -> None:
    if bpy is None:
        return

    scene = context.scene
    _configure_1997_render_engine(scene, props)

    profile = getattr(props, "render_profile", "RES_640")
    res_map = {
        "RES_320": (320, 240),
        "RES_640": (640, 480),
        "RES_1024": (1024, 768),
        "RES_1920": (1920, 1080),
    }
    rx, ry = res_map.get(profile, (640, 480))
    scene.render.resolution_x = rx
    scene.render.resolution_y = ry
    scene.render.resolution_percentage = 100

    try:
        is_ps1_prof = getattr(props, "era_pipeline", "") == "PS1_1998_LSD"
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"
        scene.view_settings.exposure = 0.0 if is_ps1_prof else 0.15
        scene.view_settings.gamma = 1.0
    except Exception:
        pass

    era = getattr(props, "era_pipeline", "BRYCE_1997")
    bloom_val = float(getattr(props, "ps2_bloom_intensity", 0.0))
    # For PS1 (where 15-bit color quantization is handled directly in shaders and bloom is 0),
    # disable the post-processing Compositor so multi-frame animation rendering is 100% crash-free!
    use_comp = bool(getattr(props, "enable_retro_compositor", True)) and (era != "PS1_1998_LSD" or bloom_val > 2.0)
    if not use_comp:
        try:
            if hasattr(scene.render, "use_compositing"):
                scene.render.use_compositing = False
            if hasattr(scene, "compositing_node_group"):
                scene.compositing_node_group = None
        except Exception:
            pass
    else:
        try:
            if hasattr(scene.render, "use_compositing"):
                scene.render.use_compositing = True
        except Exception:
            pass
    nt = _get_or_create_compositor_tree(scene, use_comp)
    if nt is None or not hasattr(nt, "nodes"):
        return

    try:
        nodes = nt.nodes
        links = nt.links
        nodes.clear()

        n_rl = nodes.new("CompositorNodeRLayers")
        n_rl.location = (-520, 0)

        try:
            n_comp = nodes.new("CompositorNodeComposite")
            out_socket = n_comp.inputs["Image"]
        except Exception:
            n_comp = nodes.new("NodeGroupOutput")
            if hasattr(nt, "interface") and len(nt.interface.items_tree) == 0:
                nt.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
            out_socket = n_comp.inputs[0]
        n_comp.location = (620, 0)

        sat_boost = float(getattr(props, "saturation_boost", 1.35))
        curr_out = n_rl.outputs["Image"]

        try:
            n_hsv = nodes.new("CompositorNodeHueSat")
            n_hsv.location = (-240, 0)
            materials.set_socket(n_hsv, ("Saturation",), sat_boost)
            materials.set_socket(n_hsv, ("Value",), 1.05)
            links.new(curr_out, n_hsv.inputs["Image"])
            curr_out = n_hsv.outputs["Image"]

            n_bc = nodes.new("CompositorNodeBrightContrast")
            n_bc.location = (-40, 0)
            materials.set_socket(n_bc, ("Contrast",), 16.0)
            links.new(curr_out, n_bc.inputs["Image"])
            curr_out = n_bc.outputs["Image"]

            # PS2 Graphics Synthesizer Framebuffer Bloom / Glow (`c.txt` Section 2.4)
            bloom_pct = float(getattr(props, "ps2_bloom_intensity", 0.0)) / 100.0
            if getattr(props, "era_pipeline", "BRYCE_1997") == "PS2_2000_EE" and bloom_pct < 0.05:
                bloom_pct = 0.65
            if bloom_pct > 0.02:
                try:
                    n_glare = nodes.new("CompositorNodeGlare")
                    n_glare.location = (80, 120)
                    if hasattr(n_glare, "glare_type"):
                        n_glare.glare_type = "FOG_GLOW"
                    if hasattr(n_glare, "mix"):
                        n_glare.mix = bloom_pct * 0.45
                    materials.set_socket(n_glare, ("Threshold",), max(0.35, 0.85 - bloom_pct * 0.4))
                    links.new(curr_out, n_glare.inputs["Image"])
                    curr_out = n_glare.outputs["Image"]
                except Exception:
                    pass
        except Exception:
            pass

        steps = max(8, int(getattr(props, "color_quantization_steps", 255)))
        if steps < 250:
            try:
                try:
                    n_sep = nodes.new("CompositorNodeSeparateColor")
                    n_comb = nodes.new("CompositorNodeCombineColor")
                    ch_names = ("Red", "Green", "Blue")
                    alpha_name = "Alpha"
                except Exception:
                    n_sep = nodes.new("CompositorNodeSepRGBA")
                    n_comb = nodes.new("CompositorNodeCombRGBA")
                    ch_names = ("R", "G", "B")
                    alpha_name = "A"
                n_sep.location = (160, 0)
                n_comb.location = (440, 0)

                links.new(curr_out, n_sep.inputs["Image"])
                for idx, ch in enumerate(ch_names):
                    m_mul = nodes.new("CompositorNodeMath")
                    m_mul.operation = "MULTIPLY"
                    m_mul.inputs[1].default_value = float(steps)
                    m_mul.location = (260, 140 - idx * 140)

                    m_rnd = nodes.new("CompositorNodeMath")
                    m_rnd.operation = "ROUND"
                    m_rnd.location = (320, 140 - idx * 140)

                    m_div = nodes.new("CompositorNodeMath")
                    m_div.operation = "DIVIDE"
                    m_div.inputs[1].default_value = float(steps)
                    m_div.location = (380, 140 - idx * 140)

                    links.new(n_sep.outputs[ch], m_mul.inputs[0])
                    links.new(m_mul.outputs["Value"], m_rnd.inputs[0])
                    links.new(m_rnd.outputs["Value"], m_div.inputs[0])
                    links.new(m_div.outputs["Value"], n_comb.inputs[ch])

                links.new(n_sep.outputs[alpha_name], n_comb.inputs[alpha_name])
                links.new(n_comb.outputs["Image"], out_socket)
                return
            except Exception:
                pass

        links.new(curr_out, out_socket)
    except Exception:
        pass




def setup_ps1_scene_animation(context: Any, props: Any) -> None:
    """
    Sets up a 240-frame looping animation on `SDS_Camera` (PS1 first-person breathing/walk drift)
    and `SDS_Hero_*` / `SDS_Dream_*` objects so pressing Spacebar in Blender immediately drives
    both camera/object motion and 12-FPS GTE fixed-point vertex wobble!
    """
    if bpy is None or context is None or getattr(context, "scene", None) is None:
        return
    scene = context.scene
    try:
        scene.frame_start = 1
        scene.frame_end = 240
    except Exception:
        pass

    era = getattr(props, "era_pipeline", "BRYCE_1997")
    snap_val = float(getattr(props, "ps1_vertex_snap", 0.0))
    is_ps1 = (era == "PS1_1998_LSD") or (snap_val > 0.001)

    # 1. Keyframe subtle 240-frame looping walk/sway on SDS_Camera
    cam_obj = bpy.data.objects.get("SDS_Camera")
    if cam_obj is not None:
        try:
            if getattr(cam_obj, "animation_data", None) is not None:
                cam_obj.animation_data_clear()
            if is_ps1 and hasattr(cam_obj, "keyframe_insert"):
                base_loc = tuple(float(x) for x in cam_obj.location)
                base_rot = tuple(float(x) for x in cam_obj.rotation_euler)
                sway_frames = [
                    (1,   (0.0,   0.0,  0.0),    (0.0,   0.0, 0.0)),
                    (60,  (0.012, 0.12, 0.008),  (0.001, 0.0, -0.0015)),
                    (120, (0.0,   0.24, 0.0),    (0.0,   0.0, 0.0)),
                    (180, (-0.012,0.12, 0.008),  (0.001, 0.0, 0.0015)),
                    (240, (0.0,   0.0,  0.0),    (0.0,   0.0, 0.0)),
                ]
                for f_no, d_loc, d_rot in sway_frames:
                    cam_obj.location = (
                        base_loc[0] + d_loc[0],
                        base_loc[1] + d_loc[1],
                        base_loc[2] + d_loc[2],
                    )
                    cam_obj.rotation_euler = (
                        base_rot[0] + d_rot[0],
                        base_rot[1] + d_rot[1],
                        base_rot[2] + d_rot[2],
                    )
                    cam_obj.keyframe_insert(data_path="location", frame=f_no)
                    cam_obj.keyframe_insert(data_path="rotation_euler", frame=f_no)
                cam_obj.location = base_loc
                cam_obj.rotation_euler = base_rot
        except Exception:
            pass

    # 2. Keyframe looping rotation & vertical bobbing on SDS_Hero_* objects
    obj_list = list(bpy.data.objects.values()) if isinstance(bpy.data.objects, dict) else list(bpy.data.objects)
    for idx, obj in enumerate(obj_list):
        if obj is None or getattr(obj, "type", "") != "MESH":
            continue
        oname = str(obj.name)
        if not oname.startswith(HERO_PREFIX):
            continue
        try:
            if getattr(obj, "animation_data", None) is not None:
                obj.animation_data_clear()
            if is_ps1 and hasattr(obj, "keyframe_insert"):
                b_loc = tuple(float(x) for x in obj.location)
                b_rot = tuple(float(x) for x in obj.rotation_euler)
                dir_sign = 1.0 if idx % 2 == 0 else -1.0
                for f_no, z_off, r_ang in (
                    (1,   0.0,  0.0),
                    (60,  0.28, 0.5 * math.pi * dir_sign),
                    (120, 0.0,  1.0 * math.pi * dir_sign),
                    (180, -0.28, 1.5 * math.pi * dir_sign),
                    (240, 0.0,  2.0 * math.pi * dir_sign),
                ):
                    obj.location = (b_loc[0], b_loc[1], b_loc[2] + z_off)
                    obj.rotation_euler = (b_rot[0] + 0.25 * math.sin(r_ang), b_rot[1], b_rot[2] + r_ang)
                    obj.keyframe_insert(data_path="location", frame=f_no)
                    obj.keyframe_insert(data_path="rotation_euler", frame=f_no)
                obj.location = b_loc
                obj.rotation_euler = b_rot
        except Exception:
            pass


def compose_full_scene(context: Any, props: Any) -> None:
    col = ensure_sds_collection(context)
    if col is None:
        return

    terrain_mat = materials.build_terrain_material(props)
    terrain.generate_or_update_terrain(context, props, col, terrain_mat=terrain_mat)
    _setup_water_plane(context, props, col)
    sky_atmosphere.setup_sky_and_atmosphere(context, props, col)
    _compose_hero_objects(context, props, col)
    force_flat_hero = (
        bool(getattr(props, "flat_shaded_terrain", False))
        or bool(getattr(props, "low_poly_primitives", False))
        or getattr(props, "era_pipeline", "") == "PS1_1998_LSD"
        or getattr(props, "shading_interpolation", "") == "FLAT_FACETED"
    )
    if bpy is not None:
        obj_iter = list(bpy.data.objects.values()) if isinstance(bpy.data.objects, dict) else list(bpy.data.objects)
        for h_obj in obj_iter:
            if h_obj.name.startswith(HERO_PREFIX) and h_obj.type == "MESH" and h_obj.data is not None:
                if force_flat_hero:
                    for poly in h_obj.data.polygons:
                        poly.use_smooth = False
                dreamspace.cache_base_vertices(h_obj.data)
                dreamspace.apply_era_geometry_modifiers(h_obj, props)
    dreamspace.compose_dreamspace(context, props, col)
    t_obj = bpy.data.objects.get('SDS_Terrain') if bpy else None
    dreamspace.apply_era_geometry_modifiers(t_obj, props)
    setup_camera_framing(context, props, col)
    setup_ps1_scene_animation(context, props)
    dreamspace.ensure_ps1_frame_handler_registered()
    dreamspace.ensure_ps1_gte_geonodes(props)
    apply_render_profile(context, props)
