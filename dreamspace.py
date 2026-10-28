# SPDX-License-Identifier: GPL-3.0-or-later
"""
04 — Dreamspace Generator & PS1/PS2 Hardware Geometry Simulators (`b.txt` & `c.txt`):
1. Spatial Graph & Modular Architectural Stitching (`compose_dreamspace`):
   - `CORRIDOR_TO_HILLS`: Enclosed tiled/concrete hallway leading abruptly onto open terrain
   - `WALLED_COMPOUND`: Surreal walled courtyard with hollow window-pierced apartment blocks & torii gate
   - `IMPOSSIBLE_STAIRS_TOWERS`: Disconnected Brutalist stairways ending in mid-air + repeating facade towers
   - `MIXED_DREAM_GRAPH`: Seeded multi-node spatial graph combining corridors, plazas, stairs & monoliths
2. Scale & Proportion Anomalies (`dream_scale_anomaly`, `dream_tilt_anomaly`):
   - Non-physical scale jumps, stretched door/window proportions, and local ground/gravity tilt
3. Heterogeneous Texture Assignment (`texture_mismatch_mode`):
   - `SEMANTIC`: Concrete/brick/window-grid facades on buildings
   - `WEAK_RANDOM`: Shuffled palettes across repeated building modules ("似曾相识但略有不同")
   - `CROSS_MISMATCH`: Swaps textures across categories (buildings get grass/sky/water; terrain gets building facades)
   - `LOCAL_MUTATION`: Injects sudden Voronoi cell patches of mismatched textures
4. PS1 GTE Vertex Quantization (`ensure_ps1_gte_modifier`):
   - Triangulates meshes and snaps 3D vertex positions to a discrete fixed-point grid (`Snap`).
"""

import math
from typing import Any, List, Tuple

try:
    import bpy
except ImportError:
    bpy = None

from . import terrain, materials


DREAM_PREFIX = "SDS_Dream_"


def clear_dreamspace_objects() -> None:
    """Safely removes all `SDS_Dream_*` objects and their zero-user meshes by string name lookup."""
    if bpy is None:
        return
    dream_names = [o.name for o in bpy.data.objects if o.name.startswith(DREAM_PREFIX)]
    mesh_names: List[str] = []
    for oname in dream_names:
        obj = bpy.data.objects.get(oname)
        if obj is not None:
            if obj.type == "MESH" and obj.data is not None:
                mesh_names.append(obj.data.name)
            bpy.data.objects.remove(obj, do_unlink=True)
    for mname in set(mesh_names):
        m = bpy.data.meshes.get(mname)
        if m is not None and m.users == 0:
            bpy.data.meshes.remove(m)


def _out_sock(node: Any, preferred_names: Tuple[str, ...], fallback_idx: int = 0) -> Any:
    if node is None or not hasattr(node, "outputs"):
        return None
    for name in preferred_names:
        if name in node.outputs:
            return node.outputs[name]
    if len(node.outputs) > fallback_idx:
        return node.outputs[fallback_idx]
    return None


def _in_sock(node: Any, preferred_names: Tuple[str, ...], fallback_idx: int = 0) -> Any:
    if node is None or not hasattr(node, "inputs"):
        return None
    for name in preferred_names:
        if name in node.inputs:
            return node.inputs[name]
    if len(node.inputs) > fallback_idx:
        return node.inputs[fallback_idx]
    return None


def cache_base_vertices(mesh: Any) -> None:
    """No-op kept for API compatibility; v3.5 evaluates GTE wobble 100% in C++ Geometry Nodes."""
    return


def ensure_ps1_gte_geonodes(props: Any) -> Any:
    """
    Creates or updates `SDS_PS1_GTE_Quantize_GN` (v3.6 Early Hardware Precision Edition):
    1. Stores the undeformed vertex position `Position` into Named Attribute `"sds_rest_pos"`
       (`GeometryNodeStoreNamedAttribute`) BEFORE `GeometryNodeSetPosition` so all procedural
       textures stay 100% locked/glued to the mesh faces and NEVER change or flip during animation!
    2. Removes artificial sine-wave shaking completely. Instead, simulates true 16-bit Fixed-Point
       Camera-Space Coordinate Truncation (`P_out = SNAP(P - CamLoc_rel, lsb) + CamLoc_rel`) with
       a fine hardware LSB (`0.004m - 0.012m`, default `0.006m` = 6mm, ~0.5-1 screen pixel at 320x240).
       As the camera glides forward, polygon edges exhibit authentic 1-pixel fixed-point precision
       stepping without any violent mesh deformation!
    """
    if bpy is None:
        return None

    snap_val = float(getattr(props, "ps1_vertex_snap", 0.0))
    if getattr(props, "era_pipeline", "BRYCE_1997") == "PS1_1998_LSD" and snap_val < 0.001:
        snap_val = 0.006

    if snap_val <= 0.0005:
        return None

    # Strictly clamp fixed-point LSB to 2mm - 12mm (0.002m - 0.012m) so even legacy .blend files
    # that had 0.24 saved in sds_props never deform geometry!
    if snap_val > 0.025:
        lsb = 0.006
    else:
        lsb = max(0.002, min(0.012, snap_val))

    group_name = "SDS_PS1_GTE_Quantize_GN"
    ng = bpy.data.node_groups.get(group_name)
    if ng is None:
        ng = bpy.data.node_groups.new(group_name, "GeometryNodeTree")

    nodes = ng.nodes
    links = ng.links
    nodes.clear()

    if hasattr(ng, "interface"):
        for item in list(ng.interface.items_tree):
            ng.interface.remove(item)
        ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    else:
        ng.inputs.clear()
        ng.outputs.clear()
        ng.inputs.new("NodeSocketGeometry", "Geometry")
        ng.outputs.new("NodeSocketGeometry", "Geometry")

    n_in = nodes.new("NodeGroupInput")
    n_in.location = (-820, 120)
    n_out = nodes.new("NodeGroupOutput")
    n_out.location = (620, 120)

    try:
        n_pos = nodes.new("GeometryNodeInputPosition")
        n_pos.location = (-820, -100)
        pos_out = _out_sock(n_pos, ("Position", "Vector"), 0)

        # Step 1: Store undeformed rest position into "sds_rest_pos" so textures never swim or flip!
        geom_curr = n_in.outputs[0]
        try:
            n_store = nodes.new("GeometryNodeStoreNamedAttribute")
            n_store.location = (-560, 120)
            if hasattr(n_store, "data_type"):
                n_store.data_type = "FLOAT_VECTOR"
            if hasattr(n_store, "domain"):
                n_store.domain = "POINT"
            name_in = _in_sock(n_store, ("Name",), 2)
            if name_in is not None:
                name_in.default_value = "sds_rest_pos"
            val_in = _in_sock(n_store, ("Value",), 3)
            if val_in is not None:
                links.new(pos_out, val_in)
            links.new(geom_curr, _in_sock(n_store, ("Geometry",), 0))
            geom_curr = _out_sock(n_store, ("Geometry",), 0)
        except Exception:
            pass

        # Step 2: Camera-Relative Fixed-Point Coordinate Truncation
        # P_out = SNAP(P - CamLoc_rel, lsb) + CamLoc_rel
        cam_obj = bpy.data.objects.get("SDS_Camera")
        cam_loc_out = None
        if cam_obj is not None:
            try:
                n_cam = nodes.new("GeometryNodeObjectInfo")
                n_cam.location = (-820, -280)
                if hasattr(n_cam, "transform_space"):
                    n_cam.transform_space = "RELATIVE"
                obj_in = _in_sock(n_cam, ("Object",), 0)
                if obj_in is not None:
                    obj_in.default_value = cam_obj
                cam_loc_out = _out_sock(n_cam, ("Location",), 1)
            except Exception:
                cam_loc_out = None

        n_inc = nodes.new("ShaderNodeCombineXYZ")
        n_inc.location = (-320, -340)
        n_inc.inputs[0].default_value = lsb
        n_inc.inputs[1].default_value = lsb
        n_inc.inputs[2].default_value = lsb

        if cam_loc_out is not None:
            n_sub_cam = nodes.new("ShaderNodeVectorMath")
            n_sub_cam.operation = "SUBTRACT"
            n_sub_cam.location = (-320, -100)
            links.new(pos_out, n_sub_cam.inputs[0])
            links.new(cam_loc_out, n_sub_cam.inputs[1])

            n_snap = nodes.new("ShaderNodeVectorMath")
            n_snap.operation = "SNAP"
            n_snap.location = (-80, -100)
            for inp in list(n_snap.inputs)[1:]:
                if getattr(inp, "type", "") == "VECTOR":
                    try:
                        inp.default_value = (lsb, lsb, lsb)
                    except Exception:
                        pass
            links.new(_out_sock(n_sub_cam, ("Vector",), 0), n_snap.inputs[0])
            inc_sock = _in_sock(n_snap, ("Increment", "Vector_001"), 1)
            if inc_sock is not None:
                links.new(_out_sock(n_inc, ("Vector",), 0), inc_sock)

            n_add_cam = nodes.new("ShaderNodeVectorMath")
            n_add_cam.operation = "ADD"
            n_add_cam.location = (160, -100)
            links.new(_out_sock(n_snap, ("Vector",), 0), n_add_cam.inputs[0])
            links.new(cam_loc_out, n_add_cam.inputs[1])
            final_pos_out = _out_sock(n_add_cam, ("Vector",), 0)
        else:
            n_snap = nodes.new("ShaderNodeVectorMath")
            n_snap.operation = "SNAP"
            n_snap.location = (-80, -100)
            for inp in list(n_snap.inputs)[1:]:
                if getattr(inp, "type", "") == "VECTOR":
                    try:
                        inp.default_value = (lsb, lsb, lsb)
                    except Exception:
                        pass
            links.new(pos_out, n_snap.inputs[0])
            inc_sock = _in_sock(n_snap, ("Increment", "Vector_001"), 1)
            if inc_sock is not None:
                links.new(_out_sock(n_inc, ("Vector",), 0), inc_sock)
            final_pos_out = _out_sock(n_snap, ("Vector",), 0)

        n_set = nodes.new("GeometryNodeSetPosition")
        n_set.location = (400, 120)
        links.new(geom_curr, _in_sock(n_set, ("Geometry",), 0))
        pos_in = _in_sock(n_set, ("Position",), 2)
        if pos_in is not None:
            links.new(final_pos_out, pos_in)
        links.new(_out_sock(n_set, ("Geometry",), 0), n_out.inputs[0])
    except Exception:
        links.new(n_in.outputs[0], n_out.inputs[0])

    return ng


def ensure_ps1_frame_handler_registered() -> None:
    """Removes any legacy Python frame_change_pre handler so Render Animation is 100% thread-safe."""
    unregister_ps1_frame_handler()


def unregister_ps1_frame_handler() -> None:
    if bpy is None or not hasattr(bpy, "app") or not hasattr(bpy.app, "handlers"):
        return
    for list_name in (
        "frame_change_pre",
        "frame_change_post",
        "render_pre",
        "render_post",
        "render_init",
        "depsgraph_update_pre",
        "depsgraph_update_post",
    ):
        h_list = getattr(bpy.app.handlers, list_name, None)
        if h_list is None:
            continue
        for h in list(h_list):
            h_name = getattr(h, "__name__", "")
            h_mod = getattr(h, "__module__", "")
            if h_name.startswith("sds_") or "late_90s_graphics_lab" in h_mod or "silicon_dreams" in h_mod:
                try:
                    h_list.remove(h)
                except Exception:
                    pass


