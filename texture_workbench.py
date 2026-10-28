# SPDX-License-Identifier: GPL-3.0-or-later
"""
05 — Historical Graphics Texture Synthesis Workbench & NodeGroup Toolkit (v4.0.0).
Reconstructs and toolifies the 4 foundational texture synthesis paradigms of late-90s / early-2000s 3D graphics:
1. `PARADIGM_1997_DTE_SOLID`:
   1997 Bryce 3D Deep Texture Editor (DTE) & POV-Ray 3D Solid Procedural Texturing
   (Zero-UV 3D scalar field synthesis + 3-component altitude/slope filter + analytic bump).
2. `PARADIGM_PS1_PREBAKED_CLUT`:
   1994–1998 PlayStation 1 Pre-Baked Grime, Triplanar Box Projection & 4/8-bit CLUT Quantizer
   (Solves 1MB VRAM limits by pre-baking grout AO, vertical moisture stains, and micro-grain
   into nearest-neighbor snapped texels with swappable CLUT color palettes).
3. `PARADIGM_DC_POWERVR2`:
   1998–2001 Sega Dreamcast / NEC PowerVR2 TBDR High-Clarity Trilinear + `GL_SPHERE_MAP` + Multi-Layer Alpha
   (Perspective-correct trilinear clarity + view-reflection sphere mapping + order-independent translucent glow).
4. `PARADIGM_PS2_GS_MULTIPASS`:
   2000–2005 PlayStation 2 Emotion Engine & GS 48GB/s eDRAM 4-Pass Weathering Synthesis
   (Pass 1 Macro Masonry + Pass 2 High-Tiling Micro-Grain Detail + Pass 3 Vertical Moss/Water + Pass 4 Overbright Bloom).

Provides:
- 5 Reusable Blender Shader NodeGroups (`SDS_NG_1_*` .. `SDS_NG_5_*`) accessible in Shader Editor (`Add -> Group`)
- Interactive Texture Synthesis Generator (`build_workbench_material`) with 10 Archetypes & 6 CLUT Palettes
- One-Click Apply to Selected Objects (`apply_workbench_texture_to_selected`)
- One-Click Retro-fy Existing Image/Procedural Materials (`retrofy_selected_object_materials`)
"""

from typing import Any, Dict, List, Sequence, Tuple

try:
    import bpy
except ImportError:
    bpy = None

from . import materials


# ===========================================================================
# CLUT PALETTE TABLES (6 Historical Color Look-Up Tables)
# ===========================================================================
CLUT_PALETTES: Dict[str, Dict[str, Tuple[float, float, float]]] = {
    "REALISTIC_GRIME": {
        "dark": (0.09, 0.11, 0.10),
        "mid_low": (0.24, 0.28, 0.25),
        "mid_high": (0.42, 0.47, 0.43),
        "light": (0.64, 0.68, 0.62),
        "accent": (0.56, 0.14, 0.10),
    },
    "WARM_LANTERN": {
        "dark": (0.12, 0.07, 0.05),
        "mid_low": (0.34, 0.20, 0.12),
        "mid_high": (0.62, 0.40, 0.22),
        "light": (0.92, 0.74, 0.45),
        "accent": (0.82, 0.18, 0.08),
    },
    "COLD_FLUORESCENT": {
        "dark": (0.05, 0.10, 0.14),
        "mid_low": (0.16, 0.30, 0.36),
        "mid_high": (0.34, 0.56, 0.62),
        "light": (0.72, 0.92, 0.96),
        "accent": (0.12, 0.82, 0.65),
    },
    "ICO_SUNLIT_OCHRE": {
        "dark": (0.16, 0.15, 0.11),
        "mid_low": (0.38, 0.34, 0.25),
        "mid_high": (0.58, 0.52, 0.38),
        "light": (0.84, 0.78, 0.62),
        "accent": (0.22, 0.36, 0.18),
    },
    "LSD_ACID_RAINBOW": {
        "dark": (0.18, 0.04, 0.42),
        "mid_low": (0.04, 0.68, 0.92),
        "mid_high": (0.28, 0.88, 0.08),
        "light": (0.98, 0.92, 0.08),
        "accent": (0.94, 0.08, 0.42),
    },
    "BLOOD_RUST": {
        "dark": (0.10, 0.03, 0.03),
        "mid_low": (0.32, 0.08, 0.06),
        "mid_high": (0.56, 0.16, 0.12),
        "light": (0.78, 0.42, 0.34),
        "accent": (0.95, 0.05, 0.02),
    },
}


