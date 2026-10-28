# SPDX-License-Identifier: GPL-3.0-or-later
"""
02 / 03 — Sky & Atmosphere Lab (v2.1):
- Zero diffuse world light (`Light Path -> Is Diffuse Ray` outputs `0.0`).
- Safe string-name lookup when removing or updating `SDS_Celestial_Orb` so no freed
  `StructRNA` reference is ever accessed.
"""

import math
from typing import Any, List, Tuple

try:
    import bpy
except ImportError:
    bpy = None

from . import materials


def create_uv_sphere_mesh_data(
    segments: int = 48, rings: int = 24, radius: float = 1.0
) -> Tuple[List[Tuple[float, float, float]], List[Tuple[int, ...]]]:
    segs = max(8, int(segments))
    rngs = max(4, int(rings))
    verts: List[Tuple[float, float, float]] = []
    faces: List[Tuple[int, ...]] = []

    verts.append((0.0, 0.0, radius))
    for r in range(1, rngs):
        phi = math.pi * (r / float(rngs))
        sin_p = math.sin(phi)
        cos_p = math.cos(phi)
        for s in range(segs):
            theta = 2.0 * math.pi * (s / float(segs))
            x = radius * sin_p * math.cos(theta)
            y = radius * sin_p * math.sin(theta)
            z = radius * cos_p
            verts.append((x, y, z))
    bottom_idx = len(verts)
    verts.append((0.0, 0.0, -radius))

    for s in range(segs):
        next_s = (s + 1) % segs
        faces.append((0, 1 + s, 1 + next_s))

    for r in range(rngs - 2):
        row_a = 1 + r * segs
        row_b = 1 + (r + 1) * segs
        for s in range(segs):
            next_s = (s + 1) % segs
            faces.append((row_a + s, row_b + s, row_b + next_s, row_a + next_s))

    last_row = 1 + (rngs - 2) * segs
    for s in range(segs):
        next_s = (s + 1) % segs
        faces.append((last_row + s, bottom_idx, last_row + next_s))

    return verts, faces