def ensure_ps2_vpu_geonodes(props: Any) -> Any:
    """
    Creates or updates `SDS_PS2_VPU_Wave_GN` (`c.txt` Section 1.1 - 1.2):
    - Simulates the PlayStation 2 Emotion Engine VU1 Vector Co-Processor executing real-time
      32-bit floating-point sinusoidal vertex wind/atmospheric wave micro-deformation (`ps2_vpu_wave`).
    """
    if bpy is None:
        return None

    wave_pct = float(getattr(props, "ps2_vpu_wave", 0.0))
    era = getattr(props, "era_pipeline", "BRYCE_1997")
    if era != "PS2_2000_EE" or wave_pct <= 0.5:
        return None

    amp = (wave_pct / 100.0) * 0.065
    group_name = "SDS_PS2_VPU_Wave_GN"
    ng = bpy.data.node_groups.get(group_name)
    if ng is None:
        ng = bpy.data.node_groups.new(group_name, "GeometryNodeTree")

    nodes = ng.nodes
    links = ng.links
    nodes.clear()

    if hasattr(ng, "interface"):
        for item in list(ng.interface.items_tree):
            ng.interface.remove(item)
        ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    else:
        ng.inputs.clear()
        ng.outputs.clear()
        ng.inputs.new("NodeSocketGeometry", "Geometry")
        ng.outputs.new("NodeSocketGeometry", "Geometry")

    n_in = nodes.new("NodeGroupInput")
    n_in.location = (-720, 120)
    n_out = nodes.new("NodeGroupOutput")
    n_out.location = (520, 120)

    try:
        n_pos = nodes.new("GeometryNodeInputPosition")
        n_pos.location = (-720, -80)
        pos_out = _out_sock(n_pos, ("Position", "Vector"), 0)

        n_stime = nodes.new("GeometryNodeInputSceneTime")
        n_stime.location = (-720, -260)
        sec_out = _out_sock(n_stime, ("Seconds", "Frame"), 0)

        n_mul_t = nodes.new("ShaderNodeMath")
        n_mul_t.operation = "MULTIPLY"
        n_mul_t.location = (-520, -260)
        if len(n_mul_t.inputs) > 1:
            n_mul_t.inputs[1].default_value = 2.2
        links.new(sec_out, n_mul_t.inputs[0])

        n_comb_t = nodes.new("ShaderNodeCombineXYZ")
        n_comb_t.location = (-340, -260)
        links.new(_out_sock(n_mul_t, ("Value",), 0), n_comb_t.inputs[0])
        links.new(_out_sock(n_mul_t, ("Value",), 0), n_comb_t.inputs[1])

        n_add = nodes.new("ShaderNodeVectorMath")
        n_add.operation = "ADD"
        n_add.location = (-160, -100)
        links.new(pos_out, n_add.inputs[0])
        links.new(_out_sock(n_comb_t, ("Vector",), 0), n_add.inputs[1])

        n_sin = nodes.new("ShaderNodeVectorMath")
        n_sin.operation = "SINE"
        n_sin.location = (20, -100)
        links.new(_out_sock(n_add, ("Vector",), 0), n_sin.inputs[0])

        n_scale = nodes.new("ShaderNodeCombineXYZ")
        n_scale.location = (20, -280)
        n_scale.inputs[0].default_value = amp
        n_scale.inputs[1].default_value = amp * 0.75
        n_scale.inputs[2].default_value = amp * 0.25

        n_off = nodes.new("ShaderNodeVectorMath")
        n_off.operation = "MULTIPLY"
        n_off.location = (180, -100)
        links.new(_out_sock(n_sin, ("Vector",), 0), n_off.inputs[0])
        links.new(_out_sock(n_scale, ("Vector",), 0), n_off.inputs[1])

        n_set = nodes.new("GeometryNodeSetPosition")
        n_set.location = (360, 120)
        links.new(n_in.outputs[0], _in_sock(n_set, ("Geometry",), 0))
        off_in = _in_sock(n_set, ("Offset",), 3)
        if off_in is not None:
            links.new(_out_sock(n_off, ("Vector",), 0), off_in)
        links.new(_out_sock(n_set, ("Geometry",), 0), n_out.inputs[0])
    except Exception:
        links.new(n_in.outputs[0], n_out.inputs[0])

    return ng


def apply_era_geometry_modifiers(obj: Any, props: Any) -> None:
    """
    Attaches or removes era-specific hardware geometry modifiers on a mesh object:
    - Category II (`PS1_1998_LSD`): `SDS_PS1_GTE` (16-bit Fixed-Point Coordinate Truncation + Rest Position Lock)
    - Category IV (`PS2_2000_EE`):  `SDS_PS2_VPU` (Emotion Engine VU1 Vector Vertex Wind Deformation)
    """
    if bpy is None or obj is None or obj.type != "MESH":
        return

    era = getattr(props, "era_pipeline", "BRYCE_1997")

    # 1. PS1 GTE Modifier
    ps1_mod_name = "SDS_PS1_GTE"
    existing_ps1 = obj.modifiers.get(ps1_mod_name)
    gn_ps1 = ensure_ps1_gte_geonodes(props) if (era == "PS1_1998_LSD" or float(getattr(props, "ps1_vertex_snap", 0.0)) > 0.0005) else None
    if gn_ps1 is not None and era == "PS1_1998_LSD":
        if existing_ps1 is None:
            existing_ps1 = obj.modifiers.new(name=ps1_mod_name, type="NODES")
        existing_ps1.node_group = gn_ps1
    elif existing_ps1 is not None:
        obj.modifiers.remove(existing_ps1)

    # 2. PS2 VU1 Vector Co-Processor Modifier
    ps2_mod_name = "SDS_PS2_VPU"
    existing_ps2 = obj.modifiers.get(ps2_mod_name)
    gn_ps2 = ensure_ps2_vpu_geonodes(props) if era == "PS2_2000_EE" else None
    if gn_ps2 is not None and era == "PS2_2000_EE":
        if existing_ps2 is None:
            existing_ps2 = obj.modifiers.new(name=ps2_mod_name, type="NODES")
        existing_ps2.node_group = gn_ps2
    elif existing_ps2 is not None:
        obj.modifiers.remove(existing_ps2)


def _create_hollow_corridor_mesh(name: str, width: float, length: float, height: float, wall_t: float = 0.25) -> Any:
    """Creates a modular LSD-style corridor tunnel with side doorway cutouts and ceiling beams."""
    mesh = bpy.data.meshes.new(name)
    verts: List[Tuple[float, float, float]] = []
    faces: List[Tuple[int, int, int, int]] = []

    hw = width * 0.5
    hl = length * 0.5

    def _add_box(x0, x1, y0, y1, z0, z1):
        b = len(verts)
        verts.extend(
            [
                (x0, y0, z0),
                (x1, y0, z0),
                (x1, y1, z0),
                (x0, y1, z0),
                (x0, y0, z1),
                (x1, y0, z1),
                (x1, y1, z1),
                (x0, y1, z1),
            ]
        )
        faces.extend(
            [
                (b + 0, b + 3, b + 2, b + 1),
                (b + 4, b + 5, b + 6, b + 7),
                (b + 0, b + 1, b + 5, b + 4),
                (b + 1, b + 2, b + 6, b + 5),
                (b + 2, b + 3, b + 7, b + 6),
                (b + 3, b + 0, b + 4, b + 7),
            ]
        )

    # Floor slab
    _add_box(-hw, hw, -hl, hl, 0.0, wall_t)
    # Left & Right walls (with an open gap in the middle for a surreal side doorway)
    seg_l = length * 0.38
    for sign in (-1.0, 1.0):
        wx0 = sign * hw - (wall_t if sign > 0 else 0.0)
        wx1 = wx0 + wall_t
        _add_box(wx0, wx1, -hl, -hl + seg_l, wall_t, height)
        _add_box(wx0, wx1, hl - seg_l, hl, wall_t, height)
        # Door lintel above the side opening
        _add_box(wx0, wx1, -hl + seg_l, hl - seg_l, height * 0.72, height)

    # Overhead ceiling beams (open sky slots between beams for dramatic shadow stripes)
    num_beams = 5
    for i in range(num_beams):
        by = -hl + (i / float(num_beams - 1)) * (length - wall_t * 2.0)
        _add_box(-hw, hw, by, by + wall_t * 1.8, height, height + wall_t * 1.4)

    mesh.from_pydata(verts, [], faces)
    mesh.update()
    return mesh


def _create_staircase_mesh(name: str, width: float, step_count: int, step_run: float, step_rise: float) -> Any:
    """Creates a Brutalist / LSD staircase that climbs into thin air."""
    mesh = bpy.data.meshes.new(name)
    verts: List[Tuple[float, float, float]] = []
    faces: List[Tuple[int, int, int, int]] = []
    hw = width * 0.5

    for i in range(max(2, step_count)):
        y0 = i * step_run
        y1 = (i + 1) * step_run
        z0 = i * step_rise * 0.35
        z1 = (i + 1) * step_rise
        b = len(verts)
        verts.extend(
            [
                (-hw, y0, z0),
                (hw, y0, z0),
                (hw, y1, z0),
                (-hw, y1, z0),
                (-hw, y0, z1),
                (hw, y0, z1),
                (hw, y1, z1),
                (-hw, y1, z1),
            ]
        )
        faces.extend(
            [
                (b + 0, b + 3, b + 2, b + 1),
                (b + 4, b + 5, b + 6, b + 7),
                (b + 0, b + 1, b + 5, b + 4),
                (b + 1, b + 2, b + 6, b + 5),
                (b + 2, b + 3, b + 7, b + 6),
                (b + 3, b + 0, b + 4, b + 7),
            ]
        )

    mesh.from_pydata(verts, [], faces)
    mesh.update()
    return mesh


def _create_hollow_building_mesh(name: str, sx: float, sy: float, sz: float, wall_t: float = 0.25) -> Any:
    """
    Creates an LSD-style hollow architectural block with an oversized/anomalous doorway
    and window cutouts ("有门窗但没有明显功能的建筑" — b.txt Section 3.5).
    """
    mesh = bpy.data.meshes.new(name)
    verts: List[Tuple[float, float, float]] = []
    faces: List[Tuple[int, int, int, int]] = []
    hx, hy = sx * 0.5, sy * 0.5

    def _add_box(x0, x1, y0, y1, z0, z1):
        b = len(verts)
        verts.extend(
            [
                (x0, y0, z0),
                (x1, y0, z0),
                (x1, y1, z0),
                (x0, y1, z0),
                (x0, y0, z1),
                (x1, y0, z1),
                (x1, y1, z1),
                (x0, y1, z1),
            ]
        )
        faces.extend(
            [
                (b + 0, b + 3, b + 2, b + 1),
                (b + 4, b + 5, b + 6, b + 7),
                (b + 0, b + 1, b + 5, b + 4),
                (b + 1, b + 2, b + 6, b + 5),
                (b + 2, b + 3, b + 7, b + 6),
                (b + 3, b + 0, b + 4, b + 7),
            ]
        )

    # Back wall, left wall, right wall, roof slab
    _add_box(-hx, hx, hy - wall_t, hy, 0.0, sz)
    _add_box(-hx, -hx + wall_t, -hy, hy - wall_t, 0.0, sz)
    _add_box(hx - wall_t, hx, -hy, hy - wall_t, 0.0, sz)
    _add_box(-hx, hx, -hy, hy, sz, sz + wall_t)

    # Front wall with off-center anomalous doorway
    door_w = sx * 0.28
    _add_box(-hx, -door_w * 0.5, -hy, -hy + wall_t, 0.0, sz)
    _add_box(door_w * 0.5, hx, -hy, -hy + wall_t, 0.0, sz)
    _add_box(-door_w * 0.5, door_w * 0.5, -hy, -hy + wall_t, sz * 0.62, sz)

    mesh.from_pydata(verts, [], faces)
    mesh.update()
    return mesh




def _create_lowpoly_tree_mesh(name: str) -> Any:
    """
    Constructs the exact 6-sided flat-shaded brown trunk & 3 angular V-branches tree
    from《LSD: Dream Emulator》Bright Moon Cottage (P5 & P6)!
    """
    mesh = bpy.data.meshes.new(name)
    verts: List[Tuple[float, float, float]] = []
    faces: List[Tuple[int, ...]] = []

    # 6-sided tapered trunk from Z=0..2.2
    for z, r in ((0.0, 0.26), (2.1, 0.16)):
        for i in range(6):
            ang = 2.0 * math.pi * (i / 6.0)
            verts.append((r * math.cos(ang), r * math.sin(ang), z))
    for i in range(6):
        ni = (i + 1) % 6
        faces.append((i, ni, 6 + ni, 6 + i))

    # 3 sharp angular branches shooting up from Z=2.0 to Z=3.8
    branch_tips = [(-1.6, -0.8, 3.8), (1.4, -0.6, 3.6), (0.2, 1.5, 3.9)]
    for bx, by, bz in branch_tips:
        b = len(verts)
        verts.extend(
            [
                (-0.12, -0.12, 2.0),
                (0.12, -0.12, 2.0),
                (0.0, 0.14, 2.0),
                (bx - 0.05, by - 0.05, bz),
                (bx + 0.05, by - 0.05, bz),
                (bx, by + 0.06, bz),
            ]
        )
        faces.extend(
            [
                (b + 0, b + 1, b + 4, b + 3),
                (b + 1, b + 2, b + 5, b + 4),
                (b + 2, b + 0, b + 3, b + 5),
            ]
        )

    mesh.from_pydata(verts, [], faces)
    mesh.update()
    for poly in mesh.polygons:
        poly.use_smooth = False
    return mesh


def _create_lowpoly_hydrant_mesh(name: str) -> Any:
    """
    Constructs the low-poly 8-sided Hong Kong red fire hydrant in the left foreground of
    《九龙风水传 Kowloon's Gate》(P2)!
    """
    mesh = bpy.data.meshes.new(name)
    verts: List[Tuple[float, float, float]] = []
    faces: List[Tuple[int, ...]] = []

    rings = [(0.0, 0.42), (0.25, 0.36), (1.15, 0.34), (1.45, 0.38), (1.72, 0.22), (1.85, 0.05)]
    segs = 8
    for z, r in rings:
        for s in range(segs):
            ang = 2.0 * math.pi * (s / float(segs))
            verts.append((r * math.cos(ang), r * math.sin(ang), z))

    for r_idx in range(len(rings) - 1):
        r0 = r_idx * segs
        r1 = (r_idx + 1) * segs
        for s in range(segs):
            ns = (s + 1) % segs
            faces.append((r0 + s, r0 + ns, r1 + ns, r1 + s))

    mesh.from_pydata(verts, [], faces)
    mesh.update()
    for poly in mesh.polygons:
        poly.use_smooth = False
    return mesh