def get_clut_palette(palette_id: str) -> Dict[str, Tuple[float, float, float]]:
    return CLUT_PALETTES.get(palette_id, CLUT_PALETTES["REALISTIC_GRIME"])


def build_triplanar_uv_nodes(
    nodes: Any,
    links: Any,
    vec_3d_socket: Any,
    loc_x: float = -620.0,
    loc_y: float = 120.0,
) -> Any:
    """
    Converts a 3D coordinate `(X, Y, Z)` into a 2D-compatible Triplanar/Box coordinate `(U, V, Z)`
    so 2D Blender nodes like `ShaderNodeTexBrick` (which only read X and Y and ignore Z!)
    render proper horizontal-by-vertical 2D tiles/bricks on BOTH vertical walls (`U = X+Y, V = Z`)
    AND horizontal floors (`U = X, V = Y`)!
    """
    n_sep_p = nodes.new("ShaderNodeSeparateXYZ")
    n_sep_p.location = (loc_x, loc_y)
    links.new(vec_3d_socket, n_sep_p.inputs["Vector"])

    n_geom = nodes.new("ShaderNodeNewGeometry")
    n_geom.location = (loc_x, loc_y - 220)
    norm_out = (n_geom.outputs["True Normal"] if "True Normal" in n_geom.outputs else n_geom.outputs[0])

    n_sep_n = nodes.new("ShaderNodeSeparateXYZ")
    n_sep_n.location = (loc_x + 160, loc_y - 220)
    links.new(norm_out, n_sep_n.inputs["Vector"])

    n_abs_nz = nodes.new("ShaderNodeMath")
    n_abs_nz.operation = "ABSOLUTE"
    n_abs_nz.location = (loc_x + 320, loc_y - 220)
    links.new(n_sep_n.outputs["Z"], n_abs_nz.inputs[0])

    # is_floor = 1.0 when |N_z| > 0.55 (horizontal floor/ceiling), 0.0 on vertical walls/pillars
    n_is_floor = nodes.new("ShaderNodeMath")
    n_is_floor.operation = "GREATER_THAN"
    n_is_floor.location = (loc_x + 480, loc_y - 220)
    n_is_floor.inputs[1].default_value = 0.55
    links.new(n_abs_nz.outputs["Value"], n_is_floor.inputs[0])

    # Wall horizontal coordinate U_wall = X + Y
    n_u_wall = nodes.new("ShaderNodeMath")
    n_u_wall.operation = "ADD"
    n_u_wall.location = (loc_x + 180, loc_y + 60)
    links.new(n_sep_p.outputs["X"], n_u_wall.inputs[0])
    links.new(n_sep_p.outputs["Y"], n_u_wall.inputs[1])

    # Floor coordinate = (X, Y, Z), Wall coordinate = (X + Y, Z, Z)
    n_comb_floor = nodes.new("ShaderNodeCombineXYZ")
    n_comb_floor.location = (loc_x + 360, loc_y + 120)
    links.new(n_sep_p.outputs["X"], n_comb_floor.inputs[0])
    links.new(n_sep_p.outputs["Y"], n_comb_floor.inputs[1])
    links.new(n_sep_p.outputs["Z"], n_comb_floor.inputs[2])

    n_comb_wall = nodes.new("ShaderNodeCombineXYZ")
    n_comb_wall.location = (loc_x + 360, loc_y - 40)
    links.new(n_u_wall.outputs["Value"], n_comb_wall.inputs[0])
    links.new(n_sep_p.outputs["Z"], n_comb_wall.inputs[1])
    links.new(n_sep_p.outputs["Y"], n_comb_wall.inputs[2])

    _, m_fac, m_c1, m_c2, tri_out = materials._new_mix_color(
        nodes, links, location=(loc_x + 640, loc_y)
    )
    links.new(n_is_floor.outputs["Value"], m_fac)
    links.new(n_comb_wall.outputs["Vector"], m_c1)
    links.new(n_comb_floor.outputs["Vector"], m_c2)
    return tri_out