def setup_sky_and_atmosphere(context: Any, props: Any, collection: Any) -> None:
    if bpy is None:
        return

    scene = context.scene

    world_name = "SDS_World_Sky"
    world = bpy.data.worlds.get(world_name)
    if world is None:
        world = bpy.data.worlds.new(world_name)
    scene.world = world
    world.use_nodes = True

    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()

    n_out = nodes.new("ShaderNodeOutputWorld")
    n_out.location = (940, 0)

    n_lp = nodes.new("ShaderNodeLightPath")
    n_lp.location = (420, 280)

    n_mix_shader = nodes.new("ShaderNodeMixShader")
    n_mix_shader.location = (720, 0)

    n_bg_camera = nodes.new("ShaderNodeBackground")
    n_bg_camera.location = (460, 40)
    materials.set_socket(n_bg_camera, ("Strength",), 1.05)

    n_bg_diffuse = nodes.new("ShaderNodeBackground")
    n_bg_diffuse.location = (460, -140)
    materials.set_socket(n_bg_diffuse, ("Color",), (0.0, 0.0, 0.0, 1.0))
    materials.set_socket(n_bg_diffuse, ("Strength",), 0.0)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-920, 0)

    n_sep = nodes.new("ShaderNodeSeparateXYZ")
    n_sep.location = (-680, 140)

    n_map_z = nodes.new("ShaderNodeMath")
    n_map_z.operation = "MULTIPLY_ADD"
    n_map_z.location = (-460, 140)
    n_map_z.inputs[1].default_value = 0.5
    n_map_z.inputs[2].default_value = 0.5

    n_sky_ramp = nodes.new("ShaderNodeValToRGB")
    n_sky_ramp.location = (-180, 180)
    elems = n_sky_ramp.color_ramp.elements

    gnd = getattr(props, "sky_ground_color", (0.04, 0.06, 0.22))
    hor = getattr(props, "sky_horizon_color", (0.86, 0.94, 1.00))
    zen = getattr(props, "sky_zenith_color", (0.18, 0.26, 0.78))
    cld_c = getattr(props, "cloud_color", (0.94, 0.60, 0.66))
    fog_pct = max(0.0, min(100.0, float(getattr(props, "far_fog", 28.0)))) / 100.0

    elems[0].position = 0.0
    elems[0].color = (gnd[0], gnd[1], gnd[2], 1.0)
    elems[1].position = 0.75
    elems[1].color = (zen[0], zen[1], zen[2], 1.0)

    hor_low = elems.new(max(0.42, 0.49 - fog_pct * 0.06))
    hor_low.color = (hor[0], hor[1], hor[2], 1.0)
    hor_high = elems.new(min(0.60, 0.51 + fog_pct * 0.08))
    hor_high.color = (hor[0], hor[1], hor[2], 1.0)

    n_cld_map = nodes.new("ShaderNodeMapping")
    n_cld_map.location = (-680, -180)
    materials.set_socket(n_cld_map, ("Scale",), (1.0, 1.0, 5.5))

    n_cloud_noise = nodes.new("ShaderNodeTexNoise")
    n_cloud_noise.location = (-440, -180)
    materials.set_socket(n_cloud_noise, ("Scale",), float(getattr(props, "cloud_scale", 3.5)))
    materials.set_socket(n_cloud_noise, ("Detail",), 3.5)
    materials.set_socket(n_cloud_noise, ("Distortion",), 0.9)

    cloud_cov = max(0.0, min(100.0, float(getattr(props, "cloud_coverage", 58.0)))) / 100.0
    n_cloud_ramp = nodes.new("ShaderNodeValToRGB")
    n_cloud_ramp.location = (-180, -180)
    c_elems = n_cloud_ramp.color_ramp.elements
    c_elems[0].position = max(0.05, 0.68 - cloud_cov * 0.52)
    c_elems[0].color = (0.0, 0.0, 0.0, 1.0)
    c_elems[1].position = min(0.95, c_elems[0].position + 0.18)
    c_elems[1].color = (1.0, 1.0, 1.0, 1.0)

    _, mix_fac, mix_c1, mix_c2, mix_out = materials._new_mix_color(nodes, links, location=(200, 40))
    mix_c2.default_value = (cld_c[0], cld_c[1], cld_c[2], 1.0)

    n_upper_sky = nodes.new("ShaderNodeValToRGB")
    n_upper_sky.location = (-180, -380)
    u_el = n_upper_sky.color_ramp.elements
    u_el[0].position = 0.49
    u_el[0].color = (0.0, 0.0, 0.0, 1.0)
    u_el[1].position = 0.55
    u_el[1].color = (1.0, 1.0, 1.0, 1.0)

    n_cloud_mask = nodes.new("ShaderNodeMath")
    n_cloud_mask.operation = "MULTIPLY"
    n_cloud_mask.location = (40, -140)

    links.new(n_coord.outputs["Generated"], n_sep.inputs["Vector"])
    is_ps1_sky = getattr(props, "era_pipeline", "BRYCE_1997") == "PS1_1998_LSD"
    if is_ps1_sky:
        n_sky_snap = nodes.new("ShaderNodeVectorMath")
        n_sky_snap.operation = "SNAP"
        n_sky_snap.location = (-560, -180)
        for inp in list(n_sky_snap.inputs)[1:]:
            if getattr(inp, "type", "") == "VECTOR":
                try:
                    inp.default_value = (0.012, 0.012, 0.012)
                except Exception:
                    pass
        links.new(n_coord.outputs["Generated"], n_cld_map.inputs["Vector"])
        links.new(n_cld_map.outputs["Vector"], n_sky_snap.inputs[0])
        links.new(n_sky_snap.outputs[0], n_cloud_noise.inputs["Vector"])
        n_cloud_ramp.color_ramp.interpolation = "CONSTANT"
        materials.set_socket(n_bg_camera, ("Strength",), 1.0)
    else:
        links.new(n_coord.outputs["Generated"], n_cld_map.inputs["Vector"])
        links.new(n_cld_map.outputs["Vector"], n_cloud_noise.inputs["Vector"])
    links.new(n_sep.outputs["Z"], n_map_z.inputs[0])
    links.new(n_map_z.outputs["Value"], n_sky_ramp.inputs["Fac"])
    links.new(n_map_z.outputs["Value"], n_upper_sky.inputs["Fac"])
    links.new(n_cloud_noise.outputs["Fac"], n_cloud_ramp.inputs["Fac"])
    links.new(n_cloud_ramp.outputs["Color"], n_cloud_mask.inputs[0])
    links.new(n_upper_sky.outputs["Color"], n_cloud_mask.inputs[1])
    links.new(n_cloud_mask.outputs["Value"], mix_fac)
    links.new(n_sky_ramp.outputs["Color"], mix_c1)
    links.new(mix_out, n_bg_camera.inputs["Color"])

    links.new(n_lp.outputs["Is Diffuse Ray"], n_mix_shader.inputs["Fac"])
    links.new(n_bg_camera.outputs["Background"], n_mix_shader.inputs[1])
    links.new(n_bg_diffuse.outputs["Background"], n_mix_shader.inputs[2])
    links.new(n_mix_shader.outputs["Shader"], n_out.inputs["Surface"])

    # Sun Light (`SDS_Sun`)
    sun_col = getattr(props, "sun_color", (1.0, 0.96, 0.82))
    sun_name = "SDS_Sun"
    sun_data = bpy.data.lights.get(sun_name)
    if sun_data is None:
        sun_data = bpy.data.lights.new(name=sun_name, type="SUN")
    sun_data.color = sun_col
    sun_data.energy = float(getattr(props, "sun_intensity", 4.2))
    hard_shadows = bool(getattr(props, "hard_shadows", True))
    sun_data.angle = math.radians(0.05 if hard_shadows else 3.0)
    is_ps1_sun = getattr(props, "era_pipeline", "BRYCE_1997") == "PS1_1998_LSD"
    try:
        sun_data.use_shadow = not is_ps1_sun
        if hasattr(sun_data, "cycles") and hasattr(sun_data.cycles, "cast_shadow"):
            sun_data.cycles.cast_shadow = not is_ps1_sun
    except Exception:
        pass

    sun_obj = bpy.data.objects.get(sun_name)
    if sun_obj is None:
        sun_obj = bpy.data.objects.new(sun_name, sun_data)
        collection.objects.link(sun_obj)
    else:
        sun_obj.data = sun_data
        if sun_obj.name not in collection.objects:
            try:
                collection.objects.link(sun_obj)
            except Exception:
                pass

    elev = math.radians(float(getattr(props, "sun_elevation", 28.0)))
    azim = math.radians(float(getattr(props, "sun_azimuth", 132.0)))
    sun_obj.location = (0.0, 0.0, 20.0)
    sun_obj.rotation_euler = (math.pi * 0.5 - elev, 0.0, azim)

    # Pure-Python Celestial Planet/Moon (`SDS_Celestial_Orb`)
    orb_name = "SDS_Celestial_Orb"
    orb_mesh_name = "SDS_Celestial_Orb_Mesh"
    orb_obj = bpy.data.objects.get(orb_name)
    if getattr(props, "enable_celestial_orb", False):
        if orb_obj is None:
            verts, faces = create_uv_sphere_mesh_data(segments=48, rings=24, radius=1.0)
            orb_mesh = bpy.data.meshes.get(orb_mesh_name)
            if orb_mesh is not None and hasattr(orb_mesh, "clear_geometry"):
                orb_mesh.clear_geometry()
            else:
                orb_mesh = bpy.data.meshes.new(orb_mesh_name)
            orb_mesh.from_pydata(verts, [], faces)
            orb_mesh.update()
            for poly in orb_mesh.polygons:
                poly.use_smooth = True
            orb_obj = bpy.data.objects.new(orb_name, orb_mesh)
            collection.objects.link(orb_obj)
        elif orb_obj.name not in collection.objects:
            try:
                collection.objects.link(orb_obj)
            except Exception:
                pass

        scale_val = float(getattr(props, "celestial_orb_scale", 20.0)) * 0.42
        orb_obj.scale = (scale_val, scale_val, scale_val)
        orb_obj.location = (5.5, 24.0, scale_val * 0.65)
        lava_mat = materials.build_hero_material("PLANET_LAVA", props, 0)
        if lava_mat:
            if len(orb_obj.data.materials) == 0:
                orb_obj.data.materials.append(lava_mat)
            else:
                orb_obj.data.materials[0] = lava_mat
    elif orb_obj is not None:
        bpy.data.objects.remove(orb_obj, do_unlink=True)
        old_m = bpy.data.meshes.get(orb_mesh_name)
        if old_m is not None and old_m.users == 0:
            bpy.data.meshes.remove(old_m)