def _build_bright_moon_cottage_scene(props: Any, collection: Any) -> List[Any]:
    """
    Reconstructs the《LSD: Dream Emulator》Bright Moon Cottage (明月庄) scene from P3, P4, P5, P6:
    - Concrete perimeter walls around the flat neon-green lawn
    - 4-story speckled concrete Bright Moon Cottage building with 3x4 purple-blue windows & awning
    - Open 1st-floor bar interior (checkerboard floor, yellow shoji walls with mahogany wainscoting,
      dark ceiling grid, L-shaped mahogany bar counter, bottle shelves & frosted glass divider)
    - 2nd-floor yellow tatami pillar corridor with pixelated wood floor & stairs
    - Low-poly 6-sided angular tree with flat leaf planes on the foreground lawn.
    """
    objs: List[Any] = []
    ext_mat = materials.build_ps1_bmc_exterior_material(props)
    win_mat = materials.build_ps1_bmc_window_material(props)
    shoji_mat = materials.build_ps1_bmc_shoji_wall_material(props)
    chk_mat = materials.build_ps1_bmc_checker_floor_material(props)
    wood_mat = materials.build_ps1_bmc_wood_floor_material(props)
    wall_mat = materials.build_dream_wall_material(props, 0)
    dark_wood_mat = materials.build_hero_material("PLASTIC", props, 1)
    bottle_mat = materials.build_ps1_kg_signboard_material(props, 0)

    def _spawn_box(name_suffix: str, sx: float, sy: float, sz: float, loc: Tuple[float, float, float], mat: Any, rot=(0.0, 0.0, 0.0)):
        mesh = bpy.data.meshes.new(f"{DREAM_PREFIX}{name_suffix}_Mesh")
        hx, hy = sx * 0.5, sy * 0.5
        verts = [
            (-hx, -hy, 0.0), (hx, -hy, 0.0), (hx, hy, 0.0), (-hx, hy, 0.0),
            (-hx, -hy, sz), (hx, -hy, sz), (hx, hy, sz), (-hx, hy, sz),
        ]
        faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        mesh.from_pydata(verts, [], faces)
        mesh.update()
        for p in mesh.polygons:
            p.use_smooth = False
        o = bpy.data.objects.new(f"{DREAM_PREFIX}{name_suffix}", mesh)
        o.location = loc
        o.rotation_euler = rot
        if mat:
            o.data.materials.append(mat)
        collection.objects.link(o)
        objs.append(o)
        return o

    # 1. Grey Concrete Perimeter Courtyard Walls (P3, P5, P6)
    _spawn_box("BMC_Wall_Back", 36.0, 0.5, 2.2, (0.0, 14.0, 0.0), wall_mat)
    _spawn_box("BMC_Wall_Left", 0.5, 34.0, 2.2, (-16.0, -2.0, 0.0), wall_mat)
    _spawn_box("BMC_Wall_Right", 0.5, 34.0, 2.2, (16.0, -2.0, 0.0), wall_mat)

    # 2. Main 4-Story Bright Moon Cottage Building Upper Mass (`Z = 3.0..12.0m`, P3 & P6)
    _spawn_box("BMC_UpperBlock", 11.0, 7.5, 9.0, (-1.5, 1.5, 3.0), ext_mat)
    # Right solid wing extending down to ground (`Z = 0.0..12.0m`, P6)
    _spawn_box("BMC_RightWing", 5.2, 7.5, 12.0, (5.5, 1.5, 0.0), ext_mat)

    # 3x4 Grid of Inset Purple-Blue Windows on front facade (`Y = -2.28`, P3 & P6)
    for row in range(3):
        wz = 4.2 + row * 2.5
        for col_i in range(4):
            wx = -5.4 + col_i * 2.4
            _spawn_box(f"BMC_Win_{row}_{col_i}", 1.55, 0.12, 1.45, (wx, -2.26, wz), win_mat)

    # Slanted Corrugated Awning over 1st-floor bar entrance (`P3 & P6`)
    _spawn_box("BMC_Awning", 10.6, 2.2, 0.16, (-1.5, -3.1, 2.85), wall_mat, rot=(math.radians(14.0), 0.0, 0.0))

    # 3. Open 1st-Floor Bar Interior (`P3 & P5 — BMC_normal_bar_1.webp`)
    _spawn_box("BMC_BarFloor", 10.8, 7.4, 0.06, (-1.5, 1.5, 0.01), chk_mat)
    _spawn_box("BMC_BarCeiling", 10.8, 7.4, 0.15, (-1.5, 1.5, 2.85), ext_mat)
    _spawn_box("BMC_BarBackWall", 10.8, 0.25, 2.85, (-1.5, 5.1, 0.0), shoji_mat)
    _spawn_box("BMC_BarLeftWall", 0.25, 7.4, 2.85, (-6.8, 1.5, 0.0), shoji_mat)
    _spawn_box("BMC_BarRightPillar", 0.65, 0.65, 2.85, (3.2, -2.0, 0.0), ext_mat)

    # Mahogany L-Shaped Bar Counter & Bottle Shelf (`P3 & P5`)
    _spawn_box("BMC_BarCounter_Front", 4.6, 0.75, 1.05, (0.2, 1.2, 0.0), dark_wood_mat)
    _spawn_box("BMC_BarCounter_Side", 0.75, 2.6, 1.05, (-1.8, 2.5, 0.0), dark_wood_mat)
    _spawn_box("BMC_BottleRack", 3.6, 0.35, 1.45, (0.4, 4.75, 1.15), bottle_mat)

    # 4. 2nd-Floor Tatami Pillar Corridor (`P4 — BMC_normal_second_floor.webp`)
    _spawn_box("BMC_HallFloor", 3.6, 11.0, 0.08, (-8.8, 1.5, 0.02), wood_mat)
    for idx in range(5):
        py = -2.5 + idx * 2.2
        _spawn_box(f"BMC_TatamiPillar_{idx}", 0.85, 0.85, 2.85, (-7.2, py, 0.0), shoji_mat)

    # 5. Low-Poly 6-Sided Angular Brown Tree on the Front Green Lawn (`P5 & P6`)
    tmesh = _create_lowpoly_tree_mesh(f"{DREAM_PREFIX}BMC_TreeMesh")
    tobj = bpy.data.objects.new(f"{DREAM_PREFIX}BMC_LowPolyTree", tmesh)
    tobj.location = (-4.5, -7.8, 0.0)
    if dark_wood_mat:
        tobj.data.materials.append(dark_wood_mat)
    collection.objects.link(tobj)
    objs.append(tobj)

    # Flat angular pixel-leaf canopy planes on the tree branches
    leaf_mat = materials.build_ps1_bmc_grass_material(props)
    for idx, (lx, ly, lz, rz) in enumerate([
        (-5.6, -8.2, 3.6, 0.4),
        (-3.4, -8.0, 3.5, -0.5),
        (-4.4, -6.6, 3.8, 0.1),
    ]):
        _spawn_box(f"BMC_TreeLeaf_{idx}", 2.1, 1.4, 0.08, (lx, ly, lz), leaf_mat, rot=(0.25, -0.2, rz))

    return objs


def _build_kowloons_gate_alley_scene(props: Any, collection: Any) -> List[Any]:
    """
    Reconstructs the atmospheric, claustrophobic PS1《九龙风水传 Kowloon's Gate》Hong Kong Walled City
    Alleyway faithfully matching P1 (`c8ee9253.webp`) & P2 (`0f3a1156.webp`):
    - Dark damp asphalt/stone alley paving with raised drainage curb
    - Left corrugated iron rolling shutter wall with red stenciled calligraphy & upper balcony
    - Right ceramic mosaic tile pillars (fine 10cm x 10cm dirty pale greenish-grey tiles with grout)
    - Dark timber market stall counter with weathered crimson vinyl skirt apron
    - Left foreground chunky 8-sided cast-iron red fire hydrant with chipped metal edges & green band
    - Illuminated Hong Kong neon lightboxes (`擺設金鋪` / `冷飲熱品`)
    - Atmospheric Local Point Lights: Warm hanging street lantern (58W) & cool fluorescent tube (42W)!
    """
    objs: List[Any] = []
    shutter_mat = materials.build_ps1_kg_shutter_material(props)
    pillar_tile_mat = materials.build_ps1_kg_tile_pillar_material(props)
    ground_mat = materials.build_ps1_kg_alley_ground_material(props)
    stall_mat = materials.build_ps1_kg_market_stall_material(props)
    hydrant_mat = materials.build_ps1_kg_hydrant_material(props)
    sign_mat_0 = materials.build_ps1_kg_signboard_material(props, 0)
    sign_mat_1 = materials.build_ps1_kg_signboard_material(props, 1)

    def _spawn_box(name_suffix: str, sx: float, sy: float, sz: float, loc: Tuple[float, float, float], mat: Any, rot=(0.0, 0.0, 0.0)) -> Any:
        m = _create_hollow_building_mesh(f"{DREAM_PREFIX}{name_suffix}_M", sx, sy, sz)
        o = bpy.data.objects.new(f"{DREAM_PREFIX}{name_suffix}", m)
        o.location = loc
        o.rotation_euler = rot
        if mat:
            o.data.materials.append(mat)
        collection.objects.link(o)
        objs.append(o)
        return o

    # 1. Dark Damp Alley Ground & Drainage Curb (P1 & P2 floor)
    _spawn_box("KG_AlleyPaving", 8.5, 24.0, 0.25, (0.2, -6.0, -0.12), ground_mat)
    _spawn_box("KG_DrainCurb_L", 0.38, 24.0, 0.28, (-1.35, -6.0, 0.0), ground_mat)
    for idx in range(6):
        _spawn_box(f"KG_AlleyStep_{idx}", 2.4, 1.4, 0.12, (0.35, -12.5 + idx * 2.2, 0.01), ground_mat)

    # 2. Left Shophouse Wall with Realistic Weathered Corrugated Shutter & Upper Balcony (P1 & P2)
    _spawn_box("KG_LeftShutterWall", 0.45, 18.0, 3.4, (-2.85, -6.0, 0.0), shutter_mat)
    _spawn_box("KG_LeftUpperBalcony", 1.25, 18.0, 3.6, (-2.45, -6.0, 3.4), pillar_tile_mat)

    # 3. Right Shophouse: Ceramic Mosaic Tile Pillars, Market Stall Counter & Slanted Tin Awning (P1 & P2)
    _spawn_box("KG_RightBackWall", 0.45, 18.0, 6.8, (3.25, -6.0, 0.0), shutter_mat)
    for idx in range(4):
        cy = -12.5 + idx * 3.8
        _spawn_box(f"KG_TilePillar_{idx}", 0.68, 0.68, 4.2, (1.95, cy, 0.0), pillar_tile_mat)

    # Dark Timber Market Stall Counter with Weathered Crimson Vinyl Apron on the right (P1)
    _spawn_box("KG_MarketStallCounter", 1.15, 6.5, 0.95, (1.65, -9.5, 0.0), stall_mat)

    # Overhanging Slanted Weathered Tin Awning (P2)
    _spawn_box("KG_TinAwning", 2.6, 9.5, 0.10, (-1.6, -7.5, 3.1), shutter_mat, rot=(0.0, math.radians(16.0), 0.0))

    # 4. Back T-Junction Cross-Alley Wall
    _spawn_box("KG_BackAlleyWall", 8.5, 0.55, 6.8, (0.0, 2.5, 0.0), pillar_tile_mat)

    # 5. Overhead Low-Poly Angular Pipes, Air Ducts & Ceiling Enclosure (P1)
    _spawn_box("KG_AlleyCeiling", 8.5, 24.0, 0.35, (0.0, -6.0, 6.2), pillar_tile_mat)
    _spawn_box("KG_OverheadDuct_0", 0.52, 16.0, 0.52, (-0.6, -6.0, 4.8), shutter_mat)
    _spawn_box("KG_OverheadDuct_1", 0.38, 16.0, 0.38, (-1.35, -6.0, 5.1), shutter_mat)

    # 6. Illuminated Hong Kong Signboards (`冷飲熱品` / `擺設金鋪` — P1 & P2)
    _spawn_box("KG_Sign_GoldShop", 0.18, 3.2, 0.85, (-2.45, -9.8, 2.85), sign_mat_0)
    _spawn_box("KG_Sign_ColdDrinks", 0.18, 2.8, 0.92, (1.65, -8.5, 2.75), sign_mat_1)
    _spawn_box("KG_Sign_DeepAlley", 1.45, 0.18, 0.65, (-0.65, -4.8, 2.45), sign_mat_1)

    # 7. Low-Poly 8-Sided Cast-Iron Red Fire Hydrant in Left Foreground (P2 `0f3a1156.webp`!)
    hmesh = _create_lowpoly_hydrant_mesh(f"{DREAM_PREFIX}KG_HydrantMesh")
    hobj = bpy.data.objects.new(f"{DREAM_PREFIX}KG_FireHydrant", hmesh)
    hobj.location = (-1.85, -11.8, 0.0)
    if hydrant_mat:
        hobj.data.materials.append(hydrant_mat)
    collection.objects.link(hobj)
    objs.append(hobj)

    # 8. Atmospheric Local Point Lights (Warm Street Lantern & Cool Fluorescent Lightbox)
    def _add_local_lamp(name: str, loc: Tuple[float, float, float], color: Tuple[float, float, float], energy: float):
        l_name = f"{DREAM_PREFIX}{name}"
        l_data = bpy.data.lights.get(l_name)
        if l_data is None:
            l_data = bpy.data.lights.new(name=l_name, type="POINT")
        l_data.color = color
        l_data.energy = energy
        if hasattr(l_data, "shadow_soft_size"):
            l_data.shadow_soft_size = 0.25
        l_obj = bpy.data.objects.get(l_name)
        if l_obj is None:
            l_obj = bpy.data.objects.new(l_name, l_data)
            collection.objects.link(l_obj)
        else:
            l_obj.data = l_data
            if l_obj.name not in collection.objects:
                try:
                    collection.objects.link(l_obj)
                except Exception:
                    pass
        l_obj.location = loc
        objs.append(l_obj)

    # Warm street lantern pool illuminating the market counter, fire hydrant and ground (P1 & P2!)
    _add_local_lamp("KG_Lantern_Warm", (0.35, -9.2, 2.45), (1.0, 0.72, 0.45), 58.0)
    # Cool fluorescent tube under the overhanging awning illuminating the shutter and signboard
    _add_local_lamp("KG_Fluorescent_Cool", (-1.45, -10.8, 2.85), (0.78, 0.92, 1.0), 42.0)
    # Distant warm alley lantern creating background depth
    _add_local_lamp("KG_Lantern_Deep", (-0.35, -3.5, 2.65), (1.0, 0.65, 0.35), 32.0)

    for obj in objs:
        if getattr(obj, "type", "") == "MESH" and obj.data is not None:
            for poly in obj.data.polygons:
                poly.use_smooth = False
    return objs