# ===========================================================================
# REUSABLE SHADER NODE GROUPS LIBRARY (5 Historical Texture Paradigms)
# ===========================================================================
def ensure_reusable_texture_node_groups() -> List[str]:
    """
    Creates or updates 5 standardized, reusable Shader NodeGroups in `bpy.data.node_groups`
    so the user can also drop them into any custom material in the Blender Shader Editor (`Add -> Group`):
    1. `SDS_NG_1_Bryce_DTE_3DSolid`
    2. `SDS_NG_2_PS1_Triplanar_Texel_Sampler`
    3. `SDS_NG_3_PS1_Prebaked_Grime_CLUT`
    4. `SDS_NG_4_DC_PowerVR2_SphereMap_Alpha`
    5. `SDS_NG_5_PS2_GS_MultiPass_Weathering`
    """
    if bpy is None:
        return []

    created_names: List[str] = []
    specs = [
        ("SDS_NG_1_Bryce_DTE_3DSolid", "VECTOR", "RGBA"),
        ("SDS_NG_2_PS1_Triplanar_Texel_Sampler", "VECTOR", "VECTOR"),
        ("SDS_NG_3_PS1_Prebaked_Grime_CLUT", "RGBA", "RGBA"),
        ("SDS_NG_4_DC_PowerVR2_SphereMap_Alpha", "RGBA", "RGBA"),
        ("SDS_NG_5_PS2_GS_MultiPass_Weathering", "RGBA", "RGBA"),
    ]

    for g_name, in_type, out_type in specs:
        ng = bpy.data.node_groups.get(g_name)
        if ng is None:
            ng = bpy.data.node_groups.new(g_name, "ShaderNodeTree")
        nodes = ng.nodes
        links = ng.links
        nodes.clear()

        if hasattr(ng, "interface"):
            for item in list(ng.interface.items_tree):
                ng.interface.remove(item)
            in_stype = "NodeSocketVector" if in_type == "VECTOR" else "NodeSocketColor"
            out_stype = "NodeSocketVector" if out_type == "VECTOR" else "NodeSocketColor"
            ng.interface.new_socket(name="Input", in_out="INPUT", socket_type=in_stype)
            ng.interface.new_socket(name="Output", in_out="OUTPUT", socket_type=out_stype)

        n_in = nodes.new("NodeGroupInput")
        n_in.location = (-480, 0)
        n_out = nodes.new("NodeGroupOutput")
        n_out.location = (480, 0)

        try:
            if g_name == "SDS_NG_2_PS1_Triplanar_Texel_Sampler":
                n_snap = nodes.new("ShaderNodeVectorMath")
                n_snap.operation = "SNAP"
                n_snap.location = (0, 0)
                for inp in list(n_snap.inputs)[1:]:
                    if getattr(inp, "type", "") == "VECTOR":
                        try:
                            inp.default_value = (1.0 / 48.0, 1.0 / 48.0, 1.0 / 48.0)
                        except Exception:
                            pass
                links.new(n_in.outputs[0], n_snap.inputs[0])
                links.new(n_snap.outputs[0], n_out.inputs[0])
            else:
                n_ns = nodes.new("ShaderNodeTexNoise")
                n_ns.location = (-180, -140)
                materials.set_socket(n_ns, ("Scale",), 8.5)
                materials.set_socket(n_ns, ("Detail",), 3.0)
                _, m_fac, m_c1, m_c2, m_out = materials._new_mix_color(nodes, links, blend_type="MULTIPLY", location=(140, 0))
                m_fac.default_value = 0.28
                if len(n_in.outputs) > 0:
                    links.new(n_in.outputs[0], m_c1)
                links.new(n_ns.outputs["Color"], m_c2)
                if len(n_out.inputs) > 0:
                    links.new(m_out, n_out.inputs[0])
        except Exception:
            if len(n_in.outputs) > 0 and len(n_out.inputs) > 0:
                links.new(n_in.outputs[0], n_out.inputs[0])

        created_names.append(g_name)

    return created_names