def _build_bright_moon_cottage_scene(props: Any, collection: Any) -> List[Any]:
    """
    Reconstructs the《LSD: Dream Emulator》Bright Moon Cottage (明月庄) scene from P3, P4, P5, P6:
    - Concrete perimeter walls around the flat neon-green lawn
    - 4-story speckled concrete Bright Moon Cottage building with 3x4 purple-blue windows & awning
    - Open 1st-floor bar interior (checkerboard floor, yellow shoji walls with mahogany wainscoting,
      dark ceiling grid, L-shaped mahogany bar counter, bottle shelves & frosted glass divider)
    - 2nd-floor yellow tatami pillar corridor with pixelated wood floor & stairs
    - Low-poly 6-sided angular tree with flat leaf planes on the foreground lawn.
    """
    objs: List[Any] = []
    ext_mat = materials.build_ps1_bmc_exterior_material(props)
    win_mat = materials.build_ps1_bmc_window_material(props)
    shoji_mat = materials.build_ps1_bmc_shoji_wall_material(props)
    chk_mat = materials.build_ps1_bmc_checker_floor_material(props)
    wood_mat = materials.build_ps1_bmc_wood_floor_material(props)
    wall_mat = materials.build_dream_wall_material(props, 0)
    dark_wood_mat = materials.build_hero_material("PLASTIC", props, 1)
    bottle_mat = materials.build_ps1_kg_signboard_material(props, 0)

    def _spawn_box(name_suffix: str, sx: float, sy: float, sz: float, loc: Tuple[float, float, float], mat: Any, rot=(0.0, 0.0, 0.0)):
        mesh = bpy.data.meshes.new(f"{DREAM_PREFIX}{name_suffix}_Mesh")
        hx, hy = sx * 0.5, sy * 0.5
        verts = [
            (-hx, -hy, 0.0), (hx, -hy, 0.0), (hx, hy, 0.0), (-hx, hy, 0.0),
            (-hx, -hy, sz), (hx, -hy, sz), (hx, hy, sz), (-hx, hy, sz),
        ]
        faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        mesh.from_pydata(verts, [], faces)
        mesh.update()
        for p in mesh.polygons:
            p.use_smooth = False
        o = bpy.data.objects.new(f"{DREAM_PREFIX}{name_suffix}", mesh)
        o.location = loc
        o.rotation_euler = rot
        if mat:
            o.data.materials.append(mat)
        collection.objects.link(o)
        objs.append(o)
        return o

    # 1. Grey Concrete Perimeter Courtyard Walls (P3, P5, P6)
    _spawn_box("BMC_Wall_Back", 36.0, 0.5, 2.2, (0.0, 14.0, 0.0), wall_mat)
    _spawn_box("BMC_Wall_Left", 0.5, 34.0, 2.2, (-16.0, -2.0, 0.0), wall_mat)
    _spawn_box("BMC_Wall_Right", 0.5, 34.0, 2.2, (16.0, -2.0, 0.0), wall_mat)

    # 2. Main 4-Story Bright Moon Cottage Building Upper Mass (`Z = 3.0..12.0m`, P3 & P6)
    _spawn_box("BMC_UpperBlock", 11.0, 7.5, 9.0, (-1.5, 1.5, 3.0), ext_mat)
    # Right solid wing extending down to ground (`Z = 0.0..12.0m`, P6)
    _spawn_box("BMC_RightWing", 5.2, 7.5, 12.0, (5.5, 1.5, 0.0), ext_mat)

    # 3x4 Grid of Inset Purple-Blue Windows on front facade (`Y = -2.28`, P3 & P6)
    for row in range(3):
        wz = 4.2 + row * 2.5
        for col_i in range(4):
            wx = -5.4 + col_i * 2.4
            _spawn_box(f"BMC_Win_{row}_{col_i}", 1.55, 0.12, 1.45, (wx, -2.26, wz), win_mat)

    # Slanted Corrugated Awning over 1st-floor bar entrance (`P3 & P6`)
    _spawn_box("BMC_Awning", 10.6, 2.2, 0.16, (-1.5, -3.1, 2.85), wall_mat, rot=(math.radians(14.0), 0.0, 0.0))

    # 3. Open 1st-Floor Bar Interior (`P3 & P5 — BMC_normal_bar_1.webp`)
    _spawn_box("BMC_BarFloor", 10.8, 7.4, 0.06, (-1.5, 1.5, 0.01), chk_mat)
    _spawn_box("BMC_BarCeiling", 10.8, 7.4, 0.15, (-1.5, 1.5, 2.85), ext_mat)
    _spawn_box("BMC_BarBackWall", 10.8, 0.25, 2.85, (-1.5, 5.1, 0.0), shoji_mat)
    _spawn_box("BMC_BarLeftWall", 0.25, 7.4, 2.85, (-6.8, 1.5, 0.0), shoji_mat)
    _spawn_box("BMC_BarRightPillar", 0.65, 0.65, 2.85, (3.2, -2.0, 0.0), ext_mat)

    # Mahogany L-Shaped Bar Counter & Bottle Shelf (`P3 & P5`)
    _spawn_box("BMC_BarCounter_Front", 4.6, 0.75, 1.05, (0.2, 1.2, 0.0), dark_wood_mat)
    _spawn_box("BMC_BarCounter_Side", 0.75, 2.6, 1.05, (-1.8, 2.5, 0.0), dark_wood_mat)
    _spawn_box("BMC_BottleRack", 3.6, 0.35, 1.45, (0.4, 4.75, 1.15), bottle_mat)

    # 4. 2nd-Floor Tatami Pillar Corridor (`P4 — BMC_normal_second_floor.webp`)
    _spawn_box("BMC_HallFloor", 3.6, 11.0, 0.08, (-8.8, 1.5, 0.02), wood_mat)
    for idx in range(5):
        py = -2.5 + idx * 2.2
        _spawn_box(f"BMC_TatamiPillar_{idx}", 0.85, 0.85, 2.85, (-7.2, py, 0.0), shoji_mat)

    # 5. Low-Poly 6-Sided Angular Brown Tree on the Front Green Lawn (`P5 & P6`)
    tmesh = _create_lowpoly_tree_mesh(f"{DREAM_PREFIX}BMC_TreeMesh")
    tobj = bpy.data.objects.new(f"{DREAM_PREFIX}BMC_LowPolyTree", tmesh)
    tobj.location = (-4.5, -7.8, 0.0)
    if dark_wood_mat:
        tobj.data.materials.append(dark_wood_mat)
    collection.objects.link(tobj)
    objs.append(tobj)

    # Flat angular pixel-leaf canopy planes on the tree branches
    leaf_mat = materials.build_ps1_bmc_grass_material(props)
    for idx, (lx, ly, lz, rz) in enumerate([
        (-5.6, -8.2, 3.6, 0.4),
        (-3.4, -8.0, 3.5, -0.5),
        (-4.4, -6.6, 3.8, 0.1),
    ]):
        _spawn_box(f"BMC_TreeLeaf_{idx}", 2.1, 1.4, 0.08, (lx, ly, lz), leaf_mat, rot=(0.25, -0.2, rz))

    return objs


def _select_dream_material(props: Any, role: str, index: int) -> Any:
    """
    Implements the Heterogeneous Texture Assignment System (`b.txt` Section 3.3):
    - `SEMANTIC`: Architectural roles get concrete/facade/plaster; natural gets grass/water
    - `WEAK_RANDOM`: Cycles across architectural variants with shifted palettes
    - `CROSS_MISMATCH`: Swaps categories (buildings get grass/sky/water; corridors get clouds)
    - `LOCAL_MUTATION`: Assigns mutated Voronoi cell facade/checker textures
    """
    mismatch = getattr(props, "texture_mismatch_mode", "SEMANTIC")
    seed = int(getattr(props, "seed", 1998))

    if mismatch == "SEMANTIC":
        if role == "TOWER":
            return materials.build_dream_facade_material(props, index % 3)
        if role == "CORRIDOR":
            return materials.build_dream_wall_material(props, 0)
        return materials.build_dream_wall_material(props, (index + 1) % 3)

    if mismatch == "WEAK_RANDOM":
        pick = (index + seed) % 4
        if pick in (0, 1):
            return materials.build_dream_facade_material(props, index % 5)
        return materials.build_dream_wall_material(props, index % 5)

    if mismatch == "CROSS_MISMATCH":
        # Cross-category mismatch: buildings get terrain/water/checker/sky textures!
        pick = (index + seed) % 4
        if pick == 0:
            return materials.build_water_material(props)
        if pick == 1:
            return materials.build_checker_material(props)
        if pick == 2:
            return materials.build_hero_material("RAINBOW", props, index)
        return materials.build_dream_facade_material(props, index + 2)

    # LOCAL_MUTATION
    return materials.build_dream_mutated_material(props, index)




def _create_csg_arch_pier_wall_mesh(name: str, width: float, thickness: float, height: float) -> Any:
    """Creates a stone viaduct wall with a semicircular arch opening at the bottom."""
    segs = 10
    rx = width * 0.36
    rz = height * 0.52
    hx = width * 0.5
    hy = thickness * 0.5

    verts: List[Tuple[float, float, float]] = []
    faces: List[Tuple[int, int, int, int]] = []

    for side_y in (-hy, hy):
        for i in range(segs + 1):
            theta = math.pi * (1.0 - i / float(segs))
            ax = rx * math.cos(theta)
            az = rz * math.sin(theta)
            verts.append((ax, side_y, az))
        for i in range(segs + 1):
            t = i / float(segs)
            if t <= 0.2:
                ox, oz = -hx, (t / 0.2) * height
            elif t <= 0.8:
                ox, oz = -hx + ((t - 0.2) / 0.6) * (2.0 * hx), height
            else:
                ox, oz = hx, (1.0 - (t - 0.8) / 0.2) * height
            verts.append((ox, side_y, oz))

    n_ring = segs + 1
    front_arch = 0
    front_outer = n_ring
    back_arch = 2 * n_ring
    back_outer = 3 * n_ring

    for i in range(segs):
        faces.append((front_arch + i, front_arch + i + 1, front_outer + i + 1, front_outer + i))
        faces.append((back_outer + i, back_outer + i + 1, back_arch + i + 1, back_arch + i))
        faces.append((front_arch + i + 1, front_arch + i, back_arch + i, back_arch + i + 1))
        faces.append((front_outer + i, front_outer + i + 1, back_outer + i + 1, back_outer + i))

    faces.append((front_outer + 0, back_outer + 0, back_arch + 0, front_arch + 0))
    faces.append((front_arch + segs, back_arch + segs, back_outer + segs, front_outer + segs))

    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    return mesh


def _build_ico_castle_bridge_scene(props: Any, collection: Any) -> List[Any]:
    """
    Faithfully reconstructs the PS2 *ICO* (2001) Castle Viaduct, Jutting Cliff Ledge,
    Ascending Stone Staircase, Stepped Parapets & Spiked Iron Fence Railings (`sJugHxmS...jpg`).
    """
    objs: List[Any] = []
    stone_light = materials.build_ps2_ico_stone_material(props, variant=0)
    stone_dark = materials.build_ps2_ico_stone_material(props, variant=1)
    iron_mat = materials.build_ps2_ico_iron_railing_material(props)

    def _add_box(name: str, sx: float, sy: float, sz: float, loc: Tuple[float, float, float], mat: Any, rot_z: float = 0.0) -> Any:
        m = _create_hollow_building_mesh(f"{DREAM_PREFIX}{name}_M", sx, sy, sz)
        o = bpy.data.objects.new(f"{DREAM_PREFIX}{name}", m)
        o.location = loc
        o.rotation_euler = (0.0, 0.0, rot_z)
        if mat:
            o.data.materials.append(mat)
        collection.objects.link(o)
        objs.append(o)
        return o

    # 1. Central Massive Stone Viaduct Pier descending into the misty abyss
    _add_box("ICO_CentralPier", 3.4, 3.8, 14.0, (0.0, 2.6, -11.8), stone_dark)
    _add_box("ICO_PierCap", 3.8, 4.2, 0.65, (0.0, 2.6, 2.15), stone_light)

    # 2. Elevated Arched Viaduct Spans (Left and Right of Central Pier)
    for side_idx, sx_pos in enumerate((-4.6, 4.6)):
        arch_m = _create_csg_arch_pier_wall_mesh(f"{DREAM_PREFIX}ICO_ArchSpan_{side_idx}_M", 5.8, 2.6, 4.2)
        arch_o = bpy.data.objects.new(f"{DREAM_PREFIX}ICO_ArchSpan_{side_idx}", arch_m)
        arch_o.location = (sx_pos, 2.6, -1.6)
        if stone_light:
            arch_o.data.materials.append(stone_light)
        collection.objects.link(arch_o)
        objs.append(arch_o)

    # Upper Viaduct Walkway Deck & Stone Parapet Curbs
    _add_box("ICO_ViaductDeck", 16.5, 3.0, 0.55, (0.0, 2.6, 2.45), stone_light)
    _add_box("ICO_ViaductBackParapet", 16.5, 0.42, 0.85, (0.0, 3.9, 2.95), stone_light)

    # 3. Jutting Weathered Left Cliffside Stone Bastion / Ledge (Left Midground in Ref Image 2)
    _add_box("ICO_LeftCliffBastion", 4.6, 4.8, 9.5, (-4.4, -2.6, -7.8), stone_dark)
    _add_box("ICO_LeftCliffLedgeTop", 4.8, 5.0, 0.55, (-4.4, -2.6, 1.65), stone_light)
    _add_box("ICO_LeftCliffParapet_W", 0.45, 4.8, 0.75, (-6.55, -2.6, 2.15), stone_light)
    _add_box("ICO_LeftCliffParapet_S", 4.8, 0.45, 0.75, (-4.4, -4.85, 2.15), stone_light)

    # 4. Ascending Stone Staircase & Stepped Parapet Walls (Foreground Right to Center Landing)
    st_mesh = _create_staircase_mesh(f"{DREAM_PREFIX}ICO_Stairs_M", 2.6, 14, 0.44, 0.25)
    st_obj = bpy.data.objects.new(f"{DREAM_PREFIX}ICO_Stairs", st_mesh)
    st_obj.location = (1.2, -5.2, -1.05)
    if stone_light:
        st_obj.data.materials.append(stone_light)
    collection.objects.link(st_obj)
    objs.append(st_obj)

    # Staircase solid under-ramp support pier
    _add_box("ICO_StairSupportPier", 2.8, 6.4, 9.0, (1.2, -2.0, -7.6), stone_dark)

    # Stepped Stone Parapet Walls flanking the staircase + Square Stone Bollards
    for step_i in range(5):
        py = -4.8 + step_i * 1.35
        pz = -0.8 + step_i * 0.68
        _add_box(f"ICO_StepWall_L_{step_i}", 0.38, 1.45, 1.25, (-0.25, py, pz), stone_light)
        _add_box(f"ICO_StepWall_R_{step_i}", 0.38, 1.45, 1.25, (2.65, py, pz), stone_light)

    # Square Stone Bollards at the base & top of the stairs
    for b_idx, (bx, by, bz) in enumerate([(-0.25, -5.4, -0.9), (2.65, -5.4, -0.9), (-0.25, 1.2, 2.45), (2.65, 1.2, 2.45)]):
        _add_box(f"ICO_StoneBollard_{b_idx}", 0.62, 0.62, 1.45, (bx, by, bz), stone_light)

    # 5. Spiked Wrought-Iron Fence Railings along the Viaduct & Ledge (`sJugHxmS...jpg`)
    for r_idx in range(18):
        rx = -6.2 + r_idx * 0.72
        _add_box(f"ICO_IronSpike_{r_idx}", 0.06, 0.06, 1.15, (rx, 1.25, 2.85), iron_mat)
    _add_box("ICO_IronTopRail", 12.8, 0.08, 0.07, (-0.1, 1.25, 3.82), iron_mat)
    _add_box("ICO_IronMidRail", 12.8, 0.08, 0.07, (-0.1, 1.25, 3.12), iron_mat)

    # 6. PS2 Graphics Synthesizer (GS) Multi-Layer Alpha-Blended Sun-Shaft / God-Ray Planes (`c.txt` Section 2)
    shaft_mat = materials.build_ps2_gs_sunshaft_material(props)
    for s_idx, (sx, sy, sz) in enumerate([(-2.2, 0.5, 4.8), (1.4, -1.2, 4.2), (4.2, 1.5, 5.2)]):
        sm = _create_hollow_building_mesh(f"{DREAM_PREFIX}ICO_SunShaft_{s_idx}_M", 2.4, 0.06, 9.5)
        so = bpy.data.objects.new(f"{DREAM_PREFIX}ICO_SunShaft_{s_idx}", sm)
        so.location = (sx, sy, sz - 2.5)
        so.rotation_euler = (math.radians(28.0), math.radians(-18.0), math.radians(22.0))
        if shaft_mat:
            so.data.materials.append(shaft_mat)
        collection.objects.link(so)
        objs.append(so)

    for obj in objs:
        if obj.type == "MESH" and obj.data is not None:
            # PS2 uses Gouraud smooth shading on curved arch vaults while keeping flat masonry courses crisp
            is_curved_arch = "ArchSpan" in obj.name or "SunShaft" in obj.name
            for poly in obj.data.polygons:
                poly.use_smooth = is_curved_arch
    return objs


def _create_starfighter_mesh(name: str) -> Any:
    """
    Creates the sleek angular Sega Dreamcast starfighter mesh (`-UPttAsJ...jpg`):
    - Sharp forward nose cone, swept delta wings, twin vertical tail fins, and dual rear thruster housings.
    """
    verts = [
        (0.0, 2.2, 0.0),      # 0: Nose tip
        (-0.45, 0.4, 0.28),   # 1: Canopy L
        (0.45, 0.4, 0.28),    # 2: Canopy R
        (0.0, 0.1, 0.48),     # 3: Canopy Ridge
        (-2.35, -0.85, -0.08),# 4: Wingtip L
        (2.35, -0.85, -0.08), # 5: Wingtip R
        (-0.65, -1.35, 0.18), # 6: Rear Body L
        (0.65, -1.35, 0.18),  # 7: Rear Body R
        (0.0, -1.45, -0.22),  # 8: Rear Belly
        (-0.85, -1.55, 0.72), # 9: Tail Fin Tip L
        (0.85, -1.55, 0.72),  # 10: Tail Fin Tip R
    ]
    faces = [
        (0, 1, 3),
        (0, 3, 2),
        (0, 4, 1),
        (0, 2, 5),
        (1, 4, 6),
        (2, 7, 5),
        (1, 6, 3),
        (3, 7, 2),
        (3, 6, 7),
        (0, 8, 4),
        (0, 5, 8),
        (4, 8, 6),
        (8, 7, 5),
        (6, 8, 7),
        (1, 6, 9),
        (2, 10, 7),
    ]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    return mesh


def _build_dreamcast_waterfall_canyon_scene(props: Any, collection: Any) -> List[Any]:
    """
    Faithfully reconstructs the Sega Dreamcast / NEC PowerVR2 3D Sci-Fi Waterfall Canyon Arena
    (`-UPttAsJ...jpg` & `d.txt`):
    - Semi-circular curved cyan-white waterfall cliff amphitheater enclosing a deep teal water basin
    - 3 bronze/gold industrial sluice towers embedded in the cliff wall
    - Right-side cliff wall bathed in vivid emerald-green bioluminescent vertex light
    - Foreground banking starfighter with `GL_SPHERE_MAP` metallic hull & multi-layer PowerVR2 translucent cyan thruster glow
    - Midground floating purple/yellow target drone over the water
    """
    objs: List[Any] = []
    wf_mat = materials.build_dc_waterfall_cliff_material(props)
    tower_mat = materials.build_dc_sluice_tower_material(props)
    biolum_mat = materials.build_dc_biolum_rock_material(props)
    hull_mat = materials.build_dc_starfighter_hull_material(props)
    cyan_glow_mat = materials.build_dc_powervr_thruster_glow_material(props, color_mode="CYAN")
    target_glow_mat = materials.build_dc_powervr_thruster_glow_material(props, color_mode="TARGET")

    # 1. Curved Semi-Circular Waterfall Cliff Amphitheater (10 segments around the basin)
    num_segs = 10
    radius = 15.5
    for i in range(num_segs):
        ang = math.radians(15.0 + (150.0 * i / float(num_segs - 1)))
        cx = radius * math.cos(ang)
        cy = 2.0 + radius * math.sin(ang)
        rot_z = ang - math.pi * 0.5
        is_right_emerald = (i <= 2)
        seg_mat = biolum_mat if is_right_emerald else wf_mat
        seg_h = 13.5 + (i % 3) * 1.4
        m = _create_hollow_building_mesh(f"{DREAM_PREFIX}DC_CliffSeg_{i}_M", 5.8, 2.4, seg_h)
        o = bpy.data.objects.new(f"{DREAM_PREFIX}DC_CliffSeg_{i}", m)
        o.location = (cx, cy, -0.5)
        o.rotation_euler = (math.radians(6.0), 0.0, rot_z)
        if seg_mat:
            o.data.materials.append(seg_mat)
        collection.objects.link(o)
        objs.append(o)

    # 2. Three Bronze/Gold Industrial Sluice Towers embedded in the Waterfall Cliff
    for t_idx, ang_deg in enumerate((52.0, 92.0, 132.0)):
        ang = math.radians(ang_deg)
        tx = (radius - 1.4) * math.cos(ang)
        ty = 2.0 + (radius - 1.4) * math.sin(ang)
        rot_z = ang - math.pi * 0.5
        tm = _create_hollow_building_mesh(f"{DREAM_PREFIX}DC_SluiceTower_{t_idx}_M", 2.3, 2.6, 14.8)
        to = bpy.data.objects.new(f"{DREAM_PREFIX}DC_SluiceTower_{t_idx}", tm)
        to.location = (tx, ty, -0.4)
        to.rotation_euler = (0.0, 0.0, rot_z)
        if tower_mat:
            to.data.materials.append(tower_mat)
        collection.objects.link(to)
        objs.append(to)

        # Upper bronze intake crown
        cm = _create_hollow_building_mesh(f"{DREAM_PREFIX}DC_TowerCrown_{t_idx}_M", 2.9, 3.0, 1.8)
        co = bpy.data.objects.new(f"{DREAM_PREFIX}DC_TowerCrown_{t_idx}", cm)
        co.location = (tx, ty, 12.6)
        co.rotation_euler = (0.0, 0.0, rot_z)
        if tower_mat:
            co.data.materials.append(tower_mat)
        collection.objects.link(co)
        objs.append(co)

    # 3. Foreground Banking Starfighter (`SDS_Dream_DC_Starfighter`)
    sf_mesh = _create_starfighter_mesh(f"{DREAM_PREFIX}DC_Starfighter_M")
    sf_obj = bpy.data.objects.new(f"{DREAM_PREFIX}DC_Starfighter", sf_mesh)
    sf_obj.location = (-1.05, -7.8, 2.35)
    sf_obj.rotation_euler = (math.radians(8.0), math.radians(-22.0), math.radians(-10.0))
    if hull_mat:
        sf_obj.data.materials.append(hull_mat)
    collection.objects.link(sf_obj)
    objs.append(sf_obj)

    # Multi-Layer PowerVR2 Order-Independent Translucent Thruster Glow Sprites (Left & Right Nozzles)
    for n_idx, nx_off in enumerate((-0.48, 0.48)):
        for layer_i, l_scale in enumerate((0.42, 0.72, 1.08)):
            gm = _create_hollow_building_mesh(
                f"{DREAM_PREFIX}DC_ThrusterGlow_{n_idx}_{layer_i}_M",
                l_scale,
                0.08,
                l_scale,
            )
            go = bpy.data.objects.new(f"{DREAM_PREFIX}DC_ThrusterGlow_{n_idx}_{layer_i}", gm)
            go.location = (-1.05 + nx_off, -9.25 - layer_i * 0.14, 2.25)
            go.rotation_euler = (0.0, math.radians(25.0 * layer_i), math.radians(-10.0))
            if cyan_glow_mat:
                go.data.materials.append(cyan_glow_mat)
            collection.objects.link(go)
            objs.append(go)

    # 4. Midground Floating Target Drone / Pod (`SDS_Dream_DC_TargetDrone`)
    dm = _create_hollow_building_mesh(f"{DREAM_PREFIX}DC_TargetDrone_M", 0.95, 0.95, 0.95)
    do = bpy.data.objects.new(f"{DREAM_PREFIX}DC_TargetDrone", dm)
    do.location = (0.25, -1.8, 2.75)
    do.rotation_euler = (math.radians(45.0), math.radians(35.0), math.radians(20.0))
    if target_glow_mat:
        do.data.materials.append(target_glow_mat)
    collection.objects.link(do)
    objs.append(do)

    # 5. PowerVR2 Order-Independent Multi-Layer Translucent Waterfall Mist Spray (`d.txt` Section 4)
    mist_mat = materials.build_dc_powervr_thruster_glow_material(props, color_mode="MIST")
    for m_idx, (mx, my, mz, m_rot) in enumerate([(-6.5, 11.5, 0.8, 0.35), (0.0, 13.5, 1.1, 0.0), (6.5, 11.5, 0.8, -0.35)]):
        mm = _create_hollow_building_mesh(f"{DREAM_PREFIX}DC_WaterfallMist_{m_idx}_M", 6.2, 0.12, 3.2)
        mo = bpy.data.objects.new(f"{DREAM_PREFIX}DC_WaterfallMist_{m_idx}", mm)
        mo.location = (mx, my, mz)
        mo.rotation_euler = (math.radians(-12.0), 0.0, m_rot)
        if mist_mat:
            mo.data.materials.append(mist_mat)
        collection.objects.link(mo)
        objs.append(mo)

    # Dreamcast uses smooth Gouraud vertex shading (`GOURAUD_VERTEX`) on curved cliff/starfighter surfaces
    for obj in objs:
        if obj.type == "MESH" and obj.data is not None:
            for poly in obj.data.polygons:
                poly.use_smooth = True

    return objs