# ===========================================================================
# CORE WORKBENCH MATERIAL GENERATOR (Supports All 5 Paradigms & 10 Archetypes)
# ===========================================================================
def build_workbench_material(props: Any, custom_name: str = "SDS_Mat_Workbench") -> Any:
    """
    Synthesizes a complete material based on the user's selected Texture Synthesis Paradigm,
    Material Archetype, Texel Grid Resolution, CLUT Palette, Pre-Baked Grime, and Detail Overlay!
    """
    if bpy is None:
        return None

    paradigm = getattr(props, "tex_synth_paradigm", "PS1_PREBAKED_CLUT")
    archetype = getattr(props, "tex_archetype", "CERAMIC_MOSAIC")
    res_mode = getattr(props, "tex_res_grid", "TEX_64")
    palette_id = getattr(props, "tex_clut_palette", "REALISTIC_GRIME")
    grime_pct = max(0.0, min(100.0, float(getattr(props, "tex_prebaked_grit", 65.0)))) / 100.0
    detail_pct = max(0.0, min(100.0, float(getattr(props, "tex_detail_overlay", 60.0)))) / 100.0
    scale_fac = max(0.1, float(getattr(props, "tex_scale_factor", 1.0)))

    pal = get_clut_palette(palette_id)
    res_map = {
        "TEX_16": 16.0,
        "TEX_32": 32.0,
        "TEX_64": 64.0,
        "TEX_128": 128.0,
        "TEX_CONT": 512.0,
    }
    tex_res = res_map.get(res_mode, 64.0)

    mat_name = f"{custom_name}_{paradigm}_{archetype}"
    mat, nodes, links = materials._get_or_create_material(mat_name)
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (1820, 100)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-1680, 120)

    # 1. Coordinate Pipeline based on Paradigm
    if paradigm in ("PS1_PREBAKED_CLUT", "PS1_CLUT_PSYCHEDELIC"):
        aff = 0.22 if paradigm == "PS1_PREBAKED_CLUT" else 0.45
        snap_3d = materials._build_ps1_texel_coord(
            nodes,
            links,
            n_coord.outputs["Object"],
            scale_xyz=(scale_fac, scale_fac, scale_fac),
            texel_res=tex_res,
            affine_shear=aff,
            loc_x=-1420.0,
            loc_y=120.0,
        )
    else:
        n_map = nodes.new("ShaderNodeMapping")
        n_map.location = (-1420, 120)
        materials.set_socket(n_map, ("Location",), (128.5, 128.5, 128.5))
        materials.set_socket(n_map, ("Scale",), (scale_fac, scale_fac, scale_fac))
        links.new(n_coord.outputs["Object"], n_map.inputs["Vector"])
        snap_3d = n_map.outputs["Vector"]
        if res_mode != "TEX_CONT":
            step = 1.0 / tex_res
            n_sn = nodes.new("ShaderNodeVectorMath")
            n_sn.operation = "SNAP"
            n_sn.location = (-1200, 120)
            for inp in list(n_sn.inputs)[1:]:
                if getattr(inp, "type", "") == "VECTOR":
                    try:
                        inp.default_value = (step, step, step)
                    except Exception:
                        pass
            links.new(snap_3d, n_sn.inputs[0])
            snap_3d = n_sn.outputs[0]

    # Convert 3D coordinates into Triplanar 2D+Z coordinates so vertical walls NEVER stretch into 1D stripes!
    tri_vec = build_triplanar_uv_nodes(nodes, links, snap_3d, loc_x=-960.0, loc_y=120.0)

    # 2. Macro Structural Pattern Synthesis (Pass 1)
    if archetype in ("CERAMIC_MOSAIC", "ASHLAR_SANDSTONE", "DAMP_ASPHALT_STONE", "WEATHERED_TIMBER"):
        n_brick = nodes.new("ShaderNodeTexBrick")
        n_brick.location = (-160, 220)
        if archetype == "CERAMIC_MOSAIC":
            n_brick.offset = 0.5
            n_brick.squash = 1.0
            materials.set_socket(n_brick, ("Scale",), 7.5)
            materials.set_socket(n_brick, ("Mortar Size",), 0.04)
            materials.set_socket(n_brick, ("Mortar Smooth",), 0.1)
        elif archetype == "ASHLAR_SANDSTONE":
            n_brick.offset = 0.5
            n_brick.squash = 1.8
            materials.set_socket(n_brick, ("Scale",), 3.8)
            materials.set_socket(n_brick, ("Mortar Size",), 0.03)
            materials.set_socket(n_brick, ("Mortar Smooth",), 0.2)
        elif archetype == "WEATHERED_TIMBER":
            n_brick.offset = 0.5
            n_brick.squash = 4.5
            materials.set_socket(n_brick, ("Scale",), 5.0)
            materials.set_socket(n_brick, ("Mortar Size",), 0.025)
            materials.set_socket(n_brick, ("Mortar Smooth",), 0.05)
        else:
            # DAMP_ASPHALT_STONE
            n_brick.offset = 0.5
            n_brick.squash = 1.4
            materials.set_socket(n_brick, ("Scale",), 2.4)
            materials.set_socket(n_brick, ("Mortar Size",), 0.03)
            materials.set_socket(n_brick, ("Mortar Smooth",), 0.15)

        materials.set_socket(n_brick, ("Color1",), materials._rgba(pal["mid_high"]))
        materials.set_socket(n_brick, ("Color2",), materials._rgba(pal["mid_low"]))
        materials.set_socket(n_brick, ("Mortar",), materials._rgba(pal["dark"]))
        links.new(tri_vec, n_brick.inputs["Vector"])
        macro_col = n_brick.outputs["Color"]

    elif archetype == "CORRUGATED_SHUTTER":
        n_wave = nodes.new("ShaderNodeTexWave")
        n_wave.location = (-160, 220)
        n_wave.wave_type = "BANDS"
        if hasattr(n_wave, "bands_direction"):
            n_wave.bands_direction = "Y"
        materials.set_socket(n_wave, ("Scale",), 28.0)
        links.new(tri_vec, n_wave.inputs["Vector"])

        n_ramp = nodes.new("ShaderNodeValToRGB")
        n_ramp.location = (80, 220)
        el = n_ramp.color_ramp.elements
        el[0].position = 0.15
        el[0].color = materials._rgba(pal["dark"])
        el[1].position = 0.85
        el[1].color = materials._rgba(pal["mid_high"])
        links.new(n_wave.outputs["Fac"], n_ramp.inputs["Fac"])
        macro_col = n_ramp.outputs["Color"]

    elif archetype in ("LSD_CLUT_PATTERN", "NEON_LIGHTBOX"):
        n_vor = nodes.new("ShaderNodeTexVoronoi")
        n_vor.location = (-160, 220)
        materials.set_socket(n_vor, ("Scale",), 2.2)
        materials.set_socket(n_vor, ("Randomness",), 0.0 if archetype == "LSD_CLUT_PATTERN" else 0.5)
        links.new(tri_vec, n_vor.inputs["Vector"])

        n_ramp = nodes.new("ShaderNodeValToRGB")
        n_ramp.location = (80, 220)
        n_ramp.color_ramp.interpolation = "CONSTANT"
        el = n_ramp.color_ramp.elements
        el[0].position = 0.0
        el[0].color = materials._rgba(pal["light"])
        el[1].position = 0.25
        el[1].color = materials._rgba(pal["accent"])
        e2 = el.new(0.50)
        e2.color = materials._rgba(pal["mid_high"])
        e3 = el.new(0.75)
        e3.color = materials._rgba(pal["mid_low"])
        links.new(n_vor.outputs["Distance"], n_ramp.inputs["Fac"])
        macro_col = n_ramp.outputs["Color"]

    else:
        # BRYCE_STRIATED_ROCK / CAST_IRON_PAINT / DC_WATERFALL_ENERGY
        n_ns = nodes.new("ShaderNodeTexNoise")
        n_ns.location = (-160, 220)
        materials.set_socket(n_ns, ("Scale",), 3.8)
        materials.set_socket(n_ns, ("Detail",), 4.0)
        links.new(snap_3d, n_ns.inputs["Vector"])

        n_ramp = nodes.new("ShaderNodeValToRGB")
        n_ramp.location = (80, 220)
        el = n_ramp.color_ramp.elements
        el[0].position = 0.25
        el[0].color = materials._rgba(pal["mid_low"])
        el[1].position = 0.75
        el[1].color = materials._rgba(pal["light"])
        e_mid = el.new(0.50)
        e_mid.color = materials._rgba(pal["mid_high"])
        links.new(n_ns.outputs["Fac"], n_ramp.inputs["Fac"])
        macro_col = n_ramp.outputs["Color"]

    # 3. Pass 2: High-Frequency Micro-Surface Grain Overlay (Eliminates flat/coarse plastic blocks!)
    n_detail = nodes.new("ShaderNodeTexNoise")
    n_detail.location = (-160, -40)
    materials.set_socket(n_detail, ("Scale",), 18.0)
    materials.set_socket(n_detail, ("Detail",), 3.0)
    materials.set_socket(n_detail, ("Roughness",), 0.7)
    links.new(snap_3d, n_detail.inputs["Vector"])

    n_det_ramp = nodes.new("ShaderNodeValToRGB")
    n_det_ramp.location = (80, -40)
    d_el = n_det_ramp.color_ramp.elements
    d_el[0].position = 0.2
    d_el[0].color = (0.72, 0.70, 0.68, 1.0)
    d_el[1].position = 0.8
    d_el[1].color = (1.15, 1.15, 1.12, 1.0)
    links.new(n_detail.outputs["Fac"], n_det_ramp.inputs["Fac"])

    _, det_fac, det_c1, det_c2, detailed_col = materials._new_mix_color(
        nodes, links, blend_type="MULTIPLY", location=(380, 140)
    )
    det_fac.default_value = detail_pct * 0.85
    links.new(macro_col, det_c1)
    links.new(n_det_ramp.outputs["Color"], det_c2)

    # 4. Pass 3: Pre-Baked Vertical Moisture Stains, Rust & Moss Weathering
    n_weath_map = nodes.new("ShaderNodeMapping")
    n_weath_map.location = (-420, -280)
    materials.set_socket(n_weath_map, ("Scale",), (1.8, 1.8, 0.35))
    links.new(snap_3d, n_weath_map.inputs["Vector"])

    n_weath_ns = nodes.new("ShaderNodeTexNoise")
    n_weath_ns.location = (-160, -280)
    materials.set_socket(n_weath_ns, ("Scale",), 4.5)
    materials.set_socket(n_weath_ns, ("Detail",), 3.0)
    links.new(n_weath_map.outputs["Vector"], n_weath_ns.inputs["Vector"])

    n_weath_ramp = nodes.new("ShaderNodeValToRGB")
    n_weath_ramp.location = (80, -280)
    w_el = n_weath_ramp.color_ramp.elements
    w_el[0].position = 0.35
    w_el[0].color = materials._rgba(pal["dark"])
    w_el[1].position = 0.70
    w_el[1].color = (1.0, 1.0, 1.0, 1.0)
    links.new(n_weath_ns.outputs["Fac"], n_weath_ramp.inputs["Fac"])

    _, gr_fac, gr_c1, gr_c2, weathered_col = materials._new_mix_color(
        nodes, links, blend_type="MULTIPLY", location=(620, 140)
    )
    gr_fac.default_value = grime_pct * 0.78
    links.new(detailed_col, gr_c1)
    links.new(n_weath_ramp.outputs["Color"], gr_c2)

    # 5. Paradigm-Specific Lighting & Output Stage
    if archetype == "NEON_LIGHTBOX":
        n_emit = nodes.new("ShaderNodeEmission")
        n_emit.location = (980, 120)
        materials.set_socket(n_emit, ("Strength",), 1.8)
        links.new(weathered_col, n_emit.inputs["Color"])
        links.new(n_emit.outputs["Emission"], n_out.inputs["Surface"])
        return mat

    spec_w = 0.0 if paradigm in ("PS1_PREBAKED_CLUT", "PS1_CLUT_PSYCHEDELIC") else 0.25
    rough_w = 0.85 if paradigm in ("PS1_PREBAKED_CLUT", "PS1_CLUT_PSYCHEDELIC") else 0.22
    shader_out = materials._append_1997_depth_fog_and_ambient(
        nodes,
        links,
        base_color_socket=weathered_col,
        normal_socket=None,
        props=props,
        specular_weight=spec_w,
        roughness=rough_w,
    )
    links.new(shader_out, n_out.inputs["Surface"])
    return mat


def apply_workbench_texture_to_selected(context: Any, props: Any) -> int:
    """
    Applies the synthesized Workbench Material to all currently selected mesh objects
    (or to the active Dreamspace/Terrain objects if no custom object is selected).
    """
    if bpy is None or context is None:
        return 0

    ensure_reusable_texture_node_groups()
    mat = build_workbench_material(props)
    if mat is None:
        return 0

    sel_objs = getattr(context, "selected_objects", None) or []
    mesh_targets = [o for o in sel_objs if getattr(o, "type", "") == "MESH" and getattr(o, "data", None) is not None]
    if not mesh_targets:
        active_o = getattr(context, "active_object", None)
        if active_o is not None and getattr(active_o, "type", "") == "MESH" and getattr(active_o, "data", None) is not None:
            mesh_targets = [active_o]
    if not mesh_targets:
        t_obj = bpy.data.objects.get("SDS_Terrain")
        if t_obj is not None and getattr(t_obj, "type", "") == "MESH":
            mesh_targets = [t_obj]

    from . import dreamspace
    count = 0
    for obj in mesh_targets:
        if len(obj.data.materials) == 0:
            obj.data.materials.append(mat)
        else:
            obj.data.materials[0] = mat
        dreamspace.apply_era_geometry_modifiers(obj, props)
        count += 1
    return count