def _create_faceted_carapace_dome_mesh(name: str, rx: float, ry: float, rim_h: float, dome_h: float) -> Any:
    """
    Creates an authentic 1998 PS1 low-poly octagonal sloped turtle carapace mesh (`e53fb9d1...jpg`):
    - Bottom flat ring (z=0), middle carapacial rim ring (z=rim_h), and narrower sloped top plate (z=rim_h+dome_h).
    """
    segs = 8
    verts = []
    faces = []
    for ring_scale, z_val in ((1.0, 0.0), (1.05, rim_h), (0.62, rim_h + dome_h)):
        for i in range(segs):
            ang = (2.0 * math.pi * i / float(segs)) + (math.pi / float(segs))
            verts.append((rx * ring_scale * math.cos(ang), ry * ring_scale * math.sin(ang), z_val))

    # Lower vertical/angled rim quads (ring 0 -> ring 1)
    for i in range(segs):
        ni = (i + 1) % segs
        faces.append((i, ni, segs + ni, segs + i))
    # Upper sloped trapezoidal carapace plates (ring 1 -> ring 2)
    for i in range(segs):
        ni = (i + 1) % segs
        faces.append((segs + i, segs + ni, 2 * segs + ni, 2 * segs + i))
    # Top octagonal cap split into flat triangles
    top_base = 2 * segs
    for i in range(1, segs - 1):
        faces.append((top_base, top_base + i, top_base + i + 1))

    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    return mesh


def _build_lsd_psychedelic_turtle_scene(props: Any, collection: Any) -> List[Any]:
    """
    Ref Image 1 (`e53fb9d1...jpg`):
    - Sloped octagonal low-poly faceted Turtle Carapace (`SDS_Dream_LSD_Turtle_*`) with eyeball-spot upper plates,
      vertical-striped lower rim, and flat-shaded teal/indigo prism legs & head!
    """
    objs: List[Any] = []
    shell_top_mat = materials.build_ps1_lsd_turtle_carapace_material(props, is_rim=False)
    shell_rim_mat = materials.build_ps1_lsd_turtle_carapace_material(props, is_rim=True)
    teal_mat = materials.build_ps1_lsd_turtle_limb_material(props, is_indigo=False)
    indigo_mat = materials.build_ps1_lsd_turtle_limb_material(props, is_indigo=True)

    tx, ty, tz = (-0.25, -4.8, 0.55)
    rot_z = math.radians(-16.0)

    # 1. Sloped Polygonal Upper Carapace Dome & Striped Lower Rim
    dome_m = _create_faceted_carapace_dome_mesh(f"{DREAM_PREFIX}LSD_TurtleDome_M", 2.15, 2.65, 0.72, 0.92)
    dome_o = bpy.data.objects.new(f"{DREAM_PREFIX}LSD_TurtleShell_Top", dome_m)
    dome_o.location = (tx, ty, tz + 0.55)
    dome_o.rotation_euler = (0.0, 0.0, rot_z)
    if shell_top_mat:
        dome_o.data.materials.append(shell_top_mat)
    collection.objects.link(dome_o)
    objs.append(dome_o)

    rim_m = _create_hollow_building_mesh(f"{DREAM_PREFIX}LSD_TurtleRim_M", 3.6, 4.4, 0.68)
    rim_o = bpy.data.objects.new(f"{DREAM_PREFIX}LSD_TurtleShell_Base", rim_m)
    rim_o.location = (tx, ty, tz + 0.15)
    rim_o.rotation_euler = (0.0, 0.0, rot_z)
    if shell_rim_mat:
        rim_o.data.materials.append(shell_rim_mat)
    collection.objects.link(rim_o)
    objs.append(rim_o)

    def _add_limb(name: str, sx: float, sy: float, sz: float, loc: Tuple[float, float, float], mat: Any, rot: Tuple[float, float, float]) -> Any:
        m = _create_hollow_building_mesh(f"{DREAM_PREFIX}{name}_M", sx, sy, sz)
        o = bpy.data.objects.new(f"{DREAM_PREFIX}{name}", m)
        o.location = loc
        o.rotation_euler = rot
        if mat:
            o.data.materials.append(mat)
        collection.objects.link(o)
        objs.append(o)
        return o

    # 2. Angled Low-Poly Prism Legs (Front-Right Teal, Front-Left Indigo, Back-Left Maroon/Indigo, Back-Right Teal)
    _add_limb("LSD_TurtleLeg_0", 0.68, 0.68, 1.35, (tx - 0.15, ty - 1.95, tz - 0.55), teal_mat, (0.08, -0.06, rot_z))
    _add_limb("LSD_TurtleLeg_1", 0.68, 0.68, 1.35, (tx + 1.45, ty - 1.35, tz - 0.55), indigo_mat, (-0.08, 0.12, rot_z))
    _add_limb("LSD_TurtleLeg_2", 0.68, 0.68, 1.35, (tx - 1.85, ty - 0.85, tz - 0.55), indigo_mat, (0.14, 0.14, rot_z))
    _add_limb("LSD_TurtleLeg_3", 0.68, 0.68, 1.35, (tx + 0.85, ty + 1.25, tz - 0.55), teal_mat, (-0.10, -0.10, rot_z))

    # 3. Protruding Angular Neck & Tapered Snout (`e53fb9d1...jpg` right side)
    _add_limb("LSD_TurtleNeck", 0.92, 1.35, 0.72, (tx + 1.45, ty - 1.55, tz + 0.32), teal_mat, (0.0, 0.15, rot_z - 0.35))
    _add_limb("LSD_TurtleHead", 0.82, 1.15, 0.64, (tx + 2.25, ty - 1.95, tz + 0.36), teal_mat, (0.0, 0.05, rot_z - 0.42))

    for obj in objs:
        if obj.type == "MESH" and obj.data is not None:
            for poly in obj.data.polygons:
                poly.use_smooth = False
    return objs


def _build_lsd_kanji_eye_giant_scene(props: Any, collection: Any) -> List[Any]:
    """
    New Ref Image 2 (`image_33a178.png`):
    - Towering glowing purple-magenta bulbous head monument covered in orange-gold Kanji character rows
    - Recessed glowing emerald-green eyeball near the upper crown + side wing fins
    - Midground mossy compound walls (`SDS_Dream_LSD_MossWall_*`) & dark traditional roof silhouettes
    - 4-pointed diagonal lens-flare sun star (`SDS_Dream_LSD_SunStar_*`) in the upper-left sky!
    """
    objs: List[Any] = []
    body_mat = materials.build_ps1_lsd_kanji_giant_material(props, role="BODY")
    eye_mat = materials.build_ps1_lsd_kanji_giant_material(props, role="EYE")
    moss_mat = materials.build_ps1_lsd_kanji_giant_material(props, role="MOSS_WALL")
    dark_mat = materials.build_ps1_lsd_purple_plaza_material(props, role="GRAY_MAN")
    sun_mat = materials.build_ps1_lsd_polkadot_floor_material(props)

    def _add_box(name: str, sx: float, sy: float, sz: float, loc: Tuple[float, float, float], mat: Any, rot: Tuple[float, float, float] = (0.0, 0.0, 0.0)) -> Any:
        m = _create_hollow_building_mesh(f"{DREAM_PREFIX}{name}_M", sx, sy, sz)
        o = bpy.data.objects.new(f"{DREAM_PREFIX}{name}", m)
        o.location = loc
        o.rotation_euler = rot
        if mat:
            o.data.materials.append(mat)
        collection.objects.link(o)
        objs.append(o)
        return o

    # 1. Giant Bulbous Purple Kanji Monument (`SDS_Dream_LSD_KanjiGiant_*`)
    gx, gy = (1.65, 2.5)
    dome_m = _create_faceted_carapace_dome_mesh(f"{DREAM_PREFIX}LSD_KanjiGiant_Body_M", 3.4, 2.8, 5.2, 2.6)
    dome_o = bpy.data.objects.new(f"{DREAM_PREFIX}LSD_KanjiGiant_Body", dome_m)
    dome_o.location = (gx, gy, 0.0)
    if body_mat:
        dome_o.data.materials.append(body_mat)
    collection.objects.link(dome_o)
    objs.append(dome_o)

    # Recessed Glowing Emerald-Green Eyeball in the upper brow slit
    _add_box("LSD_KanjiGiant_EyeSocket", 2.4, 0.45, 0.95, (gx, gy - 2.65, 5.55), eye_mat)
    # Left & Right Wing Pods flanking the monument
    _add_box("LSD_KanjiGiant_Fin_L", 1.15, 1.45, 4.6, (gx - 3.55, gy + 0.4, 0.4), body_mat, (0.0, math.radians(-12.0), 0.0))
    _add_box("LSD_KanjiGiant_Fin_R", 1.15, 1.45, 4.6, (gx + 3.55, gy + 0.4, 0.4), body_mat, (0.0, math.radians(12.0), 0.0))

    # 2. Midground Mossy Compound Walls with Central Gate Opening + Distant Dark Pagoda Roof
    _add_box("LSD_MossWall_L", 7.8, 0.65, 1.65, (-3.6, -4.2, 0.0), moss_mat)
    _add_box("LSD_MossWall_R", 6.5, 0.65, 1.65, (5.2, -4.2, 0.0), moss_mat)
    _add_box("LSD_DarkPagoda_L", 2.6, 2.4, 2.8, (-4.2, 1.2, 0.0), dark_mat)
    _add_box("LSD_DarkPagoda_Roof", 3.2, 2.8, 0.55, (-4.2, 1.2, 2.75), dark_mat)

    # 3. Upper-Left Diagonal 4-Ray Lens-Flare Sun Star (`image_33a178.png`)
    sx, sy, sz = (-2.4, 5.5, 8.2)
    _add_box("LSD_SunStar_Core", 0.65, 0.25, 0.65, (sx, sy, sz), sun_mat)
    _add_box("LSD_SunStar_Ray1", 3.8, 0.08, 0.08, (sx, sy - 0.1, sz), sun_mat, (0.0, math.radians(38.0), 0.0))
    _add_box("LSD_SunStar_Ray2", 3.2, 0.08, 0.08, (sx, sy - 0.1, sz), sun_mat, (0.0, math.radians(-48.0), 0.0))

    for obj in objs:
        if obj.type == "MESH" and obj.data is not None:
            for poly in obj.data.polygons:
                poly.use_smooth = False
    return objs


def _build_lsd_kyoto_kimono_night_scene(props: Any, collection: Any) -> List[Any]:
    """
    New Ref Image 3 (`image_33a151.png` — Kyoto Night Street, Wooden Machiya Houses & Low-Poly Kimono Woman):
    - Left Side: 2-story traditional Kyoto wooden Machiya townhouse with cyan-and-black striped pitched tile roofs
      and white-and-black vertical wooden lattice windows (`Koshi-mado`)
    - Right Side: Dark wooden compound fence + Low-Poly Flat-Shaded Kimono Geisha (`SDS_Dream_LSD_Kimono_*`)
      with wide triangular hanging floral sleeves, red lower hem, grey Geta sandals, white polygonal face & black chignon!
    """
    objs: List[Any] = []
    wall_mat = materials.build_ps1_lsd_kyoto_night_material(props, role="MACHIYA_WALL")
    roof_mat = materials.build_ps1_lsd_kyoto_night_material(props, role="CYAN_ROOF")
    silk_mat = materials.build_ps1_lsd_kyoto_night_material(props, role="KIMONO_SILK")
    red_mat = materials.build_ps1_lsd_kyoto_night_material(props, role="KIMONO_RED")
    white_mat = materials.build_ps1_lsd_kyoto_night_material(props, role="WHITE_FACE")
    black_mat = materials.build_ps1_lsd_kyoto_night_material(props, role="BLACK_HAIR")

    def _add_box(name: str, sx: float, sy: float, sz: float, loc: Tuple[float, float, float], mat: Any, rot: Tuple[float, float, float] = (0.0, 0.0, 0.0)) -> Any:
        m = _create_hollow_building_mesh(f"{DREAM_PREFIX}{name}_M", sx, sy, sz)
        o = bpy.data.objects.new(f"{DREAM_PREFIX}{name}", m)
        o.location = loc
        o.rotation_euler = rot
        if mat:
            o.data.materials.append(mat)
        collection.objects.link(o)
        objs.append(o)
        return o

    # 1. Left-Side 2-Story Kyoto Wooden Machiya Townhouse (`SDS_Dream_LSD_Machiya_*`)
    _add_box("LSD_Machiya_1F", 4.6, 5.2, 2.1, (-4.2, -5.8, 0.0), wall_mat)
    _add_box("LSD_Machiya_Eave1F", 5.2, 5.8, 0.42, (-4.2, -5.8, 2.05), roof_mat, (0.0, math.radians(12.0), 0.0))
    _add_box("LSD_Machiya_2F", 3.8, 4.4, 1.55, (-4.4, -5.6, 2.35), wall_mat)
    _add_box("LSD_Machiya_Roof2F", 4.6, 5.2, 0.65, (-4.4, -5.6, 3.85), roof_mat, (0.0, math.radians(18.0), 0.0))
    # Distant background rowhouse along the street
    _add_box("LSD_Machiya_Back", 4.2, 6.5, 3.4, (-4.6, 1.2, 0.0), wall_mat)
    _add_box("LSD_Machiya_BackRoof", 4.8, 7.0, 0.65, (-4.6, 1.2, 3.35), roof_mat)

    # 2. Right-Side Dark Perimeter Wall receding into the night street
    _add_box("LSD_KyotoFence_R", 0.65, 16.0, 2.4, (3.8, -1.5, 0.0), black_mat)

    # 3. Foreground Right: Low-Poly Flat-Shaded Kimono Geisha (`SDS_Dream_LSD_Kimono_*`)
    kx, ky = (1.65, -8.4)
    k_rot = math.radians(68.0)  # Facing toward the left street / Machiya house as in `image_33a151.png`
    # Grey Geta sandals & red lower kimono hem
    _add_box("LSD_Kimono_Geta", 0.34, 0.42, 0.16, (kx, ky, 0.0), white_mat, (0.0, 0.0, k_rot))
    _add_box("LSD_Kimono_RedHem", 0.38, 0.46, 0.42, (kx, ky, 0.16), red_mat, (0.0, 0.0, k_rot))
    # Main floral silk kimono torso & skirt
    _add_box("LSD_Kimono_Body", 0.48, 0.56, 1.38, (kx, ky, 0.52), silk_mat, (0.0, 0.0, k_rot))
    # Wide Angular Hanging Furisode Sleeves (Left & Right angled prism wings so each facet has distinct GTE flat shading!)
    _add_box("LSD_Kimono_Sleeve_L", 0.58, 0.24, 1.05, (kx - 0.28, ky - 0.18, 0.68), silk_mat, (math.radians(8.0), math.radians(-16.0), k_rot + 0.25))
    _add_box("LSD_Kimono_Sleeve_R", 0.58, 0.24, 1.05, (kx + 0.28, ky + 0.18, 0.68), silk_mat, (math.radians(-8.0), math.radians(16.0), k_rot - 0.25))
    # Red collar, stark white polygonal head/neck, and black Shimada hair chignon
    _add_box("LSD_Kimono_Collar", 0.32, 0.34, 0.18, (kx, ky, 1.88), red_mat, (0.0, 0.0, k_rot))
    _add_box("LSD_Kimono_Face", 0.28, 0.30, 0.34, (kx - 0.04, ky - 0.04, 2.04), white_mat, (0.0, math.radians(-10.0), k_rot))
    _add_box("LSD_Kimono_Hair", 0.36, 0.38, 0.36, (kx + 0.04, ky + 0.04, 2.12), black_mat, (0.0, 0.0, k_rot))

    for obj in objs:
        if obj.type == "MESH" and obj.data is not None:
            for poly in obj.data.polygons:
                poly.use_smooth = False
    return objs


def _build_lsd_gray_man_plaza_scene(props: Any, collection: Any) -> List[Any]:
    """
    Ref Image 2 (`0e0277d1...jpg`):
    - Enclosed purple-brick plaza surrounded by neon blue-violet glyph walls
    - Spiked blue-violet Sun Emblem hanging in the acid-magenta sky
    - Left-side lattice pyramid + red/cyan patterned ground strips
    - Ominous Gray Man (`SDS_Dream_LSD_GrayMan_*`) in dark trenchcoat & fedora standing dead center!
    """
    objs: List[Any] = []
    floor_mat = materials.build_ps1_lsd_purple_plaza_material(props, role="FLOOR")
    wall_mat = materials.build_ps1_lsd_purple_plaza_material(props, role="GLYPH_WALL")
    gray_mat = materials.build_ps1_lsd_purple_plaza_material(props, role="GRAY_MAN")
    sun_mat = materials.build_ps1_lsd_purple_plaza_material(props, role="SUN_EMBLEM")
    carpet_mat = materials.build_ps1_lsd_bullseye_tile_material(props, is_turtle=False)

    def _add_box(name: str, sx: float, sy: float, sz: float, loc: Tuple[float, float, float], mat: Any, rot: Tuple[float, float, float] = (0.0, 0.0, 0.0)) -> Any:
        m = _create_hollow_building_mesh(f"{DREAM_PREFIX}{name}_M", sx, sy, sz)
        o = bpy.data.objects.new(f"{DREAM_PREFIX}{name}", m)
        o.location = loc
        o.rotation_euler = rot
        if mat:
            o.data.materials.append(mat)
        collection.objects.link(o)
        objs.append(o)
        return o

    # 1. Purple Brick Plaza Floor & Side Patterned Carpet Strips
    _add_box("LSD_PlazaFloor", 24.0, 26.0, 0.25, (0.0, -4.0, -0.12), floor_mat)
    _add_box("LSD_CarpetStrip_L", 2.8, 18.0, 0.05, (-4.8, -5.0, 0.14), carpet_mat)
    _add_box("LSD_CarpetStrip_R", 2.8, 18.0, 0.05, (4.8, -5.0, 0.14), carpet_mat)

    # 2. Perimeter Neon Blue-Violet Glyph Walls
    _add_box("LSD_GlyphWall_Back", 24.0, 0.65, 3.2, (0.0, 6.5, 0.0), wall_mat)
    _add_box("LSD_GlyphWall_Left", 0.65, 24.0, 3.2, (-11.5, -4.0, 0.0), wall_mat)
    _add_box("LSD_GlyphWall_Right", 0.65, 24.0, 3.2, (11.5, -4.0, 0.0), wall_mat)

    # 3. The Gray Man (灰衣帽子男) standing in the center foreground/midground
    gx, gy = (0.0, -6.2)
    _add_box("LSD_GrayMan_Legs", 0.42, 0.28, 0.65, (gx, gy, 0.12), gray_mat)
    _add_box("LSD_GrayMan_Coat", 0.78, 0.42, 1.45, (gx, gy, 0.68), gray_mat)
    _add_box("LSD_GrayMan_Head", 0.32, 0.32, 0.36, (gx, gy, 2.12), gray_mat)
    _add_box("LSD_GrayMan_HatBrim", 0.86, 0.72, 0.07, (gx, gy, 2.36), gray_mat)
    _add_box("LSD_GrayMan_HatCrown", 0.42, 0.38, 0.24, (gx, gy, 2.42), gray_mat)

    # 4. Left-Side Lattice / Frame Pyramid (`SDS_Dream_LSD_LatticePyramid`)
    px, py = (-2.65, -9.2)
    for idx, (dx, dy, r_x, r_y) in enumerate([
        (-0.85, -0.85, -0.28, 0.28),
        (0.85, -0.85, -0.28, -0.28),
        (0.85, 0.85, 0.28, -0.28),
        (-0.85, 0.85, 0.28, 0.28),
    ]):
        _add_box(f"LSD_PyramidStrut_{idx}", 0.12, 0.12, 3.4, (px + dx * 0.5, py + dy * 0.5, 0.1), carpet_mat, (r_x, r_y, 0.0))

    # 5. Overhead Spiked Blue-Violet Sun Emblem (`SDS_Dream_LSD_SunEmblem`)
    sx, sy, sz = (0.8, 3.5, 6.4)
    _add_box("LSD_SunCore", 1.65, 0.18, 1.65, (sx, sy, sz), sun_mat)
    for r_i in range(8):
        ang = r_i * (math.pi * 0.25)
        rx = sx + math.cos(ang) * 1.45
        rz = sz + math.sin(ang) * 1.45
        _add_box(f"LSD_SunRay_{r_i}", 0.22, 0.12, 0.95, (rx, sy, rz), sun_mat, (0.0, ang - math.pi * 0.5, 0.0))

    for obj in objs:
        if obj.type == "MESH" and obj.data is not None:
            for poly in obj.data.polygons:
                poly.use_smooth = False
    return objs


def _build_lsd_flesh_tunnel_scene(props: Any, collection: Any) -> List[Any]:
    """
    Ref Image 3 (`400e7d72...jpg`):
    - Organic mottled meat/flesh tunnel with extreme vertical UV clamp stretching on lower side walls
    - Blinding #ff0000 blood-red fog portal at the end of the tunnel
    - Chunky white & red mascot doll standing inside the tunnel
    """
    objs: List[Any] = []
    flesh_mat = materials.build_ps1_lsd_flesh_tunnel_material(props, is_wall_stretched=False)
    stretch_mat = materials.build_ps1_lsd_flesh_tunnel_material(props, is_wall_stretched=True)
    red_portal_mat = materials.build_ps1_lsd_red_portal_material(props)
    doll_white_mat = materials.build_ps1_lsd_polkadot_floor_material(props)

    def _add_box(name: str, sx: float, sy: float, sz: float, loc: Tuple[float, float, float], mat: Any, rot: Tuple[float, float, float] = (0.0, 0.0, 0.0)) -> Any:
        m = _create_hollow_building_mesh(f"{DREAM_PREFIX}{name}_M", sx, sy, sz)
        o = bpy.data.objects.new(f"{DREAM_PREFIX}{name}", m)
        o.location = loc
        o.rotation_euler = rot
        if mat:
            o.data.materials.append(mat)
        collection.objects.link(o)
        objs.append(o)
        return o

    # 1. Flesh Tunnel Floor, Vertically-Stretched Lower Walls, Angled Upper Vaults & Ceiling
    _add_box("LSD_FleshFloor", 4.6, 22.0, 0.35, (0.0, -5.0, -0.15), flesh_mat)
    _add_box("LSD_FleshWall_L", 0.45, 22.0, 1.65, (-2.1, -5.0, 0.15), stretch_mat)
    _add_box("LSD_FleshWall_R", 0.45, 22.0, 1.65, (2.1, -5.0, 0.15), stretch_mat)
    _add_box("LSD_FleshVault_L", 0.45, 22.0, 1.65, (-1.65, -5.0, 1.65), flesh_mat, (0.0, math.radians(38.0), 0.0))
    _add_box("LSD_FleshVault_R", 0.45, 22.0, 1.65, (1.65, -5.0, 1.65), flesh_mat, (0.0, math.radians(-38.0), 0.0))
    _add_box("LSD_FleshCeiling", 3.6, 22.0, 0.35, (0.0, -5.0, 2.75), flesh_mat)

    # 2. Blinding #ff0000 Blood-Red Fog Portal at End of Tunnel
    _add_box("LSD_RedFogPortal", 4.8, 0.35, 3.4, (0.0, 4.5, 0.0), red_portal_mat)

    # 3. Chunky White/Red Mascot Doll standing at (0.1, -7.8)
    dx, dy = (0.08, -7.8)
    _add_box("LSD_MascotLeg_L", 0.24, 0.24, 0.45, (dx - 0.22, dy, 0.15), doll_white_mat)
    _add_box("LSD_MascotLeg_R", 0.24, 0.24, 0.45, (dx + 0.22, dy, 0.15), doll_white_mat)
    _add_box("LSD_MascotTorso", 0.72, 0.52, 0.68, (dx, dy, 0.55), doll_white_mat)
    _add_box("LSD_MascotRedBib", 0.48, 0.12, 0.48, (dx, dy - 0.24, 0.65), red_portal_mat, (0.0, math.radians(45.0), 0.0))
    _add_box("LSD_MascotHead", 0.46, 0.44, 0.42, (dx, dy, 1.24), doll_white_mat)
    _add_box("LSD_MascotArm_L", 0.38, 0.20, 0.20, (dx - 0.48, dy, 0.92), doll_white_mat, (0.0, math.radians(25.0), 0.0))
    _add_box("LSD_MascotArm_R", 0.38, 0.20, 0.20, (dx + 0.48, dy, 0.92), doll_white_mat, (0.0, math.radians(-25.0), 0.0))

    for obj in objs:
        if obj.type == "MESH" and obj.data is not None:
            for poly in obj.data.polygons:
                poly.use_smooth = False
    return objs