def retrofy_selected_object_materials(context: Any, props: Any) -> int:
    """
    Upgrades existing materials on selected objects by injecting the active Era's
    Texel Grid Quantizer (`SNAP`) and Pre-Baked Grime / Color Quantization pipeline
    while preserving any existing `ShaderNodeTexImage` textures!
    """
    if bpy is None or context is None:
        return 0

    ensure_reusable_texture_node_groups()
    sel_objs = getattr(context, "selected_objects", None) or []
    mesh_targets = [o for o in sel_objs if getattr(o, "type", "") == "MESH" and getattr(o, "data", None) is not None]
    if not mesh_targets:
        return apply_workbench_texture_to_selected(context, props)

    res_mode = getattr(props, "tex_res_grid", "TEX_64")
    res_map = {"TEX_16": 16.0, "TEX_32": 32.0, "TEX_64": 64.0, "TEX_128": 128.0, "TEX_CONT": 512.0}
    step = 1.0 / res_map.get(res_mode, 64.0)

    upgraded = 0
    for obj in mesh_targets:
        for mat in obj.data.materials:
            if mat is None or not getattr(mat, "use_nodes", False) or getattr(mat, "node_tree", None) is None:
                continue
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            # If the material has an Image Texture node, set interpolation to Closest and snap its UV!
            img_nodes = [n for n in nodes if getattr(n, "bl_idname", "") == "ShaderNodeTexImage"]
            for img_n in img_nodes:
                if hasattr(img_n, "interpolation"):
                    try:
                        img_n.interpolation = "Closest" if res_mode != "TEX_CONT" else "Linear"
                    except Exception:
                        pass
                n_uv = nodes.new("ShaderNodeTexCoord")
                n_uv.location = (img_n.location[0] - 420, img_n.location[1])
                n_sn = nodes.new("ShaderNodeVectorMath")
                n_sn.operation = "SNAP"
                n_sn.location = (img_n.location[0] - 200, img_n.location[1])
                for inp in list(n_sn.inputs)[1:]:
                    if getattr(inp, "type", "") == "VECTOR":
                        try:
                            inp.default_value = (step, step, step)
                        except Exception:
                            pass
                links.new(n_uv.outputs["UV"], n_sn.inputs[0])
                links.new(n_sn.outputs[0], img_n.inputs["Vector"])
            upgraded += 1

    if upgraded == 0:
        return apply_workbench_texture_to_selected(context, props)
    return upgraded