def _build_lsd_graffiti_corridor_scene(props: Any, collection: Any) -> List[Any]:
    """
    Ref Image 4 (`5aae83fb...jpg`):
    - White floor covered in overlapping CMYK/RGB neon polka-dots
    - Long perspective walls covered in heavily dithered acid-green/yellow/red/blue collage graffiti
    - Pitch-black Bayer-dithered ceiling and deep black distance fog
    """
    objs: List[Any] = []
    floor_mat = materials.build_ps1_lsd_polkadot_floor_material(props)
    wall_mat = materials.build_ps1_lsd_graffiti_wall_material(props)
    black_mat = materials.build_ps1_lsd_purple_plaza_material(props, role="GRAY_MAN")

    def _add_box(name: str, sx: float, sy: float, sz: float, loc: Tuple[float, float, float], mat: Any) -> Any:
        m = _create_hollow_building_mesh(f"{DREAM_PREFIX}{name}_M", sx, sy, sz)
        o = bpy.data.objects.new(f"{DREAM_PREFIX}{name}", m)
        o.location = loc
        if mat:
            o.data.materials.append(mat)
        collection.objects.link(o)
        objs.append(o)
        return o

    _add_box("LSD_PolkaFloor", 6.5, 28.0, 0.25, (0.5, -2.0, -0.12), floor_mat)
    _add_box("LSD_GraffitiWall_L", 0.45, 28.0, 2.85, (-1.85, -2.0, 0.0), wall_mat)
    _add_box("LSD_GraffitiWall_R", 0.45, 28.0, 2.85, (3.25, -2.0, 0.0), wall_mat)
    _add_box("LSD_DarkCeiling", 6.5, 28.0, 0.45, (0.5, -2.0, 2.85), black_mat)

    for obj in objs:
        if obj.type == "MESH" and obj.data is not None:
            for poly in obj.data.polygons:
                poly.use_smooth = False
    return objs


def compose_dreamspace(context: Any, props: Any, collection: Any) -> None:
    """
    Builds the《LSD: Dream Emulator》spatial graph and anomalous architectural modules
    directly inside the active scene collection.
    """
    if bpy is None:
        return

    clear_dreamspace_objects()
    arch_mode = getattr(props, "dream_architecture_mode", "NONE")
    if arch_mode == "NONE":
        return
    if arch_mode == "BRIGHT_MOON_COTTAGE":
        objs = _build_bright_moon_cottage_scene(props, collection)
        for o in objs:
            if getattr(o, "type", "") == "MESH" and getattr(o, "data", None) is not None:
                cache_base_vertices(o.data)
            apply_era_geometry_modifiers(o, props)
        return
    if arch_mode == "KOWLOON_WALLED_ALLEY":
        objs = _build_kowloons_gate_alley_scene(props, collection)
        for o in objs:
            if getattr(o, "type", "") == "MESH" and getattr(o, "data", None) is not None:
                cache_base_vertices(o.data)
            apply_era_geometry_modifiers(o, props)
        return
    if arch_mode == "ICO_CASTLE_BRIDGE":
        objs = _build_ico_castle_bridge_scene(props, collection)
        for o in objs:
            if getattr(o, "type", "") == "MESH" and getattr(o, "data", None) is not None:
                cache_base_vertices(o.data)
            apply_era_geometry_modifiers(o, props)
        return
    if arch_mode == "DC_WATERFALL_ARENA":
        objs = _build_dreamcast_waterfall_canyon_scene(props, collection)
        for o in objs:
            if getattr(o, "type", "") == "MESH" and getattr(o, "data", None) is not None:
                cache_base_vertices(o.data)
            apply_era_geometry_modifiers(o, props)
        return
    if arch_mode == "LSD_TURTLE_HILLS":
        objs = _build_lsd_psychedelic_turtle_scene(props, collection)
        for o in objs:
            apply_era_geometry_modifiers(o, props)
        return
    if arch_mode == "LSD_GRAY_MAN_PLAZA":
        objs = _build_lsd_gray_man_plaza_scene(props, collection)
        for o in objs:
            apply_era_geometry_modifiers(o, props)
        return
    if arch_mode == "LSD_FLESH_TUNNEL":
        objs = _build_lsd_flesh_tunnel_scene(props, collection)
        for o in objs:
            apply_era_geometry_modifiers(o, props)
        return
    if arch_mode == "LSD_GRAFFITI_CORRIDOR":
        objs = _build_lsd_graffiti_corridor_scene(props, collection)
        for o in objs:
            apply_era_geometry_modifiers(o, props)
        return
    if arch_mode == "LSD_KANJI_EYE_GIANT":
        objs = _build_lsd_kanji_eye_giant_scene(props, collection)
        for o in objs:
            apply_era_geometry_modifiers(o, props)
        return
    if arch_mode == "LSD_KYOTO_KIMONO_NIGHT":
        objs = _build_lsd_kyoto_kimono_night_scene(props, collection)
        for o in objs:
            apply_era_geometry_modifiers(o, props)
        return
    if arch_mode == "ICO_CASTLE_BRIDGE":
        objs = _build_ico_castle_bridge_scene(props, collection)
        for o in objs:
            if getattr(o, "type", "") == "MESH" and getattr(o, "data", None) is not None:
                cache_base_vertices(o.data)
            apply_era_geometry_modifiers(o, props)
        return
    if arch_mode == "DC_WATERFALL_ARENA":
        objs = _build_dreamcast_waterfall_canyon_scene(props, collection)
        for o in objs:
            if getattr(o, "type", "") == "MESH" and getattr(o, "data", None) is not None:
                cache_base_vertices(o.data)
            apply_era_geometry_modifiers(o, props)
        return
    if arch_mode == "ICO_CASTLE_BRIDGE":
        objs = _build_ico_castle_bridge_scene(props, collection)
        for o in objs:
            if getattr(o, "type", "") == "MESH" and getattr(o, "data", None) is not None:
                cache_base_vertices(o.data)
            apply_era_geometry_modifiers(o, props)
        return
    if arch_mode == "DC_WATERFALL_ARENA":
        objs = _build_dreamcast_waterfall_canyon_scene(props, collection)
        for o in objs:
            if getattr(o, "type", "") == "MESH" and getattr(o, "data", None) is not None:
                cache_base_vertices(o.data)
            apply_era_geometry_modifiers(o, props)
        return
    if arch_mode == "ICO_CASTLE_BRIDGE":
        objs = _build_ico_castle_bridge_scene(props, collection)
        for o in objs:
            if getattr(o, "type", "") == "MESH" and getattr(o, "data", None) is not None:
                cache_base_vertices(o.data)
            apply_era_geometry_modifiers(o, props)
        return
    if arch_mode == "DC_WATERFALL_ARENA":
        objs = _build_dreamcast_waterfall_canyon_scene(props, collection)
        for o in objs:
            if getattr(o, "type", "") == "MESH" and getattr(o, "data", None) is not None:
                cache_base_vertices(o.data)
            apply_era_geometry_modifiers(o, props)
        return
    if arch_mode == "ICO_CASTLE_BRIDGE":
        objs = _build_ico_castle_bridge_scene(props, collection)
        for o in objs:
            if getattr(o, "type", "") == "MESH" and getattr(o, "data", None) is not None:
                cache_base_vertices(o.data)
            apply_era_geometry_modifiers(o, props)
        return
    if arch_mode == "DC_WATERFALL_ARENA":
        objs = _build_dreamcast_waterfall_canyon_scene(props, collection)
        for o in objs:
            if getattr(o, "type", "") == "MESH" and getattr(o, "data", None) is not None:
                cache_base_vertices(o.data)
            apply_era_geometry_modifiers(o, props)
        return
    if arch_mode == "ICO_CASTLE_BRIDGE":
        objs = _build_ico_castle_bridge_scene(props, collection)
        for o in objs:
            if getattr(o, "type", "") == "MESH" and getattr(o, "data", None) is not None:
                cache_base_vertices(o.data)
            apply_era_geometry_modifiers(o, props)
        return
    if arch_mode == "DC_WATERFALL_ARENA":
        objs = _build_dreamcast_waterfall_canyon_scene(props, collection)
        for o in objs:
            if getattr(o, "type", "") == "MESH" and getattr(o, "data", None) is not None:
                cache_base_vertices(o.data)
            apply_era_geometry_modifiers(o, props)
        return

    seed = int(getattr(props, "seed", 1998))
    anom_pct = max(0.0, min(100.0, float(getattr(props, "dream_scale_anomaly", 50.0)))) / 100.0
    tilt_deg = float(getattr(props, "dream_tilt_anomaly", 0.0))
    tilt_rad = math.radians(tilt_deg)
    flat_sh = getattr(props, "shading_interpolation", "PHONG_SMOOTH") == "FLAT_FACETED"

    created_objs: List[Any] = []

    if arch_mode in ("CORRIDOR_TO_HILLS", "MIXED_DREAM_GRAPH"):
        # 1. Foreground Corridor connecting directly out onto the terrain/lake
        c_mesh = _create_hollow_corridor_mesh(f"{DREAM_PREFIX}CorridorMesh", 3.4, 7.5, 2.9, 0.22)
        c_obj = bpy.data.objects.new(f"{DREAM_PREFIX}EntryCorridor", c_mesh)
        c_obj.location = (0.0, -10.8, 0.05)
        c_obj.rotation_euler = (tilt_rad * 0.4, -tilt_rad * 0.3, 0.0)
        c_mat = _select_dream_material(props, "CORRIDOR", 0)
        if c_mat:
            c_obj.data.materials.append(c_mat)
        collection.objects.link(c_obj)
        created_objs.append(c_obj)

    if arch_mode in ("WALLED_COMPOUND", "MIXED_DREAM_GRAPH"):
        # 2. Repeated Apartment / Industrial Blocks with Scale & Proportion Anomalies
        tower_specs = [
            ((-6.2, -3.5, 0.0), (2.8, 2.6, 6.5), 0.12),
            ((6.4, -2.8, 0.0), (2.4, 2.4, 8.2), -0.18),
            ((-3.8, 3.2, 0.4), (3.2, 2.8, 11.5), 0.05),
            ((4.5, 4.0, 0.2), (2.6, 2.6, 9.8), -0.08),
        ]
        for idx, (loc, dims, rot_z) in enumerate(tower_specs):
            # Apply Scale & Proportion Anomaly (b.txt Section 3.2)
            s_jit = 1.0 + anom_pct * (terrain._hash2d(idx, seed, 41) * 1.4 - 0.4)
            z_stretch = 1.0 + anom_pct * (terrain._hash2d(idx, seed, 83) * 1.6)
            bx = dims[0] * s_jit
            by = dims[1] * s_jit
            bz = dims[2] * z_stretch
            b_mesh = _create_hollow_building_mesh(f"{DREAM_PREFIX}BuildingMesh_{idx}", bx, by, bz)
            b_obj = bpy.data.objects.new(f"{DREAM_PREFIX}Building_{idx}", b_mesh)
            b_obj.location = loc
            b_obj.rotation_euler = (
                tilt_rad * (terrain._hash2d(idx, seed, 12) - 0.5),
                tilt_rad * (terrain._hash2d(idx, seed, 29) - 0.5),
                rot_z,
            )
            b_mat = _select_dream_material(props, "TOWER", idx + 1)
            if b_mat:
                b_obj.data.materials.append(b_mat)
            collection.objects.link(b_obj)
            created_objs.append(b_obj)

    if arch_mode in ("IMPOSSIBLE_STAIRS_TOWERS", "MIXED_DREAM_GRAPH"):
        # 3. Disconnected Stairways climbing into the sky + Megalithic Facade Pillars
        st_mesh = _create_staircase_mesh(f"{DREAM_PREFIX}StairMesh_0", 2.2, 14, 0.48, 0.36)
        st_obj = bpy.data.objects.new(f"{DREAM_PREFIX}FloatingStairs_0", st_mesh)
        st_obj.location = (-1.8, -5.5, 0.2)
        st_obj.rotation_euler = (tilt_rad * 0.5, 0.0, math.radians(22.0))
        st_mat = _select_dream_material(props, "STAIRS", 5)
        if st_mat:
            st_obj.data.materials.append(st_mat)
        collection.objects.link(st_obj)
        created_objs.append(st_obj)

        # Second high floating staircase at an impossible angle
        st_mesh2 = _create_staircase_mesh(f"{DREAM_PREFIX}StairMesh_1", 1.8, 12, 0.45, 0.35)
        st_obj2 = bpy.data.objects.new(f"{DREAM_PREFIX}FloatingStairs_1", st_mesh2)
        st_obj2.location = (2.6, -2.0, 3.4)
        st_obj2.rotation_euler = (0.0, tilt_rad, math.radians(-38.0))
        st_mat2 = _select_dream_material(props, "STAIRS", 6)
        if st_mat2:
            st_obj2.data.materials.append(st_mat2)
        collection.objects.link(st_obj2)
        created_objs.append(st_obj2)

        # Tall Megalithic Ruin / Tower Pillars
        for idx, (px, py, ph) in enumerate([(-4.5, -1.2, 8.5), (4.8, -0.5, 10.5), (0.5, 4.5, 14.0)]):
            h_anom = ph * (1.0 + anom_pct * 0.65)
            p_mesh = _create_hollow_building_mesh(f"{DREAM_PREFIX}TowerMesh_{idx}", 2.2, 2.2, h_anom)
            p_obj = bpy.data.objects.new(f"{DREAM_PREFIX}Tower_{idx}", p_mesh)
            p_obj.location = (px, py, 0.0)
            p_obj.rotation_euler = (0.0, tilt_rad * 0.6, idx * 0.4)
            p_mat = _select_dream_material(props, "TOWER", idx + 2)
            if p_mat:
                p_obj.data.materials.append(p_mat)
            collection.objects.link(p_obj)
            created_objs.append(p_obj)

    for obj in created_objs:
        if obj.type == "MESH" and obj.data is not None:
            for poly in obj.data.polygons:
                poly.use_smooth = not flat_sh
            cache_base_vertices(obj.data)
        apply_era_geometry_modifiers(obj, props)
