# SPDX-License-Identifier: GPL-3.0-or-later
"""
03 — Material Lab: 1997 Non-PBR Illumination & Bryce Deep Texture Editor (DTE) Simulator (v2.1).
CRITICAL FIX:
- `_new_mix_color` now selects the `RGBA` (`NodeSocketColor`) sockets (`inputs[6]`, `inputs[7]`,
  `outputs[2]`) on `ShaderNodeMix` instead of looking up `inputs["A"]` / `inputs["B"]` by name
  (which in Blender 3.4 - 5.1+ returns `inputs[2]`/`inputs[3]` `NodeSocketFloat` and raises
  `TypeError: NodeSocketFloat.default_value expected a float type, not tuple`).
"""

from typing import Any, Sequence, Tuple

try:
    import bpy
except ImportError:
    bpy = None


def set_socket(node: Any, socket_names: Sequence[str], value: Any) -> bool:
    if node is None or not hasattr(node, "inputs"):
        return False
    for name in socket_names:
        if name in node.inputs:
            try:
                node.inputs[name].default_value = value
                return True
            except Exception:
                continue
    return False


def _rgba(rgb: Sequence[float], alpha: float = 1.0) -> Tuple[float, float, float, float]:
    return (float(rgb[0]), float(rgb[1]), float(rgb[2]), float(alpha))


def _scale_rgb(rgb: Sequence[float], factor: float) -> Tuple[float, float, float, float]:
    return (
        min(1.0, max(0.0, float(rgb[0]) * factor)),
        min(1.0, max(0.0, float(rgb[1]) * factor)),
        min(1.0, max(0.0, float(rgb[2]) * factor)),
        1.0,
    )


def _get_or_create_material(name: str) -> Tuple[Any, Any, Any]:
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    return mat, nt.nodes, nt.links


def _new_mix_color(
    nodes: Any,
    links: Any,
    location: Tuple[float, float] = (0.0, 0.0),
    blend_type: str = "MIX",
) -> Tuple[Any, Any, Any, Any, Any]:
    """
    Cross-version color mix node builder supporting both `ShaderNodeMix` (Blender 3.4 - 5.1+)
    and legacy `ShaderNodeMixRGB`.
    IMPORTANT: On `ShaderNodeMix`, `inputs["A"]` and `inputs["B"]` return `inputs[2]` and `inputs[3]`
    which are `NodeSocketFloat`! The `RGBA` (`NodeSocketColor`) sockets are at `inputs[6]`, `inputs[7]`,
    and `outputs[2]` (or filtered by `s.type == 'RGBA'`).
    """
    try:
        n = nodes.new("ShaderNodeMix")
        n.data_type = "RGBA"
        n.blend_type = blend_type
        n.location = location
        rgba_in = [s for s in n.inputs if getattr(s, "type", "") == "RGBA"]
        rgba_out = [s for s in n.outputs if getattr(s, "type", "") == "RGBA"]
        if len(rgba_in) >= 2 and len(rgba_out) >= 1:
            return (n, n.inputs[0], rgba_in[0], rgba_in[1], rgba_out[0])
        if len(n.inputs) >= 8 and len(n.outputs) >= 3:
            return (n, n.inputs[0], n.inputs[6], n.inputs[7], n.outputs[2])
        return (n, n.inputs["Factor"], n.inputs["A"], n.inputs["B"], n.outputs["Result"])
    except Exception:
        n = nodes.new("ShaderNodeMixRGB")
        n.blend_type = blend_type
        n.location = location
        return (
            n,
            n.inputs["Fac"],
            n.inputs["Color1"],
            n.inputs["Color2"],
            n.outputs["Color"],
        )


def _append_1997_depth_fog_and_ambient(
    nodes: Any,
    links: Any,
    base_color_socket: Any,
    normal_socket: Any,
    props: Any,
    specular_weight: float = 0.12,
    roughness: float = 0.18,
    extra_emit_factor_socket: Any = None,
) -> Any:
    fog_pct = max(0.0, min(100.0, float(getattr(props, "far_fog", 28.0)))) / 100.0
    amb_pct = max(0.0, min(100.0, float(getattr(props, "ambient_strength", 22.0)))) / 100.0
    hor_c = getattr(props, "sky_horizon_color", (0.86, 0.94, 1.00))
    era = getattr(props, "era_pipeline", "BRYCE_1997")
    shade_mode = getattr(props, "shading_interpolation", "PHONG_SMOOTH")

    n_cam = nodes.new("ShaderNodeCameraData")
    n_cam.location = (320, -420)

    n_fog_sub = nodes.new("ShaderNodeMath")
    n_fog_sub.operation = "SUBTRACT"
    n_fog_sub.location = (500, -420)
    n_fog_sub.inputs[1].default_value = 15.0

    n_fog_div = nodes.new("ShaderNodeMath")
    n_fog_div.operation = "DIVIDE"
    n_fog_div.location = (660, -420)
    fog_span = max(20.0, 110.0 * (1.15 - fog_pct * 0.90))
    n_fog_div.inputs[1].default_value = fog_span

    n_fog_mul = nodes.new("ShaderNodeMath")
    n_fog_mul.operation = "MULTIPLY"
    n_fog_mul.location = (820, -420)
    n_fog_mul.inputs[1].default_value = fog_pct * 0.85

    n_fog_clamp = nodes.new("ShaderNodeValToRGB")
    n_fog_clamp.location = (980, -420)
    n_fog_clamp.color_ramp.elements[0].position = 0.0
    n_fog_clamp.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    n_fog_clamp.color_ramp.elements[1].position = 1.0
    n_fog_clamp.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)

    links.new(n_cam.outputs["View Distance"], n_fog_sub.inputs[0])
    links.new(n_fog_sub.outputs["Value"], n_fog_div.inputs[0])
    links.new(n_fog_div.outputs["Value"], n_fog_mul.inputs[0])
    fog_val_out = n_fog_mul.outputs["Value"]

    if era == "PS1_1998_LSD" or shade_mode == "FLAT_FACETED":
        # =======================================================================
        # AUTHENTIC PS1 UNLIT + GTE FLAT POLYGON SHADING PIPELINE (`POLY_FT3`):
        # - Zero cast shadows and zero Lambertian sky-tint washout!
        # - Ground polygons (`TrueNormal.Z > 0.75`) render at 100% full-bright (`1.0`)
        #   so ground tiles match `e53fb9d1...jpg` & `image_33a178.png` with pure vibrance.
        # - Vertical/angled 3D polygons (turtle carapace, kimono woman sleeves, house walls)
        #   are modulated by stepped GTE flat polygon-normal dot product (`[0.64 .. 1.06]`),
        #   giving every flat facet a crisp, distinct polygon shade!
        # =======================================================================
        true_norm = None
        try:
            n_tgeom = nodes.new("ShaderNodeNewGeometry")
            n_tgeom.location = (320, 260)
            true_norm = (n_tgeom.outputs["True Normal"] if "True Normal" in n_tgeom.outputs else n_tgeom.outputs[0])

            n_dot = nodes.new("ShaderNodeVectorMath")
            n_dot.operation = "DOT_PRODUCT"
            n_dot.location = (500, 260)
            if len(n_dot.inputs) > 1:
                n_dot.inputs[1].default_value = (0.42, -0.52, 0.74)
            links.new(true_norm, n_dot.inputs[0])
            dot_out = (n_dot.outputs["Value"] if "Value" in n_dot.outputs else n_dot.outputs[0])

            # Map dot product [-1, 1] -> [0.64, 1.06] and quantize to 6 GTE brightness steps
            n_sh_madd = nodes.new("ShaderNodeMath")
            n_sh_madd.operation = "MULTIPLY_ADD"
            n_sh_madd.location = (660, 260)
            n_sh_madd.inputs[1].default_value = 0.21
            n_sh_madd.inputs[2].default_value = 0.85
            links.new(dot_out, n_sh_madd.inputs[0])

            n_sh_snap = nodes.new("ShaderNodeMath")
            n_sh_snap.operation = "SNAP"
            n_sh_snap.location = (820, 260)
            n_sh_snap.inputs[1].default_value = 0.07
            links.new(n_sh_madd.outputs["Value"], n_sh_snap.inputs[0])

            # Keep horizontal ground polygons (`abs(N_z) > 0.78`) near 1.0 full-bright
            n_sep_n = nodes.new("ShaderNodeSeparateXYZ")
            n_sep_n.location = (500, 420)
            links.new(true_norm, n_sep_n.inputs["Vector"])

            n_gt_z = nodes.new("ShaderNodeMath")
            n_gt_z.operation = "GREATER_THAN"
            n_gt_z.location = (660, 420)
            n_gt_z.inputs[1].default_value = 0.78
            links.new(n_sep_n.outputs["Z"], n_gt_z.inputs[0])

            n_max_sh = nodes.new("ShaderNodeMath")
            n_max_sh.operation = "MAXIMUM"
            n_max_sh.location = (960, 320)
            links.new(n_sh_snap.outputs["Value"], n_max_sh.inputs[0])
            links.new(n_gt_z.outputs["Value"], n_max_sh.inputs[1])

            n_comb_sh = nodes.new("ShaderNodeCombineXYZ")
            n_comb_sh.location = (1100, 320)
            links.new(n_max_sh.outputs["Value"], n_comb_sh.inputs[0])
            links.new(n_max_sh.outputs["Value"], n_comb_sh.inputs[1])
            links.new(n_max_sh.outputs["Value"], n_comb_sh.inputs[2])

            _, m_sfac, m_sc1, m_sc2, shaded_tex_col = _new_mix_color(
                nodes, links, blend_type="MULTIPLY", location=(1120, 160)
            )
            m_sfac.default_value = 1.0
            links.new(base_color_socket, m_sc1)
            links.new(n_comb_sh.outputs["Vector"], m_sc2)
        except Exception:
            shaded_tex_col = base_color_socket

        # Step distance fog & mix with horizon fog color
        try:
            n_fog_snap = nodes.new("ShaderNodeMath")
            n_fog_snap.operation = "SNAP"
            n_fog_snap.location = (900, -420)
            n_fog_snap.inputs[1].default_value = 1.0 / 16.0
            links.new(fog_val_out, n_fog_snap.inputs[0])
            fog_val_out = n_fog_snap.outputs["Value"]
        except Exception:
            pass
        links.new(fog_val_out, n_fog_clamp.inputs["Fac"])

        _, fog_fac, fog_c1, fog_c2, fogged_col_out = _new_mix_color(nodes, links, location=(1280, 140))
        fog_c2.default_value = _rgba(hor_c)
        links.new(n_fog_clamp.outputs["Color"], fog_fac)
        links.new(shaded_tex_col, fog_c1)

        # Clean 15-bit High Color (5-5-5 RGB, 32 steps per channel) quantization
        try:
            q_inc = 1.0 / 32.0
            n_qsnap = nodes.new("ShaderNodeVectorMath")
            n_qsnap.operation = "SNAP"
            n_qsnap.location = (1440, 140)
            for inp in list(n_qsnap.inputs)[1:]:
                if getattr(inp, "type", "") == "VECTOR":
                    try:
                        inp.default_value = (q_inc, q_inc, q_inc)
                    except Exception:
                        pass
            links.new(fogged_col_out, n_qsnap.inputs[0])
            fogged_col_out = n_qsnap.outputs[0]
        except Exception:
            pass

        # PS1 Atmospheric Shading: Local Light Diffuse (0.78) + Base Ambient Fill (0.22)
        # Allows warm street lanterns & fluorescent tubes to cast atmospheric light pools & shadows!
        n_diff_ps1 = nodes.new("ShaderNodeBsdfDiffuse")
        n_diff_ps1.location = (1580, 240)
        set_socket(n_diff_ps1, ("Roughness",), 0.5)
        links.new(fogged_col_out, n_diff_ps1.inputs["Color"])
        if true_norm is not None and "Normal" in n_diff_ps1.inputs:
            links.new(true_norm, n_diff_ps1.inputs["Normal"])

        n_emit_ps1 = nodes.new("ShaderNodeEmission")
        n_emit_ps1.location = (1580, 60)
        set_socket(n_emit_ps1, ("Strength",), 0.22)
        links.new(fogged_col_out, n_emit_ps1.inputs["Color"])

        n_add_ps1 = nodes.new("ShaderNodeAddShader")
        n_add_ps1.location = (1760, 140)
        links.new(n_diff_ps1.outputs["BSDF"], n_add_ps1.inputs[0])
        links.new(n_emit_ps1.outputs["Emission"], n_add_ps1.inputs[1])
        return n_add_ps1.outputs["Shader"]

    # =======================================================================
    # CATEGORY I (1997 Bryce/POV-Ray), III (Dreamcast PowerVR2) & IV (PS2 EE/GS)
    # =======================================================================
    if era in ("DC_1999_POWERVR2", "PS2_2000_EE") or shade_mode == "GOURAUD_VERTEX":
        roughness = max(0.28, roughness)
        specular_weight = min(0.35, specular_weight)

    links.new(fog_val_out, n_fog_clamp.inputs["Fac"])
    _, fog_fac, fog_c1, fog_c2, fogged_col_out = _new_mix_color(nodes, links, location=(740, 140))
    fog_c2.default_value = _rgba(hor_c)
    links.new(n_fog_clamp.outputs["Color"], fog_fac)
    links.new(base_color_socket, fog_c1)

    n_diff = nodes.new("ShaderNodeBsdfDiffuse")
    n_diff.location = (1020, 220)
    set_socket(n_diff, ("Roughness",), 0.0)
    links.new(fogged_col_out, n_diff.inputs["Color"])
    if normal_socket is not None and "Normal" in n_diff.inputs:
        links.new(normal_socket, n_diff.inputs["Normal"])

    n_emit = nodes.new("ShaderNodeEmission")
    n_emit.location = (1020, 40)
    links.new(fogged_col_out, n_emit.inputs["Color"])

    if extra_emit_factor_socket is not None:
        n_amb_add = nodes.new("ShaderNodeMath")
        n_amb_add.operation = "ADD"
        n_amb_add.location = (840, -60)
        n_amb_add.inputs[0].default_value = amb_pct * 0.65
        links.new(extra_emit_factor_socket, n_amb_add.inputs[1])
        links.new(n_amb_add.outputs["Value"], n_emit.inputs["Strength"])
    else:
        set_socket(n_emit, ("Strength",), amb_pct * 0.65)

    n_add_amb = nodes.new("ShaderNodeAddShader")
    n_add_amb.location = (1240, 140)
    links.new(n_diff.outputs["BSDF"], n_add_amb.inputs[0])
    links.new(n_emit.outputs["Emission"], n_add_amb.inputs[1])

    vintage_spec = bool(getattr(props, "vintage_specular", True))
    if not vintage_spec or specular_weight <= 0.005:
        return n_add_amb.outputs["Shader"]

    n_gloss = nodes.new("ShaderNodeBsdfGlossy")
    n_gloss.location = (1020, -140)
    set_socket(n_gloss, ("Color",), (1.0, 0.98, 0.92, 1.0))
    set_socket(n_gloss, ("Roughness",), max(0.04, roughness * 0.65))
    if normal_socket is not None and "Normal" in n_gloss.inputs:
        links.new(normal_socket, n_gloss.inputs["Normal"])

    n_mix_spec = nodes.new("ShaderNodeMixShader")
    n_mix_spec.location = (1460, 100)
    n_mix_spec.inputs["Fac"].default_value = min(0.35, specular_weight)
    links.new(n_add_amb.outputs["Shader"], n_mix_spec.inputs[1])
    links.new(n_gloss.outputs["BSDF"], n_mix_spec.inputs[2])
    return n_mix_spec.outputs["Shader"]


def build_terrain_material(props: Any) -> Any:
    if bpy is None:
        return None

    mismatch = getattr(props, "texture_mismatch_mode", "SEMANTIC")
    if mismatch == "CROSS_MISMATCH":
        # b.txt Section 3.3: Mountain terrain gets repeating building window facades!
        return build_dream_facade_material(props, 0)
    if mismatch == "LOCAL_MUTATION":
        return build_dream_mutated_material(props, 0)

    mismatch = getattr(props, "texture_mismatch_mode", "SEMANTIC")
    if mismatch == "CROSS_MISMATCH":
        # b.txt Section 3.3: Mountain terrain gets repeating building window facades!
        return build_dream_facade_material(props, 0)
    if mismatch == "LOCAL_MUTATION":
        return build_dream_mutated_material(props, 0)

    mode = getattr(props, "terrain_mode", "FRACTAL_MOUNTAINS")
    preset_id = getattr(props, "world_preset", "CLASSIC_BRYCE")
    era = getattr(props, "era_pipeline", "BRYCE_1997")
    if mode == "CHECKER_PLANE":
        if preset_id == "RAYTRACED_GEOMETRY":
            return build_checker_material(props)
        if preset_id == "SUNSET_MONOLITH":
            return build_lichen_desert_material(props)
        if preset_id == "LSD_DREAM_EMULATOR":
            return build_ps1_bmc_grass_material(props)
        if preset_id in ("LSD_VIOLENCE_TOWERS", "PS1_AFFINE_DUNGEON"):
            return build_ps1_bmc_wood_floor_material(props)
        if preset_id == "IMPOSSIBLE_GEOGRAPHY":
            return build_cyber_grid_ground_material(props)
        return build_cloud_ground_material(props)
    if preset_id == "LSD_PSYCHEDELIC_TURTLE":
        return build_ps1_lsd_bullseye_tile_material(props, is_turtle=False)
    if preset_id == "LSD_KANJI_EYE_GIANT":
        return build_ps1_lsd_kanji_giant_material(props, role="GREEN_BLUE_TILE")
    if preset_id == "LSD_KYOTO_KIMONO_NIGHT":
        return build_ps1_lsd_kyoto_night_material(props, role="SAND_STREET")
    if preset_id == "LSD_GRAY_MAN_PLAZA":
        return build_ps1_lsd_purple_plaza_material(props, role="FLOOR")
    if preset_id == "LSD_FLESH_TUNNEL":
        return build_ps1_lsd_flesh_tunnel_material(props, is_wall_stretched=False)
    if preset_id == "LSD_GRAFFITI_CORRIDOR":
        return build_ps1_lsd_polkadot_floor_material(props)
    if era == "PS1_1998_LSD":
        return build_ps1_lowpoly_terrain_material(props)

    mat, nodes, links = _get_or_create_material("SDS_Mat_Terrain")

    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (1680, 100)

    low_c = getattr(props, "terrain_low_color", (0.02, 0.30, 0.02))
    mid_c = getattr(props, "terrain_mid_color", (0.54, 0.18, 0.02))
    high_c = getattr(props, "terrain_high_color", (1.00, 0.96, 0.76))
    sharp_pct = max(10.0, min(99.0, float(getattr(props, "color_contrast_sharpness", 90.0)))) / 100.0
    half_band = max(0.012, (1.0 - sharp_pct) * 0.20)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-1100, 0)
    n_geom = nodes.new("ShaderNodeNewGeometry")
    n_geom.location = (-1100, -280)

    n_sep_pos = nodes.new("ShaderNodeSeparateXYZ")
    n_sep_pos.location = (-860, 60)
    n_sep_norm = nodes.new("ShaderNodeSeparateXYZ")
    n_sep_norm.location = (-860, -280)

    relief = max(15.0, float(getattr(props, "terrain_relief", 64.0)))
    max_h = max(2.0, 12.0 * (relief / 100.0))
    n_alt_norm = nodes.new("ShaderNodeMath")
    n_alt_norm.operation = "DIVIDE"
    n_alt_norm.location = (-640, 60)
    n_alt_norm.inputs[1].default_value = max_h

    # --- DTE COMPONENT 1: 3-Color Mottled Lowland / Shoreline ---
    n_grass_noise = nodes.new("ShaderNodeTexNoise")
    n_grass_noise.location = (-640, 460)
    set_socket(n_grass_noise, ("Scale",), 6.8)
    set_socket(n_grass_noise, ("Detail",), 4.0)

    n_grass_ramp = nodes.new("ShaderNodeValToRGB")
    n_grass_ramp.location = (-360, 460)
    g_el = n_grass_ramp.color_ramp.elements
    g_el[0].position = 0.34
    g_el[0].color = _scale_rgb(low_c, 0.20)
    g_el[1].position = 0.68
    g_el[1].color = _scale_rgb(low_c, 1.45)
    g_mid = g_el.new(0.50)
    g_mid.color = _rgba(low_c)

    # --- DTE COMPONENT 2: Striated Canyon Rock OR Cracked Voronoi Basalt (`ISOLATED_PEAKS`) ---
    n_rock_wave = nodes.new("ShaderNodeTexWave")
    n_rock_wave.location = (-640, 220)
    n_rock_wave.wave_type = "BANDS"
    if hasattr(n_rock_wave, "bands_direction"):
        # Vertical granite striations for KARST_DOMES (`9lFBJ8s...jpg`), horizontal for Bryce mountains
        n_rock_wave.bands_direction = "X" if mode == "KARST_DOMES" else "Z"
    set_socket(n_rock_wave, ("Scale",), 16.0 if mode in ("KARST_DOMES", "ISOLATED_PEAKS") else 13.0)
    set_socket(n_rock_wave, ("Distortion",), 8.5 if mode == "ISOLATED_PEAKS" else 6.5)
    set_socket(n_rock_wave, ("Detail",), 4.0)

    n_rock_ramp = nodes.new("ShaderNodeValToRGB")
    n_rock_ramp.location = (-360, 220)
    r_el = n_rock_ramp.color_ramp.elements
    r_el[0].position = 0.30
    r_el[0].color = _scale_rgb(mid_c, 0.14)
    r_el[1].position = 0.70
    r_el[1].color = _scale_rgb(mid_c, 1.45)
    r_mid = r_el.new(0.50)
    r_mid.color = _rgba(mid_c)

    # --- DTE FILTER 1: Foothill Green -> Striated Rock ---
    n_mask_noise = nodes.new("ShaderNodeTexNoise")
    n_mask_noise.location = (-640, -120)
    set_socket(n_mask_noise, ("Scale",), 2.6)
    set_socket(n_mask_noise, ("Detail",), 3.0)

    n_steep = nodes.new("ShaderNodeMath")
    n_steep.operation = "SUBTRACT"
    n_steep.location = (-640, -300)
    n_steep.inputs[0].default_value = 1.0

    n_rock_score1 = nodes.new("ShaderNodeMath")
    n_rock_score1.operation = "ADD"
    n_rock_score1.location = (-400, -80)

    n_rock_score2 = nodes.new("ShaderNodeMath")
    n_rock_score2.operation = "ADD"
    n_rock_score2.location = (-220, -80)

    n_rock_mask = nodes.new("ShaderNodeValToRGB")
    n_rock_mask.location = (-40, -80)
    rm_el = n_rock_mask.color_ramp.elements
    thresh_r = 0.45 if mode in ("KARST_DOMES", "ISOLATED_PEAKS") else 0.60
    rm_el[0].position = max(0.05, thresh_r - half_band)
    rm_el[0].color = (0.0, 0.0, 0.0, 1.0)
    rm_el[1].position = min(0.95, thresh_r + half_band)
    rm_el[1].color = (1.0, 1.0, 1.0, 1.0)

    _, gr_fac, gr_c1, gr_c2, gr_out = _new_mix_color(nodes, links, location=(240, 260))

    # --- DTE FILTER 2: Stark Patchy Bryce Snow / Mineral Highlight Mask ---
    n_snow_noise = nodes.new("ShaderNodeTexNoise")
    n_snow_noise.location = (-640, -480)
    set_socket(n_snow_noise, ("Scale",), 2.1)
    set_socket(n_snow_noise, ("Detail",), 3.5)
    set_socket(n_snow_noise, ("Distortion",), 0.6)

    n_snow_add1 = nodes.new("ShaderNodeMath")
    n_snow_add1.operation = "ADD"
    n_snow_add1.location = (-380, -380)

    n_snow_sub = nodes.new("ShaderNodeMath")
    n_snow_sub.operation = "SUBTRACT"
    n_snow_sub.location = (-200, -380)

    n_snow_mask = nodes.new("ShaderNodeValToRGB")
    n_snow_mask.location = (20, -380)
    sm_el = n_snow_mask.color_ramp.elements
    thresh_s = 0.72 if mode == "KARST_DOMES" else 0.56
    sm_el[0].position = max(0.05, thresh_s - half_band * 0.75)
    sm_el[0].color = (0.0, 0.0, 0.0, 1.0)
    sm_el[1].position = min(0.95, thresh_s + half_band * 0.75)
    sm_el[1].color = (1.0, 1.0, 1.0, 1.0)

    _, sn_fac, sn_c1, sn_c2, sn_out = _new_mix_color(nodes, links, location=(480, 160))
    sn_c2.default_value = _rgba(high_c)

    n_snow_glow = nodes.new("ShaderNodeMath")
    n_snow_glow.operation = "MULTIPLY"
    n_snow_glow.location = (480, -120)
    n_snow_glow.inputs[1].default_value = 0.05 if mode == "KARST_DOMES" else 0.25

    n_bump = nodes.new("ShaderNodeBump")
    n_bump.location = (480, -280)
    set_socket(n_bump, ("Strength",), 0.50)

    links.new(n_coord.outputs["Object"], n_sep_pos.inputs["Vector"])
    links.new(n_coord.outputs["Object"], n_grass_noise.inputs["Vector"])
    links.new(n_coord.outputs["Object"], n_rock_wave.inputs["Vector"])
    links.new(n_coord.outputs["Object"], n_mask_noise.inputs["Vector"])
    links.new(n_coord.outputs["Object"], n_snow_noise.inputs["Vector"])
    links.new(n_geom.outputs["Normal"], n_sep_norm.inputs["Vector"])

    links.new(n_sep_pos.outputs["Z"], n_alt_norm.inputs[0])
    links.new(n_sep_norm.outputs["Z"], n_steep.inputs[1])

    links.new(n_grass_noise.outputs["Fac"], n_grass_ramp.inputs["Fac"])
    links.new(n_rock_wave.outputs["Fac"], n_rock_ramp.inputs["Fac"])

    links.new(n_alt_norm.outputs["Value"], n_rock_score1.inputs[0])
    links.new(n_steep.outputs["Value"], n_rock_score1.inputs[1])
    links.new(n_rock_score1.outputs["Value"], n_rock_score2.inputs[0])
    links.new(n_mask_noise.outputs["Fac"], n_rock_score2.inputs[1])
    links.new(n_rock_score2.outputs["Value"], n_rock_mask.inputs["Fac"])

    links.new(n_rock_mask.outputs["Color"], gr_fac)
    links.new(n_grass_ramp.outputs["Color"], gr_c1)
    links.new(n_rock_ramp.outputs["Color"], gr_c2)

    links.new(n_alt_norm.outputs["Value"], n_snow_add1.inputs[0])
    links.new(n_snow_noise.outputs["Fac"], n_snow_add1.inputs[1])
    links.new(n_snow_add1.outputs["Value"], n_snow_sub.inputs[0])
    links.new(n_steep.outputs["Value"], n_snow_sub.inputs[1])
    links.new(n_snow_sub.outputs["Value"], n_snow_mask.inputs["Fac"])

    links.new(n_snow_mask.outputs["Color"], sn_fac)
    links.new(gr_out, sn_c1)

    links.new(n_snow_mask.outputs["Color"], n_snow_glow.inputs[0])
    links.new(n_rock_wave.outputs["Fac"], n_bump.inputs["Height"])

    shader_out = _append_1997_depth_fog_and_ambient(
        nodes,
        links,
        base_color_socket=sn_out,
        normal_socket=n_bump.outputs["Normal"],
        props=props,
        specular_weight=0.08 if getattr(props, "vintage_specular", True) else 0.02,
        roughness=0.22,
        extra_emit_factor_socket=n_snow_glow.outputs["Value"],
    )
    links.new(shader_out, n_out.inputs["Surface"])

    return mat


def build_lichen_desert_material(props: Any) -> Any:
    """
    Ref Image 2 (`qsvqqrL...jpg`): Infinite sunset desert covered in sharp green moss patches
    over bumped terracotta/sand earth.
    """
    if bpy is None:
        return None
    mat, nodes, links = _get_or_create_material("SDS_Mat_Terrain")
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (1600, 100)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-620, 0)

    n_noise = nodes.new("ShaderNodeTexNoise")
    n_noise.location = (-360, 120)
    set_socket(n_noise, ("Scale",), 14.0)
    set_socket(n_noise, ("Detail",), 5.0)
    set_socket(n_noise, ("Distortion",), 0.8)

    n_ramp = nodes.new("ShaderNodeValToRGB")
    n_ramp.location = (-80, 120)
    elems = n_ramp.color_ramp.elements
    elems[0].position = 0.44
    elems[0].color = _rgba(getattr(props, "terrain_low_color", (0.06, 0.26, 0.04)))
    elems[1].position = 0.52
    elems[1].color = _rgba(getattr(props, "terrain_mid_color", (0.58, 0.28, 0.18)))

    n_bump = nodes.new("ShaderNodeBump")
    n_bump.location = (-40, -140)
    set_socket(n_bump, ("Strength",), 0.45)

    links.new(n_coord.outputs["Generated"], n_noise.inputs["Vector"])
    links.new(n_noise.outputs["Fac"], n_ramp.inputs["Fac"])
    links.new(n_noise.outputs["Fac"], n_bump.inputs["Height"])

    shader_out = _append_1997_depth_fog_and_ambient(
        nodes,
        links,
        base_color_socket=n_ramp.outputs["Color"],
        normal_socket=n_bump.outputs["Normal"],
        props=props,
        specular_weight=0.06,
        roughness=0.30,
    )
    links.new(shader_out, n_out.inputs["Surface"])
    return mat


def build_cloud_ground_material(props: Any) -> Any:
    if bpy is None:
        return None
    mat, nodes, links = _get_or_create_material("SDS_Mat_Terrain")
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (1600, 100)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-560, 0)

    n_noise = nodes.new("ShaderNodeTexNoise")
    n_noise.location = (-320, 0)
    set_socket(n_noise, ("Scale",), 8.0)
    set_socket(n_noise, ("Detail",), 4.5)

    n_ramp = nodes.new("ShaderNodeValToRGB")
    n_ramp.location = (-40, 0)
    elems = n_ramp.color_ramp.elements
    elems[0].position = 0.38
    elems[0].color = _rgba(getattr(props, "terrain_low_color", (0.26, 0.26, 0.28)))
    elems[1].position = 0.62
    elems[1].color = _rgba(getattr(props, "terrain_high_color", (0.98, 0.98, 1.00)))

    links.new(n_coord.outputs["Generated"], n_noise.inputs["Vector"])
    links.new(n_noise.outputs["Fac"], n_ramp.inputs["Fac"])

    shader_out = _append_1997_depth_fog_and_ambient(
        nodes,
        links,
        base_color_socket=n_ramp.outputs["Color"],
        normal_socket=None,
        props=props,
        specular_weight=0.10,
        roughness=0.10,
    )
    links.new(shader_out, n_out.inputs["Surface"])
    return mat


def build_checker_material(props: Any) -> Any:
    if bpy is None:
        return None
    mat, nodes, links = _get_or_create_material("SDS_Mat_Checker")
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (1600, 100)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-480, 0)

    n_checker = nodes.new("ShaderNodeTexChecker")
    n_checker.location = (-200, 0)
    set_socket(n_checker, ("Scale",), 24.0)
    set_socket(n_checker, ("Color1",), _rgba(getattr(props, "terrain_low_color", (0.02, 0.09, 0.44))))
    set_socket(n_checker, ("Color2",), _rgba(getattr(props, "terrain_mid_color", (1.00, 1.00, 1.00))))

    links.new(n_coord.outputs["Generated"], n_checker.inputs["Vector"])

    shader_out = _append_1997_depth_fog_and_ambient(
        nodes,
        links,
        base_color_socket=n_checker.outputs["Color"],
        normal_socket=None,
        props=props,
        specular_weight=0.14,
        roughness=0.0,
    )
    links.new(shader_out, n_out.inputs["Surface"])
    return mat


def build_water_material(props: Any) -> Any:
    """
    Supports both:
    - `RIPPLE_MIRROR`: 1997 Bryce Constant-Reflectivity Anisotropic Ripple Water (`image_98ffb5.jpg`)
    - `CYBER_GRID`: Electric Ultramarine Blue Wireframe Grid Floor (`Ob3AH_A...jpg`)
    """
    if bpy is None:
        return None

    water_style = getattr(props, "water_style", "RIPPLE_MIRROR")
    mat, nodes, links = _get_or_create_material("SDS_Mat_Water")
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (760, 0)

    w_col = getattr(props, "water_color", (0.01, 0.06, 0.48))

    if water_style == "CYBER_GRID":
        # Ref Image 5 (`Ob3AH_A...jpg`): Electric Ultramarine Blue with bright white/yellow grid lines
        n_coord = nodes.new("ShaderNodeTexCoord")
        n_coord.location = (-720, 0)
        n_wave_x = nodes.new("ShaderNodeTexWave")
        n_wave_x.location = (-460, 140)
        n_wave_x.wave_type = "BANDS"
        if hasattr(n_wave_x, "bands_direction"):
            n_wave_x.bands_direction = "X"
        set_socket(n_wave_x, ("Scale",), 18.0)
        set_socket(n_wave_x, ("Distortion",), 0.6)

        n_wave_y = nodes.new("ShaderNodeTexWave")
        n_wave_y.location = (-460, -140)
        n_wave_y.wave_type = "BANDS"
        if hasattr(n_wave_y, "bands_direction"):
            n_wave_y.bands_direction = "Y"
        set_socket(n_wave_y, ("Scale",), 18.0)
        set_socket(n_wave_y, ("Distortion",), 0.6)

        n_max = nodes.new("ShaderNodeMath")
        n_max.operation = "MAXIMUM"
        n_max.location = (-200, 0)

        n_ramp = nodes.new("ShaderNodeValToRGB")
        n_ramp.location = (20, 0)
        el = n_ramp.color_ramp.elements
        el[0].position = 0.90
        el[0].color = _rgba(w_col)
        el[1].position = 0.96
        el[1].color = (1.0, 1.0, 0.82, 1.0)

        n_emit = nodes.new("ShaderNodeEmission")
        n_emit.location = (360, 0)
        set_socket(n_emit, ("Strength",), 1.05)

        links.new(n_coord.outputs["Generated"], n_wave_x.inputs["Vector"])
        links.new(n_coord.outputs["Generated"], n_wave_y.inputs["Vector"])
        links.new(n_wave_x.outputs["Fac"], n_max.inputs[0])
        links.new(n_wave_y.outputs["Fac"], n_max.inputs[1])
        links.new(n_max.outputs["Value"], n_ramp.inputs["Fac"])
        links.new(n_ramp.outputs["Color"], n_emit.inputs["Color"])
        links.new(n_emit.outputs["Emission"], n_out.inputs["Surface"])
        return mat

    refl = max(0.0, min(1.0, float(getattr(props, "mirror_reflection", 95.0)) / 100.0))
    chop = max(0.0, min(1.0, float(getattr(props, "wave_chop", 32.0)) / 100.0))

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-760, -140)

    n_map = nodes.new("ShaderNodeMapping")
    n_map.location = (-540, -140)
    set_socket(n_map, ("Scale",), (2.2, 22.0, 1.0))

    n_noise = nodes.new("ShaderNodeTexNoise")
    n_noise.location = (-280, -140)
    set_socket(n_noise, ("Scale",), 5.8)
    set_socket(n_noise, ("Detail",), 2.8)

    n_bump = nodes.new("ShaderNodeBump")
    n_bump.location = (-20, -140)
    set_socket(n_bump, ("Strength",), chop * 0.35)

    n_gloss = nodes.new("ShaderNodeBsdfGlossy")
    n_gloss.location = (240, 120)
    set_socket(n_gloss, ("Roughness",), 0.0)
    mirror_tint = (
        min(1.0, 0.55 + w_col[0] * 0.8),
        min(1.0, 0.62 + w_col[1] * 0.8),
        min(1.0, 0.85 + w_col[2] * 0.5),
        1.0,
    )
    set_socket(n_gloss, ("Color",), mirror_tint)

    n_emit = nodes.new("ShaderNodeEmission")
    n_emit.location = (240, -120)
    set_socket(n_emit, ("Color",), _rgba(w_col))
    set_socket(n_emit, ("Strength",), 0.45)

    n_mix_shader = nodes.new("ShaderNodeMixShader")
    n_mix_shader.location = (480, 0)
    n_mix_shader.inputs["Fac"].default_value = 0.18 + (1.0 - refl) * 0.5

    links.new(n_coord.outputs["Object"], n_map.inputs["Vector"])
    links.new(n_map.outputs["Vector"], n_noise.inputs["Vector"])
    links.new(n_noise.outputs["Fac"], n_bump.inputs["Height"])
    links.new(n_bump.outputs["Normal"], n_gloss.inputs["Normal"])
    links.new(n_gloss.outputs["BSDF"], n_mix_shader.inputs[1])
    links.new(n_emit.outputs["Emission"], n_mix_shader.inputs[2])
    links.new(n_mix_shader.outputs["Shader"], n_out.inputs["Surface"])

    return mat


def build_hero_material(style: str, props: Any, variant_index: int = 0) -> Any:
    if bpy is None:
        return None

    mat_name = f"SDS_Mat_{style}_{variant_index}"
    mat, nodes, links = _get_or_create_material(mat_name)

    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (680, 0)

    palette = [
        (0.96, 0.98, 1.00),
        (0.98, 0.08, 0.12),
        (0.06, 0.86, 0.20),
        (0.08, 0.32, 1.00),
        (0.92, 0.25, 0.98),
        (1.00, 0.82, 0.06),
    ]
    base_rgb = palette[variant_index % len(palette)]

    if style == "CHROME":
        if getattr(props, "reflection_model", "WHITTED_RAYTRACE") == "SPHERICAL_ENVMAP":
            # 1997 Realtime Spherical Environment Mapping (`GL_SPHERE_MAP` via TexCoord.Reflection!)
            n_coord = nodes.new("ShaderNodeTexCoord")
            n_coord.location = (-520, 0)
            n_sep = nodes.new("ShaderNodeSeparateXYZ")
            n_sep.location = (-300, 0)
            n_ramp = nodes.new("ShaderNodeValToRGB")
            n_ramp.location = (-40, 0)
            el = n_ramp.color_ramp.elements
            gnd = getattr(props, "sky_ground_color", (0.04, 0.06, 0.22))
            hor = getattr(props, "sky_horizon_color", (0.86, 0.94, 1.00))
            zen = getattr(props, "sky_zenith_color", (0.18, 0.26, 0.78))
            el[0].position = 0.0
            el[0].color = _rgba(gnd)
            el[1].position = 0.85
            el[1].color = _rgba(zen)
            h_stop = el.new(0.48)
            h_stop.color = _rgba(hor)
            n_emit = nodes.new("ShaderNodeEmission")
            n_emit.location = (280, 0)
            set_socket(n_emit, ("Strength",), 1.15)
            links.new(n_coord.outputs["Reflection"], n_sep.inputs["Vector"])
            links.new(n_sep.outputs["Z"], n_ramp.inputs["Fac"])
            links.new(n_ramp.outputs["Color"], n_emit.inputs["Color"])
            links.new(n_emit.outputs["Emission"], n_out.inputs["Surface"])
            return mat

        n_gloss = nodes.new("ShaderNodeBsdfGlossy")
        n_gloss.location = (300, 0)
        set_socket(n_gloss, ("Color",), (0.96, 0.98, 1.00, 1.0))
        set_socket(n_gloss, ("Roughness",), 0.0)
        links.new(n_gloss.outputs["BSDF"], n_out.inputs["Surface"])
        return mat

    if style == "COPPER_METAL":
        # Ref Image 2 (`qsvqqrL...jpg`): Burnished Sunset Copper / Bronze Torus
        n_gloss = nodes.new("ShaderNodeBsdfGlossy")
        n_gloss.location = (300, 0)
        set_socket(n_gloss, ("Color",), (0.98, 0.42, 0.12, 1.0))
        set_socket(n_gloss, ("Roughness",), 0.02)
        links.new(n_gloss.outputs["BSDF"], n_out.inputs["Surface"])
        return mat

    if style == "RUBY_GLASS":
        # Ref Image 2 (`qsvqqrL...jpg`): Translucent Glowing Ruby-Red Monolith Slab
        n_glass = nodes.new("ShaderNodeBsdfPrincipled")
        n_glass.location = (300, 0)
        set_socket(n_glass, ("Base Color",), (1.0, 0.12, 0.16, 1.0))
        set_socket(n_glass, ("Roughness",), 0.0)
        set_socket(n_glass, ("IOR",), 1.48)
        set_socket(n_glass, ("Transmission Weight", "Transmission"), 0.92)
        set_socket(n_glass, ("Emission Color", "Emission"), (1.0, 0.15, 0.18, 1.0))
        set_socket(n_glass, ("Emission Strength",), 0.35)
        links.new(n_glass.outputs["BSDF"], n_out.inputs["Surface"])
        return mat

    if style == "NEON_GREEN_CRYSTAL":
        # Ref Image 1 (`dT6cACN...jpg`): Glowing Neon-Green Bio-Crystal Spikes
        n_emit = nodes.new("ShaderNodeEmission")
        n_emit.location = (300, 0)
        set_socket(n_emit, ("Color",), (0.12, 1.0, 0.18, 1.0))
        set_socket(n_emit, ("Strength",), 2.4)
        links.new(n_emit.outputs["Emission"], n_out.inputs["Surface"])
        return mat

    if style == "EYEBALL_ORB":
        # Ref Image 2 (`qsvqqrL...jpg`): Surreal 1997 Floating Eyeball Orb
        n_coord = nodes.new("ShaderNodeTexCoord")
        n_coord.location = (-560, 0)
        n_grad = nodes.new("ShaderNodeTexGradient")
        n_grad.location = (-320, 0)
        n_grad.gradient_type = "SPHERICAL"
        n_ramp = nodes.new("ShaderNodeValToRGB")
        n_ramp.location = (-60, 0)
        el = n_ramp.color_ramp.elements
        el[0].position = 0.62
        el[0].color = (0.85, 0.78, 0.82, 1.0)
        el[1].position = 0.88
        el[1].color = (0.02, 0.04, 0.08, 1.0)
        iris = el.new(0.74)
        iris.color = (0.12, 0.48, 0.78, 1.0)
        links.new(n_coord.outputs["Object"], n_grad.inputs["Vector"])
        links.new(n_grad.outputs["Fac"], n_ramp.inputs["Fac"])
        shader_out = _append_1997_depth_fog_and_ambient(
            nodes,
            links,
            base_color_socket=n_ramp.outputs["Color"],
            normal_socket=None,
            props=props,
            specular_weight=0.18,
            roughness=0.05,
        )
        links.new(shader_out, n_out.inputs["Surface"])
        return mat

    if style == "GLASS":
        n_glass = nodes.new("ShaderNodeBsdfPrincipled")
        n_glass.location = (300, 0)
        aero_tint = (0.76, 0.96, 1.0) if variant_index % 2 == 0 else (0.70, 1.0, 0.84)
        set_socket(n_glass, ("Base Color",), _rgba(aero_tint))
        set_socket(n_glass, ("Roughness",), 0.0)
        set_socket(n_glass, ("IOR",), 1.48)
        set_socket(n_glass, ("Transmission Weight", "Transmission"), 0.98)
        set_socket(n_glass, ("Specular IOR Level", "Specular"), 1.0)
        links.new(n_glass.outputs["BSDF"], n_out.inputs["Surface"])
        return mat

    if style == "COBALT_MARBLE_TOP":
        n_coord = nodes.new("ShaderNodeTexCoord")
        n_coord.location = (-560, 0)
        n_noise = nodes.new("ShaderNodeTexNoise")
        n_noise.location = (-320, 0)
        set_socket(n_noise, ("Scale",), 5.5)
        set_socket(n_noise, ("Detail",), 3.5)
        n_ramp = nodes.new("ShaderNodeValToRGB")
        n_ramp.location = (-60, 0)
        el = n_ramp.color_ramp.elements
        el[0].position = 0.28
        el[0].color = (0.02, 0.14, 0.68, 1.0)
        el[1].position = 0.72
        el[1].color = (0.14, 0.46, 1.00, 1.0)
        links.new(n_coord.outputs["Generated"], n_noise.inputs["Vector"])
        links.new(n_noise.outputs["Fac"], n_ramp.inputs["Fac"])

        shader_out = _append_1997_depth_fog_and_ambient(
            nodes,
            links,
            base_color_socket=n_ramp.outputs["Color"],
            normal_socket=None,
            props=props,
            specular_weight=0.22,
            roughness=0.02,
        )
        links.new(shader_out, n_out.inputs["Surface"])
        return mat

    if style == "MARBLE_ORB":
        n_coord = nodes.new("ShaderNodeTexCoord")
        n_coord.location = (-560, 0)
        n_noise = nodes.new("ShaderNodeTexNoise")
        n_noise.location = (-320, 0)
        set_socket(n_noise, ("Scale",), 3.6 + variant_index * 1.1)
        set_socket(n_noise, ("Detail",), 4.0)
        set_socket(n_noise, ("Distortion",), 2.2)

        n_ramp = nodes.new("ShaderNodeValToRGB")
        n_ramp.location = (-60, 0)
        elems = n_ramp.color_ramp.elements
        elems[0].position = 0.35
        elems[0].color = _rgba((0.04, 0.06, 0.12))
        elems[1].position = 0.65
        elems[1].color = _rgba(base_rgb)

        links.new(n_coord.outputs["Object"], n_noise.inputs["Vector"])
        links.new(n_noise.outputs["Fac"], n_ramp.inputs["Fac"])

        n_gloss = nodes.new("ShaderNodeBsdfGlossy")
        n_gloss.location = (260, 80)
        set_socket(n_gloss, ("Roughness",), 0.0)
        links.new(n_ramp.outputs["Color"], n_gloss.inputs["Color"])

        n_diff = nodes.new("ShaderNodeBsdfDiffuse")
        n_diff.location = (260, -100)
        links.new(n_ramp.outputs["Color"], n_diff.inputs["Color"])

        n_mix = nodes.new("ShaderNodeMixShader")
        n_mix.location = (480, 0)
        n_mix.inputs["Fac"].default_value = 0.25 if variant_index > 0 else 0.05
        links.new(n_gloss.outputs["BSDF"], n_mix.inputs[1])
        links.new(n_diff.outputs["BSDF"], n_mix.inputs[2])
        links.new(n_mix.outputs["Shader"], n_out.inputs["Surface"])
        return mat

    if style == "RAINBOW":
        n_coord = nodes.new("ShaderNodeTexCoord")
        n_coord.location = (-520, 0)
        n_grad = nodes.new("ShaderNodeTexGradient")
        n_grad.location = (-300, 0)
        n_ramp = nodes.new("ShaderNodeValToRGB")
        n_ramp.location = (-60, 0)
        n_ramp.color_ramp.color_mode = "HSV"
        n_ramp.color_ramp.hue_interpolation = "FAR"
        n_ramp.color_ramp.elements[0].color = (1.0, 0.08, 0.55, 1.0)
        n_ramp.color_ramp.elements[1].color = (0.05, 0.95, 1.0, 1.0)

        n_gloss = nodes.new("ShaderNodeBsdfGlossy")
        n_gloss.location = (280, 0)
        set_socket(n_gloss, ("Roughness",), 0.0)

        links.new(n_coord.outputs["Generated"], n_grad.inputs["Vector"])
        links.new(n_grad.outputs["Fac"], n_ramp.inputs["Fac"])
        links.new(n_ramp.outputs["Color"], n_gloss.inputs["Color"])
        links.new(n_gloss.outputs["BSDF"], n_out.inputs["Surface"])
        return mat

    if style == "PYRAMID_SAND":
        n_coord = nodes.new("ShaderNodeTexCoord")
        n_coord.location = (-520, 0)
        n_noise = nodes.new("ShaderNodeTexNoise")
        n_noise.location = (-280, 0)
        set_socket(n_noise, ("Scale",), 28.0)
        set_socket(n_noise, ("Detail",), 5.0)

        n_ramp = nodes.new("ShaderNodeValToRGB")
        n_ramp.location = (-40, 120)
        el = n_ramp.color_ramp.elements
        el[0].position = 0.30
        el[0].color = (0.78, 0.68, 0.28, 1.0)
        el[1].position = 0.70
        el[1].color = (0.98, 0.90, 0.46, 1.0)

        n_bump = nodes.new("ShaderNodeBump")
        n_bump.location = (-40, -140)
        set_socket(n_bump, ("Strength",), 0.28)

        links.new(n_coord.outputs["Object"], n_noise.inputs["Vector"])
        links.new(n_noise.outputs["Fac"], n_ramp.inputs["Fac"])
        links.new(n_noise.outputs["Fac"], n_bump.inputs["Height"])

        shader_out = _append_1997_depth_fog_and_ambient(
            nodes,
            links,
            base_color_socket=n_ramp.outputs["Color"],
            normal_socket=n_bump.outputs["Normal"],
            props=props,
            specular_weight=0.05,
            roughness=0.35,
        )
        links.new(shader_out, n_out.inputs["Surface"])
        return mat

    if style == "PLANET_LAVA":
        n_coord = nodes.new("ShaderNodeTexCoord")
        n_coord.location = (-560, 0)
        n_noise = nodes.new("ShaderNodeTexNoise")
        n_noise.location = (-340, 0)
        set_socket(n_noise, ("Scale",), 4.8)
        set_socket(n_noise, ("Detail",), 5.0)
        n_ramp = nodes.new("ShaderNodeValToRGB")
        n_ramp.location = (-80, 0)
        elems = n_ramp.color_ramp.elements
        elems[0].position = 0.28
        elems[0].color = (0.32, 0.04, 0.02, 1.0)
        elems[1].position = 0.74
        elems[1].color = (1.0, 0.82, 0.18, 1.0)
        mid = elems.new(0.50)
        mid.color = (0.94, 0.22, 0.04, 1.0)

        n_emit = nodes.new("ShaderNodeEmission")
        n_emit.location = (260, 0)
        set_socket(n_emit, ("Strength",), 2.2)

        links.new(n_coord.outputs["Object"], n_noise.inputs["Vector"])
        links.new(n_noise.outputs["Fac"], n_ramp.inputs["Fac"])
        links.new(n_ramp.outputs["Color"], n_emit.inputs["Color"])
        links.new(n_emit.outputs["Emission"], n_out.inputs["Surface"])
        return mat

    # Default PLASTIC (1997 High-Saturation Lambert + Phong)
    n_rgb = nodes.new("ShaderNodeRGB")
    n_rgb.location = (-120, 120)
    n_rgb.outputs[0].default_value = _rgba(base_rgb)
    shader_out = _append_1997_depth_fog_and_ambient(
        nodes,
        links,
        base_color_socket=n_rgb.outputs[0],
        normal_socket=None,
        props=props,
        specular_weight=0.35,
        roughness=0.02,
    )
    links.new(shader_out, n_out.inputs["Surface"])
    return mat





def build_dream_facade_material(props: Any, variant_index: int = 0) -> Any:
    """
    Builds a 1998《LSD: Dream Emulator》/ PS1 procedural building window-facade material
    using `ShaderNodeTexBrick` + optional PS1 Affine UV shear (`ps1_affine_warp`).
    """
    if bpy is None:
        return None
    mat_name = f"SDS_Mat_DreamFacade_{variant_index}"
    mat, nodes, links = _get_or_create_material(mat_name)
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (1600, 100)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-820, 0)

    # PS1 Affine UV Warping simulation (shears UVs based on Camera View vector / Noise)
    warp_pct = max(0.0, min(100.0, float(getattr(props, "ps1_affine_warp", 0.0)))) / 100.0
    if getattr(props, "era_pipeline", "BRYCE_1997") == "PS1_1998_LSD" and warp_pct < 0.05:
        warp_pct = 0.55

    n_map = nodes.new("ShaderNodeMapping")
    n_map.location = (-580, 0)
    set_socket(n_map, ("Scale",), (3.5, 3.5, 3.5))
    if warp_pct > 0.01:
        set_socket(n_map, ("Rotation",), (0.0, 0.0, warp_pct * 0.22))

    n_brick = nodes.new("ShaderNodeTexBrick")
    n_brick.location = (-300, 0)
    set_socket(n_brick, ("Scale",), 4.5 + (variant_index % 3) * 1.5)
    set_socket(n_brick, ("Mortar Size",), 0.06)
    set_socket(n_brick, ("Mortar Smooth",), 0.0)

    facade_palettes = [
        ((0.18, 0.22, 0.32), (0.95, 0.88, 0.32), (0.08, 0.10, 0.14)),
        ((0.48, 0.16, 0.22), (0.22, 0.92, 0.78), (0.14, 0.04, 0.08)),
        ((0.24, 0.38, 0.22), (0.96, 0.42, 0.18), (0.08, 0.14, 0.06)),
        ((0.35, 0.28, 0.52), (0.98, 0.95, 0.65), (0.12, 0.08, 0.20)),
        ((0.62, 0.58, 0.48), (0.12, 0.28, 0.45), (0.25, 0.22, 0.18)),
    ]
    c_wall, c_win, c_mort = facade_palettes[variant_index % len(facade_palettes)]
    set_socket(n_brick, ("Color1",), _rgba(c_wall))
    set_socket(n_brick, ("Color2",), _rgba(c_win))
    set_socket(n_brick, ("Mortar",), _rgba(c_mort))

    locked_c = _get_locked_rest_coord(nodes, links, n_coord.outputs["Object"])
    links.new(locked_c, n_map.inputs["Vector"])
    links.new(n_map.outputs["Vector"], n_brick.inputs["Vector"])

    shader_out = _append_1997_depth_fog_and_ambient(
        nodes,
        links,
        base_color_socket=n_brick.outputs["Color"],
        normal_socket=None,
        props=props,
        specular_weight=0.04,
        roughness=0.40,
    )
    links.new(shader_out, n_out.inputs["Surface"])
    return mat


def build_dream_wall_material(props: Any, variant_index: int = 0) -> Any:
    """Builds an LSD corridor/courtyard wall material with surreal color stains."""
    if bpy is None:
        return None
    mat_name = f"SDS_Mat_DreamWall_{variant_index}"
    mat, nodes, links = _get_or_create_material(mat_name)
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (1600, 100)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-620, 0)
    n_noise = nodes.new("ShaderNodeTexNoise")
    n_noise.location = (-360, 0)
    set_socket(n_noise, ("Scale",), 4.2)
    set_socket(n_noise, ("Detail",), 2.0)

    n_ramp = nodes.new("ShaderNodeValToRGB")
    n_ramp.location = (-80, 0)
    wall_palettes = [
        ((0.68, 0.62, 0.48), (0.28, 0.42, 0.36)),
        ((0.55, 0.24, 0.42), (0.88, 0.72, 0.25)),
        ((0.22, 0.36, 0.58), (0.78, 0.32, 0.28)),
    ]
    c0, c1 = wall_palettes[variant_index % len(wall_palettes)]
    n_ramp.color_ramp.elements[0].position = 0.35
    n_ramp.color_ramp.elements[0].color = _rgba(c0)
    n_ramp.color_ramp.elements[1].position = 0.68
    n_ramp.color_ramp.elements[1].color = _rgba(c1)

    locked_c = _get_locked_rest_coord(nodes, links, n_coord.outputs["Object"])
    links.new(locked_c, n_noise.inputs["Vector"])
    links.new(n_noise.outputs["Fac"], n_ramp.inputs["Fac"])

    shader_out = _append_1997_depth_fog_and_ambient(
        nodes,
        links,
        base_color_socket=n_ramp.outputs["Color"],
        normal_socket=None,
        props=props,
        specular_weight=0.02,
        roughness=0.50,
    )
    links.new(shader_out, n_out.inputs["Surface"])
    return mat


def build_dream_mutated_material(props: Any, variant_index: int = 0) -> Any:
    """
    Implements `LOCAL_MUTATION` (`b.txt` Section 3.3):
    Mixes natural grass/rock with sudden patches of building window facades and checkerboards!
    """
    if bpy is None:
        return None
    mat_name = f"SDS_Mat_DreamMutated_{variant_index}"
    mat, nodes, links = _get_or_create_material(mat_name)
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (1600, 100)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-780, 0)

    n_brick = nodes.new("ShaderNodeTexBrick")
    n_brick.location = (-440, 220)
    set_socket(n_brick, ("Scale",), 6.0)
    set_socket(n_brick, ("Color1",), (0.15, 0.20, 0.35, 1.0))
    set_socket(n_brick, ("Color2",), (0.98, 0.90, 0.25, 1.0))

    n_chk = nodes.new("ShaderNodeTexChecker")
    n_chk.location = (-440, -40)
    set_socket(n_chk, ("Scale",), 12.0)
    set_socket(n_chk, ("Color1",), (0.08, 0.55, 0.18, 1.0))
    set_socket(n_chk, ("Color2",), (0.92, 0.22, 0.58, 1.0))

    n_mask = nodes.new("ShaderNodeTexNoise")
    n_mask.location = (-440, -280)
    set_socket(n_mask, ("Scale",), 1.8)
    set_socket(n_mask, ("Detail",), 1.0)

    n_ramp = nodes.new("ShaderNodeValToRGB")
    n_ramp.location = (-180, -280)
    n_ramp.color_ramp.elements[0].position = 0.48
    n_ramp.color_ramp.elements[1].position = 0.52

    _, m_fac, m_c1, m_c2, m_out = _new_mix_color(nodes, links, location=(140, 100))

    links.new(n_coord.outputs["Object"], n_brick.inputs["Vector"])
    links.new(n_coord.outputs["Object"], n_chk.inputs["Vector"])
    links.new(n_coord.outputs["Object"], n_mask.inputs["Vector"])
    links.new(n_mask.outputs["Fac"], n_ramp.inputs["Fac"])
    links.new(n_ramp.outputs["Color"], m_fac)
    links.new(n_brick.outputs["Color"], m_c1)
    links.new(n_chk.outputs["Color"], m_c2)

    shader_out = _append_1997_depth_fog_and_ambient(
        nodes,
        links,
        base_color_socket=m_out,
        normal_socket=None,
        props=props,
        specular_weight=0.08,
        roughness=0.20,
    )
    links.new(shader_out, n_out.inputs["Surface"])
    return mat







def _to_triplanar_2d_coord(nodes: Any, links: Any, vec_socket: Any, loc_x: float = -420.0, loc_y: float = 0.0) -> Any:
    """
    Projects 3D coordinates `(X, Y, Z)` onto a Triplanar 2D+Z vector:
    - On horizontal floors/ceilings (`|TrueNormal.Z| > 0.55`): `(X, Y, Z)`
    - On vertical walls/pillars (`|TrueNormal.Z| <= 0.55`): `(X + Y, Z, Y)`
    Guarantees that 2D nodes like `ShaderNodeTexBrick` (which only read X and Y and ignore Z!)
    render crisp 2D horizontal-by-vertical bricks/tiles on ALL vertical walls and pillars!
    """
    try:
        n_sep_p = nodes.new("ShaderNodeSeparateXYZ")
        n_sep_p.location = (loc_x, loc_y)
        links.new(vec_socket, n_sep_p.inputs["Vector"])

        n_geom = nodes.new("ShaderNodeNewGeometry")
        n_geom.location = (loc_x, loc_y - 180)
        norm_out = (n_geom.outputs["True Normal"] if "True Normal" in n_geom.outputs else n_geom.outputs[0])

        n_sep_n = nodes.new("ShaderNodeSeparateXYZ")
        n_sep_n.location = (loc_x + 140, loc_y - 180)
        links.new(norm_out, n_sep_n.inputs["Vector"])

        n_abs_nz = nodes.new("ShaderNodeMath")
        n_abs_nz.operation = "ABSOLUTE"
        n_abs_nz.location = (loc_x + 280, loc_y - 180)
        links.new(n_sep_n.outputs["Z"], n_abs_nz.inputs[0])

        n_is_floor = nodes.new("ShaderNodeMath")
        n_is_floor.operation = "GREATER_THAN"
        n_is_floor.location = (loc_x + 420, loc_y - 180)
        n_is_floor.inputs[1].default_value = 0.55
        links.new(n_abs_nz.outputs["Value"], n_is_floor.inputs[0])

        n_u_wall = nodes.new("ShaderNodeMath")
        n_u_wall.operation = "ADD"
        n_u_wall.location = (loc_x + 160, loc_y + 40)
        links.new(n_sep_p.outputs["X"], n_u_wall.inputs[0])
        links.new(n_sep_p.outputs["Y"], n_u_wall.inputs[1])

        n_comb_wall = nodes.new("ShaderNodeCombineXYZ")
        n_comb_wall.location = (loc_x + 320, loc_y + 40)
        links.new(n_u_wall.outputs["Value"], n_comb_wall.inputs[0])
        links.new(n_sep_p.outputs["Z"], n_comb_wall.inputs[1])
        links.new(n_sep_p.outputs["Z"], n_comb_wall.inputs[2])

        _, m_fac, m_c1, m_c2, tri_out = _new_mix_color(nodes, links, location=(loc_x + 520, loc_y))
        links.new(n_is_floor.outputs["Value"], m_fac)
        links.new(n_comb_wall.outputs["Vector"], m_c1)
        links.new(vec_socket, m_c2)
        return tri_out
    except Exception:
        return vec_socket


def _get_locked_rest_coord(nodes: Any, links: Any, fallback_socket: Any, loc_x: float = -1100.0, loc_y: float = -180.0) -> Any:
    """
    Reads the pre-deformation vertex attribute `sds_rest_pos` stored by `SDS_PS1_GTE_Quantize_GN`
    so procedural textures remain 100% glued to polygon faces and NEVER flip or swim when vertices step!
    Falls back to `fallback_socket` if `sds_rest_pos` is not present.
    """
    try:
        n_attr = nodes.new("ShaderNodeAttribute")
        n_attr.attribute_name = "sds_rest_pos"
        n_attr.location = (loc_x, loc_y)

        n_len = nodes.new("ShaderNodeVectorMath")
        n_len.operation = "LENGTH"
        n_len.location = (loc_x + 160, loc_y - 80)
        links.new(n_attr.outputs["Vector"], n_len.inputs[0])

        n_gt = nodes.new("ShaderNodeMath")
        n_gt.operation = "GREATER_THAN"
        n_gt.location = (loc_x + 320, loc_y - 80)
        n_gt.inputs[1].default_value = 0.0001
        links.new(n_len.outputs["Value"], n_gt.inputs[0])

        _, m_fac, m_c1, m_c2, m_out = _new_mix_color(nodes, links, location=(loc_x + 480, loc_y))
        links.new(n_gt.outputs["Value"], m_fac)
        links.new(fallback_socket, m_c1)
        links.new(n_attr.outputs["Vector"], m_c2)
        return m_out
    except Exception:
        return fallback_socket


def _build_ps1_texel_coord(
    nodes: Any,
    links: Any,
    coord_socket: Any,
    scale_xyz: Tuple[float, float, float] = (1.0, 1.0, 1.0),
    texel_res: float = 48.0,
    affine_shear: float = 0.35,
    loc_x: float = -900.0,
    loc_y: float = 0.0,
) -> Any:
    """
    Transforms continuous 3D/UV coordinates into crisp PS1 Nearest-Neighbor (`Closest`)
    discrete square texels:
    1. Offsets locked rest coordinates by `(+128.5, +128.5, +128.5)` so coordinates are strictly
       positive everywhere, completely eliminating X=0/Y=0 origin seams!
    2. Applies subtle PS1 triangle-diagonal affine UV kinking without blurring square tiles.
    3. Snaps coordinates via `ShaderNodeVectorMath (operation='SNAP')` to `1.0 / eff_res`
       so every texture renders with sharp, unmistakable square pixel-art clarity!
    """
    locked_coord = _get_locked_rest_coord(nodes, links, coord_socket, loc_x - 560, loc_y - 160)
    n_map = nodes.new("ShaderNodeMapping")
    n_map.location = (loc_x, loc_y)
    set_socket(n_map, ("Location",), (128.5, 128.5, 128.5))
    set_socket(n_map, ("Scale",), scale_xyz)
    links.new(locked_coord, n_map.inputs["Vector"])
    curr_vec = n_map.outputs["Vector"]

    if affine_shear > 0.005:
        n_diag = nodes.new("ShaderNodeTexWave")
        n_diag.location = (loc_x + 180, loc_y - 180)
        n_diag.wave_type = "BANDS"
        if hasattr(n_diag, "bands_direction"):
            n_diag.bands_direction = "DIAGONAL"
        if hasattr(n_diag, "wave_profile"):
            n_diag.wave_profile = "SAW"
        set_socket(n_diag, ("Scale",), 3.2)
        links.new(curr_vec, n_diag.inputs["Vector"])

        n_shear_mul = nodes.new("ShaderNodeMath")
        n_shear_mul.operation = "MULTIPLY"
        n_shear_mul.location = (loc_x + 340, loc_y - 180)
        # Keep affine kink crisp and localized (0.022 max) so square tiles stay rectangular
        n_shear_mul.inputs[1].default_value = min(0.035, affine_shear * 0.022)
        links.new(n_diag.outputs["Fac"], n_shear_mul.inputs[0])

        n_vec_add = nodes.new("ShaderNodeVectorMath")
        n_vec_add.operation = "ADD"
        n_vec_add.location = (loc_x + 500, loc_y)
        links.new(curr_vec, n_vec_add.inputs[0])
        links.new(n_shear_mul.outputs["Value"], n_vec_add.inputs[1])
        curr_vec = n_vec_add.outputs["Vector"]

    # High-clarity Nearest-Neighbor square pixel grid
    eff_res = max(24.0, float(texel_res) * 1.45)
    step = 1.0 / eff_res
    n_snap = nodes.new("ShaderNodeVectorMath")
    n_snap.operation = "SNAP"
    n_snap.location = (loc_x + 680, loc_y)
    for inp in list(n_snap.inputs)[1:]:
        if getattr(inp, "type", "") == "VECTOR":
            try:
                inp.default_value = (step, step, step)
            except Exception:
                pass
    tri_vec = _to_triplanar_2d_coord(nodes, links, curr_vec, loc_x + 520, loc_y - 120)
    links.new(tri_vec, n_snap.inputs[0])
    return n_snap.outputs["Vector"]




def _finish_ps1_unlit_or_gouraud_shader(
    nodes: Any,
    links: Any,
    base_color_socket: Any,
    props: Any,
    extra_emit: float = 0.0,
) -> Any:
    """Routes all PS1 BMC & Kowloon shaders through the unified PS1 Unlit + GTE Flat-Polygon Shading pipeline."""
    return _append_1997_depth_fog_and_ambient(
        nodes,
        links,
        base_color_socket=base_color_socket,
        normal_socket=None,
        props=props,
        specular_weight=0.0,
        roughness=1.0,
    )


def build_ps1_bmc_grass_material(props: Any) -> Any:
    """
    P3 & P6 (`PSOGL2_022.webp` & `BMC_regular_outside_2.webp`):
    Flat lawn with neon-green pixelated grass texels and strong diagonal chevron affine warping!
    """
    if bpy is None:
        return None
    mat, nodes, links = _get_or_create_material("SDS_Mat_Terrain")
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (1650, 100)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-1200, 0)

    # Stretch along X/Y with diagonal chevron shear + snap to discrete PS1 texels
    snap_vec = _build_ps1_texel_coord(
        nodes,
        links,
        n_coord.outputs["Object"],
        scale_xyz=(0.45, 1.85, 1.0),
        texel_res=32.0,
        affine_shear=0.85 * (max(0.0, float(getattr(props, "ps1_affine_warp", 65.0))) / 65.0),
        loc_x=-1000.0,
        loc_y=0.0,
    )

    n_noise = nodes.new("ShaderNodeTexNoise")
    n_noise.location = (-120, 0)
    set_socket(n_noise, ("Scale",), 16.0)
    set_socket(n_noise, ("Detail",), 1.0)

    n_ramp = nodes.new("ShaderNodeValToRGB")
    n_ramp.location = (140, 0)
    n_ramp.color_ramp.interpolation = "CONSTANT"
    el = n_ramp.color_ramp.elements
    el[0].position = 0.0
    el[0].color = (0.14, 0.58, 0.04, 1.0)
    el[1].position = 0.45
    el[1].color = (0.28, 0.82, 0.08, 1.0)
    e2 = el.new(0.72)
    e2.color = (0.42, 0.94, 0.14, 1.0)

    links.new(snap_vec, n_noise.inputs["Vector"])
    links.new(n_noise.outputs["Fac"], n_ramp.inputs["Fac"])

    shader_out = _finish_ps1_unlit_or_gouraud_shader(nodes, links, n_ramp.outputs["Color"], props)
    links.new(shader_out, n_out.inputs["Surface"])
    return mat


def build_ps1_bmc_exterior_material(props: Any) -> Any:
    """
    P3 & P6: Bright Moon Cottage 4-story exterior wall with alternating dark-brown (#382C28)
    and speckled grey-pink (#786662) horizontal concrete bands and blocky pixel noise!
    """
    if bpy is None:
        return None
    mat, nodes, links = _get_or_create_material("SDS_Mat_BMC_Exterior")
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (1650, 100)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-1200, 0)
    snap_vec = _build_ps1_texel_coord(
        nodes, links, n_coord.outputs["Object"], scale_xyz=(1.0, 1.0, 1.0), texel_res=24.0, affine_shear=0.25 * (max(0.0, float(getattr(props, "ps1_affine_warp", 65.0))) / 65.0)
    )

    n_sep = nodes.new("ShaderNodeSeparateXYZ")
    n_sep.location = (-180, 200)

    # Horizontal story bands along Z
    n_wave_z = nodes.new("ShaderNodeTexWave")
    n_wave_z.location = (20, 220)
    n_wave_z.wave_type = "BANDS"
    if hasattr(n_wave_z, "bands_direction"):
        n_wave_z.bands_direction = "Z"
    set_socket(n_wave_z, ("Scale",), 0.85)
    set_socket(n_wave_z, ("Distortion",), 0.0)

    # High-frequency speckled pixel noise (4-bit CLUT concrete grain in P3 & P6)
    n_speck = nodes.new("ShaderNodeTexNoise")
    n_speck.location = (20, -60)
    set_socket(n_speck, ("Scale",), 35.0)
    set_socket(n_speck, ("Detail",), 0.0)

    n_mix_val = nodes.new("ShaderNodeMath")
    n_mix_val.operation = "MULTIPLY_ADD"
    n_mix_val.location = (220, 100)
    n_mix_val.inputs[1].default_value = 0.28

    n_ramp = nodes.new("ShaderNodeValToRGB")
    n_ramp.location = (380, 100)
    n_ramp.color_ramp.interpolation = "CONSTANT"
    el = n_ramp.color_ramp.elements
    el[0].position = 0.0
    el[0].color = (0.16, 0.12, 0.12, 1.0)
    el[1].position = 0.52
    el[1].color = (0.48, 0.38, 0.36, 1.0)
    e_hi = el.new(0.76)
    e_hi.color = (0.68, 0.56, 0.54, 1.0)

    links.new(snap_vec, n_wave_z.inputs["Vector"])
    links.new(snap_vec, n_speck.inputs["Vector"])
    links.new(n_speck.outputs["Fac"], n_mix_val.inputs[0])
    links.new(n_wave_z.outputs["Fac"], n_mix_val.inputs[2])
    links.new(n_mix_val.outputs["Value"], n_ramp.inputs["Fac"])

    shader_out = _finish_ps1_unlit_or_gouraud_shader(nodes, links, n_ramp.outputs["Color"], props)
    links.new(shader_out, n_out.inputs["Surface"])
    return mat


def build_ps1_bmc_window_material(props: Any) -> Any:
    """
    P3 & P6: Inset double-pane window with purple-blue-white gradient glass and dark frame,
    exhibiting the classic PS1 diagonal triangle affine kink!
    """
    if bpy is None:
        return None
    mat, nodes, links = _get_or_create_material("SDS_Mat_BMC_Window")
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (1650, 100)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-1200, 0)
    snap_vec = _build_ps1_texel_coord(
        nodes, links, n_coord.outputs["Generated"], scale_xyz=(1.0, 1.0, 1.0), texel_res=24.0, affine_shear=0.65 * (max(0.0, float(getattr(props, "ps1_affine_warp", 65.0))) / 65.0)
    )

    n_brick = nodes.new("ShaderNodeTexBrick")
    n_brick.location = (-100, 0)
    set_socket(n_brick, ("Scale",), 2.0)
    set_socket(n_brick, ("Row Height",), 1.0)
    set_socket(n_brick, ("Brick Width",), 0.5)
    set_socket(n_brick, ("Offset",), 0.0)
    set_socket(n_brick, ("Mortar Size",), 0.08)
    set_socket(n_brick, ("Mortar Smooth",), 0.0)
    set_socket(n_brick, ("Color1",), (0.38, 0.36, 0.78, 1.0))
    set_socket(n_brick, ("Color2",), (0.72, 0.74, 0.92, 1.0))
    set_socket(n_brick, ("Mortar",), (0.08, 0.06, 0.10, 1.0))

    links.new(snap_vec, n_brick.inputs["Vector"])
    shader_out = _finish_ps1_unlit_or_gouraud_shader(nodes, links, n_brick.outputs["Color"], props)
    links.new(shader_out, n_out.inputs["Surface"])
    return mat


def build_ps1_bmc_shoji_wall_material(props: Any) -> Any:
    """
    P3, P4, P5 (`BMC_normal_bar_1.webp` & `BMC_normal_second_floor.webp`):
    Yellow-cream Japanese shoji/tatami wall with red-brown timber grid strips,
    dark mahogany lower wainscoting (in bar), and quantized pixel-stepped green/brown vertex shading!
    """
    if bpy is None:
        return None
    mat, nodes, links = _get_or_create_material("SDS_Mat_BMC_ShojiWall")
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (1650, 100)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-1200, 0)
    snap_vec = _build_ps1_texel_coord(
        nodes, links, n_coord.outputs["Generated"], scale_xyz=(1.0, 1.0, 1.0), texel_res=32.0, affine_shear=0.20 * (max(0.0, float(getattr(props, "ps1_affine_warp", 65.0))) / 65.0)
    )

    n_sep = nodes.new("ShaderNodeSeparateXYZ")
    n_sep.location = (-180, -180)

    n_brick = nodes.new("ShaderNodeTexBrick")
    n_brick.location = (-180, 160)
    set_socket(n_brick, ("Scale",), 4.0)
    set_socket(n_brick, ("Offset",), 0.0)
    set_socket(n_brick, ("Mortar Size",), 0.04)
    set_socket(n_brick, ("Mortar Smooth",), 0.0)
    set_socket(n_brick, ("Color1",), (0.94, 0.88, 0.48, 1.0))
    set_socket(n_brick, ("Color2",), (0.86, 0.82, 0.42, 1.0))
    set_socket(n_brick, ("Mortar",), (0.45, 0.16, 0.04, 1.0))

    # Lower 28% is dark red-brown ribbed wood wainscoting (`P3 & P5`)
    n_wain_ramp = nodes.new("ShaderNodeValToRGB")
    n_wain_ramp.location = (80, -180)
    n_wain_ramp.color_ramp.interpolation = "CONSTANT"
    el = n_wain_ramp.color_ramp.elements
    el[0].position = 0.0
    el[0].color = (0.34, 0.10, 0.03, 1.0)
    el[1].position = 0.28
    el[1].color = (1.0, 1.0, 1.0, 1.0)

    _, m_fac, m_c1, m_c2, m_out = _new_mix_color(nodes, links, location=(340, 80), blend_type="MULTIPLY")

    links.new(snap_vec, n_brick.inputs["Vector"])
    links.new(snap_vec, n_sep.inputs["Vector"])
    links.new(n_sep.outputs["Z"], n_wain_ramp.inputs["Fac"])
    m_fac.default_value = 1.0
    links.new(n_brick.outputs["Color"], m_c1)
    links.new(n_wain_ramp.outputs["Color"], m_c2)

    shader_out = _finish_ps1_unlit_or_gouraud_shader(nodes, links, m_out, props)
    links.new(shader_out, n_out.inputs["Surface"])
    return mat


def build_ps1_bmc_checker_floor_material(props: Any) -> Any:
    """P3 & P5 (`BMC_normal_bar_1.webp`): Black, Grey, and White pixelated checkerboard bar floor."""
    if bpy is None:
        return None
    mat, nodes, links = _get_or_create_material("SDS_Mat_BMC_CheckerFloor")
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (1650, 100)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-1200, 0)
    snap_vec = _build_ps1_texel_coord(
        nodes, links, n_coord.outputs["Object"], scale_xyz=(0.8, 0.8, 1.0), texel_res=32.0, affine_shear=0.30 * (max(0.0, float(getattr(props, "ps1_affine_warp", 65.0))) / 65.0)
    )

    n_chk = nodes.new("ShaderNodeTexChecker")
    n_chk.location = (-100, 0)
    set_socket(n_chk, ("Scale",), 2.5)
    set_socket(n_chk, ("Color1",), (0.08, 0.09, 0.10, 1.0))
    set_socket(n_chk, ("Color2",), (0.72, 0.74, 0.76, 1.0))

    links.new(snap_vec, n_chk.inputs["Vector"])
    shader_out = _finish_ps1_unlit_or_gouraud_shader(nodes, links, n_chk.outputs["Color"], props)
    links.new(shader_out, n_out.inputs["Surface"])
    return mat


def build_ps1_bmc_wood_floor_material(props: Any) -> Any:
    """P4 (`BMC_normal_second_floor.webp`): Pixelated multi-tone wooden plank corridor floor."""
    if bpy is None:
        return None
    mat, nodes, links = _get_or_create_material("SDS_Mat_BMC_WoodFloor")
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (1650, 100)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-1200, 0)
    snap_vec = _build_ps1_texel_coord(
        nodes, links, n_coord.outputs["Object"], scale_xyz=(1.5, 0.4, 1.0), texel_res=32.0, affine_shear=0.45 * (max(0.0, float(getattr(props, "ps1_affine_warp", 65.0))) / 65.0)
    )

    n_brick = nodes.new("ShaderNodeTexBrick")
    n_brick.location = (-100, 0)
    set_socket(n_brick, ("Scale",), 4.0)
    set_socket(n_brick, ("Mortar Size",), 0.03)
    set_socket(n_brick, ("Mortar Smooth",), 0.0)
    set_socket(n_brick, ("Color1",), (0.48, 0.42, 0.28, 1.0))
    set_socket(n_brick, ("Color2",), (0.28, 0.26, 0.18, 1.0))
    set_socket(n_brick, ("Mortar",), (0.10, 0.08, 0.05, 1.0))

    links.new(snap_vec, n_brick.inputs["Vector"])
    shader_out = _finish_ps1_unlit_or_gouraud_shader(nodes, links, n_brick.outputs["Color"], props)
    links.new(shader_out, n_out.inputs["Surface"])
    return mat


def build_ps1_kg_tile_pillar_material(props: Any) -> Any:
    """
    P2 (`0f3a1156.webp` right foreground pillar & wall):
    - Fine 10cm x 10cm pale greenish-grey ceramic mosaic tiles (#5a6458 / #72806e)
    - Dark recessed grout lines with vertical water grime streaks running down the seam!
    """
    mat, nodes, links = _get_or_create_material("SDS_Mat_KG_TilePillar")
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (1560, 100)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-1240, 120)
    snap_vec = _build_ps1_texel_coord(
        nodes, links, n_coord.outputs["Object"], scale_xyz=(1.0, 1.0, 1.0), texel_res=36.0, affine_shear=0.15, loc_x=-940.0, loc_y=120.0
    )

    n_brick = nodes.new("ShaderNodeTexBrick")
    n_brick.location = (-320, 140)
    n_brick.offset = 0.5
    n_brick.squash = 1.0
    set_socket(n_brick, ("Scale",), 7.5)
    set_socket(n_brick, ("Mortar Size",), 0.045)
    set_socket(n_brick, ("Mortar Smooth",), 0.0)
    set_socket(n_brick, ("Color1",), (0.34, 0.40, 0.35, 1.0))  # Pale greenish-grey ceramic tile
    set_socket(n_brick, ("Color2",), (0.28, 0.34, 0.29, 1.0))  # Weathered mosaic tile
    set_socket(n_brick, ("Mortar",), (0.08, 0.10, 0.08, 1.0))  # Dark recessed grout
    links.new(snap_vec, n_brick.inputs["Vector"])

    # Vertical water grime and rust staining running down the wall
    n_grime = nodes.new("ShaderNodeTexNoise")
    n_grime.location = (-320, -140)
    set_socket(n_grime, ("Scale",), 4.2)
    set_socket(n_grime, ("Detail",), 2.0)
    links.new(snap_vec, n_grime.inputs["Vector"])

    n_gramp = nodes.new("ShaderNodeValToRGB")
    n_gramp.location = (-40, -140)
    n_gramp.color_ramp.interpolation = "CONSTANT"
    el = n_gramp.color_ramp.elements
    el[0].position = 0.35
    el[0].color = (0.55, 0.52, 0.42, 1.0)  # Dark soot/water stain
    el[1].position = 0.65
    el[1].color = (1.00, 1.00, 1.00, 1.0)
    links.new(n_grime.outputs["Fac"], n_gramp.inputs["Fac"])

    _, m_fac, m_c1, m_c2, tile_col = _new_mix_color(nodes, links, blend_type="MULTIPLY", location=(220, 120))
    m_fac.default_value = 0.65
    links.new(n_brick.outputs["Color"], m_c1)
    links.new(n_gramp.outputs["Color"], m_c2)

    shader_out = _append_1997_depth_fog_and_ambient(nodes, links, tile_col, None, props)
    links.new(shader_out, n_out.inputs["Surface"])
    return mat


def build_ps1_kg_shutter_material(props: Any) -> Any:
    """
    P1 (`c8ee9253.webp`) & P2 (`0f3a1156.webp`):
    - Realistic weathered corrugated iron rolling shutter: dark metallic charcoal-grey (#262a2c)
    - Fine horizontal corrugation slats (`bands_direction = 'Y'` in triplanar space = vertical Z!)
    - High-frequency micro-grain metal texture + subtle dark rust/oil grime streaks (no coarse red blotches!)
    """
    mat, nodes, links = _get_or_create_material("SDS_Mat_KG_Shutter")
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (1620, 100)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-1320, 120)
    snap_vec = _build_ps1_texel_coord(
        nodes, links, n_coord.outputs["Object"], scale_xyz=(1.0, 1.0, 1.0), texel_res=48.0, affine_shear=0.10, loc_x=-1020.0, loc_y=120.0
    )

    # 1. Fine horizontal corrugation slats (along Y of triplanar coord = world Z height)
    n_wave = nodes.new("ShaderNodeTexWave")
    n_wave.location = (-360, 220)
    n_wave.wave_type = "BANDS"
    if hasattr(n_wave, "bands_direction"):
        n_wave.bands_direction = "Y"
    set_socket(n_wave, ("Scale",), 24.0)
    set_socket(n_wave, ("Distortion",), 0.15)
    links.new(snap_vec, n_wave.inputs["Vector"])

    n_slat_ramp = nodes.new("ShaderNodeValToRGB")
    n_slat_ramp.location = (-100, 220)
    el = n_slat_ramp.color_ramp.elements
    el[0].position = 0.15
    el[0].color = (0.11, 0.13, 0.14, 1.0)  # Recessed slat shadow groove
    el[1].position = 0.82
    el[1].color = (0.30, 0.33, 0.35, 1.0)  # Brushed galvanized iron highlight
    links.new(n_wave.outputs["Fac"], n_slat_ramp.inputs["Fac"])

    # 2. High-frequency micro-grain & weathered oil/rust grime (Pass 2 & Pass 3)
    n_rust = nodes.new("ShaderNodeTexNoise")
    n_rust.location = (-360, -40)
    set_socket(n_rust, ("Scale",), 9.5)
    set_socket(n_rust, ("Detail",), 3.0)
    set_socket(n_rust, ("Roughness",), 0.65)
    links.new(snap_vec, n_rust.inputs["Vector"])

    n_rust_ramp = nodes.new("ShaderNodeValToRGB")
    n_rust_ramp.location = (-100, -40)
    r_el = n_rust_ramp.color_ramp.elements
    r_el[0].position = 0.25
    r_el[0].color = (0.48, 0.36, 0.28, 1.0)  # Dark weathered oil/rust patina
    r_el[1].position = 0.72
    r_el[1].color = (1.05, 1.05, 1.02, 1.0)
    links.new(n_rust.outputs["Fac"], n_rust_ramp.inputs["Fac"])

    _, m_rfac, m_rc1, m_rc2, shutter_col = _new_mix_color(nodes, links, blend_type="MULTIPLY", location=(240, 140))
    m_rfac.default_value = 0.72
    links.new(n_slat_ramp.outputs["Color"], m_rc1)
    links.new(n_rust_ramp.outputs["Color"], m_rc2)

    shader_out = _append_1997_depth_fog_and_ambient(nodes, links, shutter_col, None, props)
    links.new(shader_out, n_out.inputs["Surface"])
    return mat


def build_ps1_kg_hydrant_material(props: Any) -> Any:
    """
    P2 (`0f3a1156.webp` left foreground cast-iron fire hydrant):
    - Deep rich weathered cast-iron red body (#8a1812) with chipped dark metal edges
    - Dark forest-green collar band (#1c4828)
    - Brass/bronze side valve caps (#a88432)
    """
    mat, nodes, links = _get_or_create_material("SDS_Mat_KG_Hydrant")
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (1460, 100)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-1180, 120)
    snap_vec = _build_ps1_texel_coord(
        nodes, links, n_coord.outputs["Object"], scale_xyz=(1.0, 1.0, 1.0), texel_res=32.0, affine_shear=0.08, loc_x=-920.0, loc_y=120.0
    )

    n_sep = nodes.new("ShaderNodeSeparateXYZ")
    n_sep.location = (-280, 120)
    links.new(snap_vec, n_sep.inputs["Vector"])

    # Green collar band around mid-height (z in [0.72, 0.95])
    n_mod_z = nodes.new("ShaderNodeMath")
    n_mod_z.operation = "MODULO"
    n_mod_z.location = (-60, 220)
    n_mod_z.inputs[1].default_value = 1.35
    links.new(n_sep.outputs["Z"], n_mod_z.inputs[0])

    n_gt_low = nodes.new("ShaderNodeMath")
    n_gt_low.operation = "GREATER_THAN"
    n_gt_low.location = (140, 300)
    n_gt_low.inputs[1].default_value = 0.72
    links.new(n_mod_z.outputs["Value"], n_gt_low.inputs[0])

    n_lt_high = nodes.new("ShaderNodeMath")
    n_lt_high.operation = "LESS_THAN"
    n_lt_high.location = (140, 140)
    n_lt_high.inputs[1].default_value = 0.96
    links.new(n_mod_z.outputs["Value"], n_lt_high.inputs[0])

    n_is_green = nodes.new("ShaderNodeMath")
    n_is_green.operation = "MULTIPLY"
    n_is_green.location = (320, 220)
    links.new(n_gt_low.outputs["Value"], n_is_green.inputs[0])
    links.new(n_lt_high.outputs["Value"], n_is_green.inputs[1])

    # Chipped edge noise
    n_chip = nodes.new("ShaderNodeTexNoise")
    n_chip.location = (-60, -80)
    set_socket(n_chip, ("Scale",), 8.5)
    links.new(snap_vec, n_chip.inputs["Vector"])

    n_chip_ramp = nodes.new("ShaderNodeValToRGB")
    n_chip_ramp.location = (140, -80)
    n_chip_ramp.color_ramp.interpolation = "CONSTANT"
    el = n_chip_ramp.color_ramp.elements
    el[0].position = 0.00
    el[0].color = (0.12, 0.08, 0.08, 1.0)  # Chipped dark cast-iron edge
    el[1].position = 0.32
    el[1].color = (0.54, 0.10, 0.08, 1.0)  # Rich red body paint
    links.new(n_chip.outputs["Fac"], n_chip_ramp.inputs["Fac"])

    _, m_gfac, m_gc1, m_gc2, hydrant_col = _new_mix_color(nodes, links, location=(520, 120))
    m_gc2.default_value = (0.12, 0.32, 0.16, 1.0)  # Dark green collar band
    links.new(n_is_green.outputs["Value"], m_gfac)
    links.new(n_chip_ramp.outputs["Color"], m_gc1)

    shader_out = _append_1997_depth_fog_and_ambient(nodes, links, hydrant_col, None, props)
    links.new(shader_out, n_out.inputs["Surface"])
    return mat


def build_ps1_kg_alley_ground_material(props: Any) -> Any:
    """
    P1 (`c8ee9253.webp`) & P2 (`0f3a1156.webp`):
    - Dark damp weathered concrete & stone slab alley pavement (#1c1e20)
    - Subtle stone slab joints & damp reflection spots under the warm lantern!
    """
    mat, nodes, links = _get_or_create_material("SDS_Mat_KG_AlleyGround")
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (1480, 100)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-1200, 120)
    snap_vec = _build_ps1_texel_coord(
        nodes, links, n_coord.outputs["Object"], scale_xyz=(1.0, 1.0, 1.0), texel_res=32.0, affine_shear=0.18, loc_x=-940.0, loc_y=120.0
    )

    n_brick = nodes.new("ShaderNodeTexBrick")
    n_brick.location = (-300, 140)
    n_brick.offset = 0.5
    n_brick.squash = 1.4
    set_socket(n_brick, ("Scale",), 2.2)
    set_socket(n_brick, ("Mortar Size",), 0.035)
    set_socket(n_brick, ("Mortar Smooth",), 0.0)
    set_socket(n_brick, ("Color1",), (0.14, 0.15, 0.16, 1.0))
    set_socket(n_brick, ("Color2",), (0.18, 0.19, 0.20, 1.0))
    set_socket(n_brick, ("Mortar",), (0.05, 0.06, 0.06, 1.0))
    links.new(snap_vec, n_brick.inputs["Vector"])

    n_puddle = nodes.new("ShaderNodeTexNoise")
    n_puddle.location = (-300, -120)
    set_socket(n_puddle, ("Scale",), 3.2)
    set_socket(n_puddle, ("Detail",), 2.0)
    links.new(snap_vec, n_puddle.inputs["Vector"])

    n_pramp = nodes.new("ShaderNodeValToRGB")
    n_pramp.location = (-40, -120)
    n_pramp.color_ramp.interpolation = "CONSTANT"
    el = n_pramp.color_ramp.elements
    el[0].position = 0.42
    el[0].color = (0.75, 0.78, 0.82, 1.0)  # Dark damp puddle shadow
    el[1].position = 0.65
    el[1].color = (1.00, 1.00, 1.00, 1.0)
    links.new(n_puddle.outputs["Fac"], n_pramp.inputs["Fac"])

    _, m_fac, m_c1, m_c2, ground_col = _new_mix_color(nodes, links, blend_type="MULTIPLY", location=(220, 100))
    m_fac.default_value = 0.68
    links.new(n_brick.outputs["Color"], m_c1)
    links.new(n_pramp.outputs["Color"], m_c2)

    shader_out = _append_1997_depth_fog_and_ambient(nodes, links, ground_col, None, props)
    links.new(shader_out, n_out.inputs["Surface"])
    return mat


def build_ps1_kg_market_stall_material(props: Any) -> Any:
    """
    P1 (`c8ee9253.webp`): Dark weathered timber market stall with rich crimson cloth/vinyl apron!
    """
    mat, nodes, links = _get_or_create_material("SDS_Mat_KG_MarketStall")
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (1440, 100)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-1140, 120)
    snap_vec = _build_ps1_texel_coord(
        nodes, links, n_coord.outputs["Object"], scale_xyz=(1.0, 1.0, 1.0), texel_res=32.0, affine_shear=0.15, loc_x=-880.0, loc_y=120.0
    )

    n_sep = nodes.new("ShaderNodeSeparateXYZ")
    n_sep.location = (-240, 120)
    links.new(snap_vec, n_sep.inputs["Vector"])

    # Upper counter shelf (z > 0.82) is dark wood, lower apron (z <= 0.82) is weathered dark crimson cloth
    n_is_wood = nodes.new("ShaderNodeMath")
    n_is_wood.operation = "GREATER_THAN"
    n_is_wood.location = (20, 180)
    n_is_wood.inputs[1].default_value = 0.82
    links.new(n_sep.outputs["Z"], n_is_wood.inputs[0])

    _, m_fac, m_c1, m_c2, stall_col = _new_mix_color(nodes, links, location=(280, 120))
    m_c1.default_value = (0.52, 0.09, 0.07, 1.0)  # Weathered dark crimson vinyl apron
    m_c2.default_value = (0.16, 0.11, 0.07, 1.0)  # Dark aged timber counter top
    links.new(n_is_wood.outputs["Value"], m_fac)

    shader_out = _append_1997_depth_fog_and_ambient(nodes, links, stall_col, None, props)
    links.new(shader_out, n_out.inputs["Surface"])
    return mat


def build_ps1_kg_signboard_material(props: Any, variant: int = 0) -> Any:
    """
    P1 & P2 (`冷飲熱品 馬龍` / `擺設金鋪`):
    - Backlit Hong Kong acrylic lightbox (#fcf4d4) with dark metal frame
    - Crisp, beautiful traditional red & teal Chinese calligraphy characters that glow softly!
    """
    mat, nodes, links = _get_or_create_material(f"SDS_Mat_KG_Signboard_{variant}")
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (1180, 100)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-980, 120)
    snap_vec = _build_ps1_texel_coord(
        nodes, links, n_coord.outputs["Generated"], scale_xyz=(1.0, 1.0, 1.0), texel_res=24.0, affine_shear=0.08, loc_x=-720.0, loc_y=120.0
    )

    # 1. Outer Dark Metal Lightbox Border (u < 0.08 or u > 0.92 or v < 0.12 or v > 0.88)
    n_vor_box = nodes.new("ShaderNodeTexVoronoi")
    n_vor_box.location = (-180, 240)
    if hasattr(n_vor_box, "distance"):
        try:
            n_vor_box.distance = "CHEBYSHEV"
        except Exception:
            pass
    set_socket(n_vor_box, ("Scale",), 1.0)
    set_socket(n_vor_box, ("Randomness",), 0.0)
    links.new(snap_vec, n_vor_box.inputs["Vector"])

    n_is_metal_rim = nodes.new("ShaderNodeMath")
    n_is_metal_rim.operation = "GREATER_THAN"
    n_is_metal_rim.location = (60, 240)
    n_is_metal_rim.inputs[1].default_value = 0.44
    links.new(n_vor_box.outputs["Distance"], n_is_metal_rim.inputs[0])

    # 2. Chinese calligraphy character stroke noise
    n_char_ns = nodes.new("ShaderNodeTexNoise")
    n_char_ns.location = (-180, -40)
    set_socket(n_char_ns, ("Scale",), 9.5)
    set_socket(n_char_ns, ("Detail",), 2.0)
    links.new(snap_vec, n_char_ns.inputs["Vector"])

    n_is_char = nodes.new("ShaderNodeMath")
    n_is_char.operation = "GREATER_THAN"
    n_is_char.location = (60, -40)
    n_is_char.inputs[1].default_value = 0.54
    links.new(n_char_ns.outputs["Fac"], n_is_char.inputs[0])

    # Inner acrylic plate with calligraphy
    _, m_cfac, m_cc1, m_cc2, face_col = _new_mix_color(nodes, links, location=(300, 60))
    m_cc1.default_value = (0.96, 0.92, 0.78, 1.0)  # Backlit warm cream acrylic plate
    # Variant 0: Stenciled red calligraphy `擺設金鋪`; Variant 1: Stenciled crimson/teal calligraphy `冷飲熱品`
    m_cc2.default_value = (0.82, 0.12, 0.08, 1.0) if variant == 0 else (0.12, 0.48, 0.52, 1.0)
    links.new(n_is_char.outputs["Value"], m_cfac)

    # Frame outer dark metal border
    _, m_rfac, m_rc1, m_rc2, sign_col = _new_mix_color(nodes, links, location=(540, 100))
    m_rc2.default_value = (0.06, 0.07, 0.08, 1.0)  # Dark bronze/black metal box rim
    links.new(n_is_metal_rim.outputs["Value"], m_rfac)
    links.new(face_col, m_rc1)

    # Soft self-illumination emission so lightbox glows in the dark alley!
    n_emit = nodes.new("ShaderNodeEmission")
    n_emit.location = (840, 100)
    set_socket(n_emit, ("Strength",), 1.85)
    links.new(sign_col, n_emit.inputs["Color"])
    links.new(n_emit.outputs["Emission"], n_out.inputs["Surface"])
    return mat


def build_ps1_lowpoly_terrain_material(props: Any) -> Any:
    """
    Authentic 1996-1998 PS1 Nearest-Neighbor Pixelated & Color-Quantized Terrain Material:
    - Uses `_build_ps1_texel_coord` (`VectorMath -> SNAP` at 0.25m texel grid + affine UV warp)
    - Uses `CONSTANT` stepped ColorRamps (zero smooth gradients) and zero specular.
    """
    mat, nodes, links = _get_or_create_material("SDS_Mat_Terrain")
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (960, 100)

    low_c = getattr(props, "terrain_low_color", (0.12, 0.34, 0.10))
    mid_c = getattr(props, "terrain_mid_color", (0.42, 0.30, 0.18))
    high_c = getattr(props, "terrain_high_color", (0.78, 0.76, 0.72))

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-1140, 120)
    snap_out = _build_ps1_texel_coord(nodes, links, n_coord.outputs["Object"], texel_res=32.0, affine_shear=0.45 * (max(0.0, float(getattr(props, "ps1_affine_warp", 65.0))) / 65.0), loc_x=-920.0, loc_y=120.0)

    n_sep = nodes.new("ShaderNodeSeparateXYZ")
    n_sep.location = (-620, 260)
    links.new(snap_out, n_sep.inputs["Vector"])

    n_noise = nodes.new("ShaderNodeTexNoise")
    n_noise.location = (-620, -20)
    set_socket(n_noise, ("Scale",), 4.5)
    set_socket(n_noise, ("Detail",), 0.0)
    links.new(snap_out, n_noise.inputs["Vector"])

    n_math = nodes.new("ShaderNodeMath")
    n_math.operation = "MULTIPLY_ADD"
    n_math.location = (-360, 120)
    n_math.inputs[1].default_value = 0.16
    links.new(n_sep.outputs["Z"], n_math.inputs[0])
    links.new(n_noise.outputs["Fac"], n_math.inputs[2])

    n_ramp = nodes.new("ShaderNodeValToRGB")
    n_ramp.location = (-80, 120)
    n_ramp.color_ramp.interpolation = "CONSTANT"
    el = n_ramp.color_ramp.elements
    el[0].position = 0.0
    el[0].color = _scale_rgb(low_c, 0.65)
    el[1].position = 0.28
    el[1].color = _rgba(low_c)
    e2 = el.new(0.55)
    e2.color = _rgba(mid_c)
    e3 = el.new(0.80)
    e3.color = _rgba(high_c)
    links.new(n_math.outputs["Value"], n_ramp.inputs["Fac"])

    shader_out = _append_1997_depth_fog_and_ambient(
        nodes,
        links,
        base_color_socket=n_ramp.outputs["Color"],
        normal_socket=None,
        props=props,
        specular_weight=0.0,
        roughness=1.0,
    )
    links.new(shader_out, n_out.inputs["Surface"])
    return mat


def build_ps2_ico_stone_material(props: Any, variant: int = 0) -> Any:
    """
    PS2 *ICO* (2001) Weathered Sunlit Sandstone / Ashlar Viaduct Material (`sJugHxmS...jpg`):
    - Combines perspective-correct running-bond stone courses (`ShaderNodeTexBrick`)
      with vertical dark moss/soot moisture streaks at lower elevations and warm sunlit
      ochre/cream highlights on upper parapets.
    """
    mat, nodes, links = _get_or_create_material(f"SDS_Mat_PS2_ICO_Stone_{variant}")
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (980, 100)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-920, 120)

    n_sep = nodes.new("ShaderNodeSeparateXYZ")
    n_sep.location = (-680, -140)
    links.new(n_coord.outputs["Object"], n_sep.inputs["Vector"])

    n_brick = nodes.new("ShaderNodeTexBrick")
    n_brick.location = (-640, 220)
    n_brick.offset = 0.5
    n_brick.squash = 1.8
    set_socket(n_brick, ("Scale",), 3.6 if variant == 0 else 4.8)
    set_socket(n_brick, ("Mortar Size",), 0.025)
    set_socket(n_brick, ("Mortar Smooth",), 0.15)
    if variant == 0:
        # Warm sunlit sandstone viaduct & staircase blocks
        set_socket(n_brick, ("Color1",), (0.68, 0.60, 0.44, 1.0))
        set_socket(n_brick, ("Color2",), (0.54, 0.47, 0.34, 1.0))
        set_socket(n_brick, ("Mortar",), (0.24, 0.21, 0.15, 1.0))
    else:
        # Darker weathered cliff bastion & lower pier stone
        set_socket(n_brick, ("Color1",), (0.52, 0.46, 0.34, 1.0))
        set_socket(n_brick, ("Color2",), (0.38, 0.34, 0.25, 1.0))
        set_socket(n_brick, ("Mortar",), (0.16, 0.15, 0.11, 1.0))
    links.new(n_coord.outputs["Object"], n_brick.inputs["Vector"])

    # Vertical weathering & dark moss streaks
    n_noise = nodes.new("ShaderNodeTexNoise")
    n_noise.location = (-640, -60)
    set_socket(n_noise, ("Scale",), 5.5)
    set_socket(n_noise, ("Detail",), 4.0)
    set_socket(n_noise, ("Roughness",), 0.65)
    links.new(n_coord.outputs["Object"], n_noise.inputs["Vector"])

    n_weath_ramp = nodes.new("ShaderNodeValToRGB")
    n_weath_ramp.location = (-360, -60)
    el = n_weath_ramp.color_ramp.elements
    el[0].position = 0.32
    el[0].color = (0.16, 0.18, 0.12, 1.0)
    el[1].position = 0.72
    el[1].color = (0.86, 0.80, 0.64, 1.0)
    links.new(n_noise.outputs["Fac"], n_weath_ramp.inputs["Fac"])

    _, m_fac, m_c1, m_c2, m_out = _new_mix_color(nodes, links, blend_type="MULTIPLY", location=(-40, 140))
    m_fac.default_value = 0.58
    links.new(n_brick.outputs["Color"], m_c1)
    links.new(n_weath_ramp.outputs["Color"], m_c2)

    n_bump = nodes.new("ShaderNodeBump")
    n_bump.location = (220, -140)
    set_socket(n_bump, ("Strength",), 0.35)
    set_socket(n_bump, ("Distance",), 0.04)
    links.new(n_brick.outputs["Fac"], n_bump.inputs["Height"])

    shader_out = _append_1997_depth_fog_and_ambient(
        nodes,
        links,
        base_color_socket=m_out,
        normal_socket=n_bump.outputs["Normal"],
        props=props,
        specular_weight=0.12,
        roughness=0.55,
    )
    links.new(shader_out, n_out.inputs["Surface"])
    return mat


def build_ps2_ico_iron_railing_material(props: Any) -> Any:
    """Dark weathered wrought-iron fence railing material for PS2 *ICO* castle bridge."""
    mat, nodes, links = _get_or_create_material("SDS_Mat_PS2_ICO_Iron")
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (620, 100)

    n_rgb = nodes.new("ShaderNodeRGB")
    n_rgb.location = (-180, 120)
    n_rgb.outputs[0].default_value = (0.09, 0.10, 0.09, 1.0)

    shader_out = _append_1997_depth_fog_and_ambient(
        nodes,
        links,
        base_color_socket=n_rgb.outputs["Color"],
        normal_socket=None,
        props=props,
        specular_weight=0.35,
        roughness=0.32,
    )
    links.new(shader_out, n_out.inputs["Surface"])
    return mat


def build_dc_waterfall_cliff_material(props: Any) -> Any:
    """
    Sega Dreamcast / PowerVR2 (1999) Waterfall Cliff Arena Material (`-UPttAsJ...jpg`):
    - Crisp perspective-correct trilinear-filtered vertical cyan-white waterfall streams
      cascading down dark teal-indigo canyon walls.
    """
    mat, nodes, links = _get_or_create_material("SDS_Mat_DC_WaterfallCliff")
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (980, 100)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-920, 120)

    n_map = nodes.new("ShaderNodeMapping")
    n_map.location = (-700, 120)
    # Stretch strongly along Z so noise forms vertical cascading waterfall ribbons
    n_map.inputs["Scale"].default_value = (3.8, 3.8, 0.32)
    links.new(n_coord.outputs["Object"], n_map.inputs["Vector"])

    n_noise = nodes.new("ShaderNodeTexNoise")
    n_noise.location = (-460, 120)
    sharp = max(0.0, min(100.0, float(getattr(props, "dc_trilinear_sharpness", 85.0)))) / 100.0
    set_socket(n_noise, ("Scale",), 2.8 + sharp * 1.5)
    set_socket(n_noise, ("Detail",), 5.0)
    set_socket(n_noise, ("Roughness",), 0.55)
    links.new(n_map.outputs["Vector"], n_noise.inputs["Vector"])

    n_ramp = nodes.new("ShaderNodeValToRGB")
    n_ramp.location = (-180, 120)
    el = n_ramp.color_ramp.elements
    el[0].position = 0.25
    el[0].color = (0.04, 0.16, 0.28, 1.0)  # Deep wet teal-indigo cliff rock
    el[1].position = 0.72
    el[1].color = (0.85, 0.98, 1.00, 1.0)  # Foaming white-cyan waterfall stream
    e_mid = el.new(0.48)
    e_mid.color = (0.14, 0.62, 0.82, 1.0)  # Vivid cyan cascade
    links.new(n_noise.outputs["Fac"], n_ramp.inputs["Fac"])

    shader_out = _append_1997_depth_fog_and_ambient(
        nodes,
        links,
        base_color_socket=n_ramp.outputs["Color"],
        normal_socket=None,
        props=props,
        specular_weight=0.65,
        roughness=0.18,
    )
    links.new(shader_out, n_out.inputs["Surface"])
    return mat


def build_dc_sluice_tower_material(props: Any) -> Any:
    """
    Sega Dreamcast / PowerVR2 Bronze-Gold Industrial Sluice Tower Material (`-UPttAsJ...jpg`):
    - Metallic bronze/amber-gold vertical structural ribs with dark recessed mechanical vents.
    """
    mat, nodes, links = _get_or_create_material("SDS_Mat_DC_SluiceTower")
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (940, 100)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-840, 120)

    n_brick = nodes.new("ShaderNodeTexBrick")
    n_brick.location = (-560, 120)
    n_brick.offset = 0.0
    n_brick.squash = 0.65
    set_socket(n_brick, ("Scale",), 4.2)
    set_socket(n_brick, ("Mortar Size",), 0.06)
    set_socket(n_brick, ("Color1",), (0.78, 0.56, 0.18, 1.0))  # Warm bronze-gold armor plate
    set_socket(n_brick, ("Color2",), (0.52, 0.36, 0.10, 1.0))  # Aged brass panel
    set_socket(n_brick, ("Mortar",), (0.10, 0.08, 0.06, 1.0))  # Dark mechanical seam/vent
    links.new(n_coord.outputs["Object"], n_brick.inputs["Vector"])

    shader_out = _append_1997_depth_fog_and_ambient(
        nodes,
        links,
        base_color_socket=n_brick.outputs["Color"],
        normal_socket=None,
        props=props,
        specular_weight=0.88,
        roughness=0.16,
    )
    links.new(shader_out, n_out.inputs["Surface"])
    return mat


def build_dc_biolum_rock_material(props: Any) -> Any:
    """
    Sega Dreamcast Right-Side Cliff Outcrop with Vivid Emerald-Green Gouraud Vertex Lighting (`-UPttAsJ...jpg`).
    """
    mat, nodes, links = _get_or_create_material("SDS_Mat_DC_BiolumRock")
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (920, 100)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-780, 120)

    n_noise = nodes.new("ShaderNodeTexNoise")
    n_noise.location = (-520, 120)
    set_socket(n_noise, ("Scale",), 3.2)
    set_socket(n_noise, ("Detail",), 3.0)
    links.new(n_coord.outputs["Object"], n_noise.inputs["Vector"])

    n_ramp = nodes.new("ShaderNodeValToRGB")
    n_ramp.location = (-240, 120)
    el = n_ramp.color_ramp.elements
    el[0].position = 0.25
    el[0].color = (0.04, 0.28, 0.14, 1.0)
    el[1].position = 0.72
    el[1].color = (0.12, 0.96, 0.38, 1.0)  # Vivid Dreamcast emerald-green vertex-lit rock
    links.new(n_noise.outputs["Fac"], n_ramp.inputs["Fac"])

    shader_out = _append_1997_depth_fog_and_ambient(
        nodes,
        links,
        base_color_socket=n_ramp.outputs["Color"],
        normal_socket=None,
        props=props,
        specular_weight=0.55,
        roughness=0.22,
    )
    links.new(shader_out, n_out.inputs["Surface"])
    return mat


def build_dc_starfighter_hull_material(props: Any) -> Any:
    """
    Sega Dreamcast / PowerVR2 Spherical Environment Mapped (`GL_SPHERE_MAP`) Starfighter Hull (`d.txt` Section 3).
    """
    mat, nodes, links = _get_or_create_material("SDS_Mat_DC_StarfighterHull")
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (920, 100)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-780, 120)

    n_sep = nodes.new("ShaderNodeSeparateXYZ")
    n_sep.location = (-540, 120)
    links.new(n_coord.outputs["Reflection"], n_sep.inputs["Vector"])

    n_ramp = nodes.new("ShaderNodeValToRGB")
    n_ramp.location = (-260, 120)
    el = n_ramp.color_ramp.elements
    el[0].position = 0.0
    el[0].color = (0.12, 0.22, 0.45, 1.0)
    el[1].position = 1.0
    el[1].color = (0.92, 0.98, 1.00, 1.0)
    e_mid = el.new(0.48)
    e_mid.color = (0.42, 0.68, 0.95, 1.0)
    links.new(n_sep.outputs["Z"], n_ramp.inputs["Fac"])

    shader_out = _append_1997_depth_fog_and_ambient(
        nodes,
        links,
        base_color_socket=n_ramp.outputs["Color"],
        normal_socket=None,
        props=props,
        specular_weight=1.0,
        roughness=0.04,
    )
    links.new(shader_out, n_out.inputs["Surface"])
    return mat


def build_dc_powervr_thruster_glow_material(props: Any, color_mode: str = "CYAN") -> Any:
    """
    Sega Dreamcast / NEC PowerVR2 Hardware Order-Independent Translucent Alpha-Blended Glow (`d.txt` Section 4):
    - Combines `ShaderNodeBsdfTransparent` + high-intensity `ShaderNodeEmission` driven by radial
      object-space falloff so layered thruster/target sprites glow with authentic 1999 additive halo.
    """
    mat, nodes, links = _get_or_create_material(f"SDS_Mat_DC_PowerVR_Glow_{color_mode}")
    if hasattr(mat, "blend_method"):
        try:
            mat.blend_method = "BLEND"
        except Exception:
            pass

    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (780, 100)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-680, 120)

    n_len = nodes.new("ShaderNodeVectorMath")
    n_len.operation = "LENGTH"
    n_len.location = (-440, 120)
    links.new(n_coord.outputs["Object"], n_len.inputs[0])

    n_ramp = nodes.new("ShaderNodeValToRGB")
    n_ramp.location = (-180, 120)
    el = n_ramp.color_ramp.elements
    if color_mode == "CYAN":
        el[0].position = 0.0
        el[0].color = (0.95, 1.00, 1.00, 1.0)  # White-hot core
        el[1].position = 0.95
        el[1].color = (0.0, 0.35, 0.95, 1.0)   # Deep electric cyan halo
        e_mid = el.new(0.45)
        e_mid.color = (0.15, 0.92, 1.00, 1.0)
    elif color_mode == "MIST":
        el[0].position = 0.0
        el[0].color = (0.88, 0.98, 1.00, 1.0)  # Dense white-cyan waterfall spray core
        el[1].position = 0.95
        el[1].color = (0.12, 0.58, 0.82, 1.0)  # Translucent teal-cyan mist edge
    else:
        el[0].position = 0.0
        el[0].color = (1.00, 0.96, 0.35, 1.0)  # Bright yellow target core
        el[1].position = 0.95
        el[1].color = (0.85, 0.12, 0.78, 1.0)  # Magenta-purple outer target ring
    links.new(n_len.outputs["Value"], n_ramp.inputs["Fac"])

    glow_pct = max(10.0, min(100.0, float(getattr(props, "dc_alpha_glow", 85.0)))) / 100.0
    n_emit = nodes.new("ShaderNodeEmission")
    n_emit.location = (160, 180)
    set_socket(n_emit, ("Strength",), 3.5 + glow_pct * 5.5)
    links.new(n_ramp.outputs["Color"], n_emit.inputs["Color"])

    n_trans = nodes.new("ShaderNodeBsdfTransparent")
    n_trans.location = (160, -20)

    n_mix = nodes.new("ShaderNodeMixShader")
    n_mix.location = (460, 100)
    n_mix.inputs["Fac"].default_value = 0.78
    links.new(n_trans.outputs["BSDF"], n_mix.inputs[1])
    links.new(n_emit.outputs["Emission"], n_mix.inputs[2])
    links.new(n_mix.outputs["Shader"], n_out.inputs["Surface"])
    return mat


def build_ps2_gs_sunshaft_material(props: Any) -> Any:
    """
    PS2 Graphics Synthesizer (GS) Multi-Pass eDRAM Alpha-Blended Volumetric Sun-Shaft / Mist Card (`c.txt` Section 2):
    - PS2 lacked programmable pixel shaders but had 48 GB/s eDRAM fillrate, so games like *ICO* (2001)
      and *Shadow of the Colossus* (2005) rendered slanted semi-transparent light-beam planes in 3D space!
    """
    mat, nodes, links = _get_or_create_material("SDS_Mat_PS2_GS_SunShaft")
    if hasattr(mat, "blend_method"):
        try:
            mat.blend_method = "BLEND"
        except Exception:
            pass

    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (740, 100)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-640, 120)

    n_sep = nodes.new("ShaderNodeSeparateXYZ")
    n_sep.location = (-420, 120)
    links.new(n_coord.outputs["Generated"], n_sep.inputs["Vector"])

    n_ramp = nodes.new("ShaderNodeValToRGB")
    n_ramp.location = (-180, 120)
    el = n_ramp.color_ramp.elements
    el[0].position = 0.0
    el[0].color = (0.98, 0.95, 0.80, 1.0)
    el[1].position = 1.0
    el[1].color = (0.72, 0.76, 0.68, 1.0)
    links.new(n_sep.outputs["Z"], n_ramp.inputs["Fac"])

    bloom_pct = max(10.0, min(100.0, float(getattr(props, "ps2_bloom_intensity", 78.0)))) / 100.0
    n_emit = nodes.new("ShaderNodeEmission")
    n_emit.location = (140, 180)
    set_socket(n_emit, ("Strength",), 0.85 + bloom_pct * 1.45)
    links.new(n_ramp.outputs["Color"], n_emit.inputs["Color"])

    n_trans = nodes.new("ShaderNodeBsdfTransparent")
    n_trans.location = (140, -20)

    n_mix = nodes.new("ShaderNodeMixShader")
    n_mix.location = (440, 100)
    n_mix.inputs["Fac"].default_value = 0.22 + bloom_pct * 0.16
    links.new(n_trans.outputs["BSDF"], n_mix.inputs[1])
    links.new(n_emit.outputs["Emission"], n_mix.inputs[2])
    links.new(n_mix.outputs["Shader"], n_out.inputs["Surface"])
    return mat


# ===========================================================================
# v3.9 — HIGH-CLARITY PS1 PIXEL-ART &《LSD: DREAM EMULATOR》SHADERS
# ===========================================================================
def build_ps1_lsd_bullseye_tile_material(props: Any, is_turtle: bool = False) -> Any:
    """
    Ref Image 1 (`e53fb9d1...jpg`):
    - Strictly rectangular square tiles (`Voronoi CHEBYSHEV` with `Randomness=0.0` for crisp
      1-texel electric-cyan square tile frames) + `Voronoi EUCLIDEAN` (`Randomness=0.0`) for
      razor-sharp `32x32` concentric pixelated rainbow bullseye rings inside every square tile!
    """
    if is_turtle:
        return build_ps1_lsd_turtle_carapace_material(props)

    mat, nodes, links = _get_or_create_material("SDS_Mat_LSD_BullseyeTiles")
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (1580, 100)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-1320, 120)
    warp_scale = max(0.0, float(getattr(props, "ps1_affine_warp", 75.0))) / 65.0
    snap_vec = _build_ps1_texel_coord(
        nodes,
        links,
        n_coord.outputs["Object"],
        scale_xyz=(0.72, 0.72, 0.72),
        texel_res=28.0,
        affine_shear=0.35 * warp_scale,
        loc_x=-1040.0,
        loc_y=120.0,
    )

    # 1. Square Box Frame (`CHEBYSHEV`, Randomness=0.0) -> Distance > 0.41 is the crisp Cyan square frame!
    n_vor_box = nodes.new("ShaderNodeTexVoronoi")
    n_vor_box.location = (-360, 280)
    if hasattr(n_vor_box, "distance"):
        try:
            n_vor_box.distance = "CHEBYSHEV"
        except Exception:
            pass
    set_socket(n_vor_box, ("Scale",), 1.0)
    set_socket(n_vor_box, ("Randomness",), 0.0)
    links.new(snap_vec, n_vor_box.inputs["Vector"])

    n_is_border = nodes.new("ShaderNodeMath")
    n_is_border.operation = "GREATER_THAN"
    n_is_border.location = (-80, 280)
    n_is_border.inputs[1].default_value = 0.41
    links.new(n_vor_box.outputs["Distance"], n_is_border.inputs[0])

    # 2. Concentric Circular Bullseye Rings (`EUCLIDEAN`, Randomness=0.0) inside each square tile
    n_vor_rad = nodes.new("ShaderNodeTexVoronoi")
    n_vor_rad.location = (-360, -20)
    if hasattr(n_vor_rad, "distance"):
        try:
            n_vor_rad.distance = "EUCLIDEAN"
        except Exception:
            pass
    set_socket(n_vor_rad, ("Scale",), 1.0)
    set_socket(n_vor_rad, ("Randomness",), 0.0)
    links.new(snap_vec, n_vor_rad.inputs["Vector"])

    # Per-tile deterministic color-table shift from cell hash (`Voronoi.Color.X`)
    n_sep_cell = nodes.new("ShaderNodeSeparateXYZ")
    n_sep_cell.location = (-120, -220)
    links.new(n_vor_rad.outputs["Color"], n_sep_cell.inputs["Vector"])

    n_ring_val = nodes.new("ShaderNodeMath")
    n_ring_val.operation = "MULTIPLY_ADD"
    n_ring_val.location = (80, -20)
    n_ring_val.inputs[1].default_value = 1.65
    links.new(n_vor_rad.outputs["Distance"], n_ring_val.inputs[0])
    links.new(n_sep_cell.outputs["X"], n_ring_val.inputs[2])

    n_mod = nodes.new("ShaderNodeMath")
    n_mod.operation = "MODULO"
    n_mod.location = (260, -20)
    n_mod.inputs[1].default_value = 1.0
    links.new(n_ring_val.outputs["Value"], n_mod.inputs[0])

    n_ramp = nodes.new("ShaderNodeValToRGB")
    n_ramp.location = (460, -20)
    n_ramp.color_ramp.interpolation = "CONSTANT"
    el = n_ramp.color_ramp.elements
    el[0].position = 0.00
    el[0].color = (1.00, 0.94, 0.04, 1.0)  # Vivid yellow bullseye center
    el[1].position = 0.16
    el[1].color = (0.98, 0.42, 0.02, 1.0)  # Bright orange inner ring
    e2 = el.new(0.32)
    e2.color = (0.92, 0.04, 0.28, 1.0)     # Crimson-magenta ring
    e3 = el.new(0.48)
    e3.color = (0.28, 0.10, 0.86, 1.0)     # Deep royal-indigo ring
    e4 = el.new(0.66)
    e4.color = (0.38, 0.88, 0.04, 1.0)     # Acid lime-green ring
    e5 = el.new(0.82)
    e5.color = (0.86, 0.08, 0.48, 1.0)     # Deep rose-magenta outer ring
    links.new(n_mod.outputs["Value"], n_ramp.inputs["Fac"])

    # Mix square cyan tile border (`#00A8F2`) over the concentric bullseye rings
    _, b_fac, b_c1, b_c2, tile_col = _new_mix_color(nodes, links, location=(760, 120))
    b_c2.default_value = (0.00, 0.68, 0.96, 1.0)  # Crisp 1-texel Electric Cyan Square Tile Frame
    links.new(n_is_border.outputs["Value"], b_fac)
    links.new(n_ramp.outputs["Color"], b_c1)

    shader_out = _append_1997_depth_fog_and_ambient(
        nodes, links, tile_col, None, props, specular_weight=0.0, roughness=1.0
    )
    links.new(shader_out, n_out.inputs["Surface"])
    return mat


def build_ps1_lsd_turtle_carapace_material(props: Any, is_rim: bool = False) -> Any:
    """
    Ref Image 1 (`e53fb9d1...jpg`) Turtle Shell Material:
    - Upper Carapace (`is_rim=False`): Crisp pixelated lavender/purple/white/crimson eyeball spots & green patches
    - Lower Rim (`is_rim=True`): Vertical purple, pink, maroon & teal barcode stripes!
    """
    mat_name = "SDS_Mat_LSD_TurtleRim" if is_rim else "SDS_Mat_LSD_TurtleShell"
    mat, nodes, links = _get_or_create_material(mat_name)
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (1480, 100)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-1240, 120)
    sc = (2.4, 2.4, 0.25) if is_rim else (1.15, 1.15, 1.15)
    snap_vec = _build_ps1_texel_coord(
        nodes, links, n_coord.outputs["Object"], scale_xyz=sc, texel_res=24.0, affine_shear=0.25, loc_x=-980.0, loc_y=120.0
    )

    n_vor = nodes.new("ShaderNodeTexVoronoi")
    n_vor.location = (-320, 120)
    set_socket(n_vor, ("Scale",), 1.8 if is_rim else 1.4)
    set_socket(n_vor, ("Randomness",), 0.15 if is_rim else 0.35)
    links.new(snap_vec, n_vor.inputs["Vector"])

    n_ramp = nodes.new("ShaderNodeValToRGB")
    n_ramp.location = (40, 120)
    n_ramp.color_ramp.interpolation = "CONSTANT"
    el = n_ramp.color_ramp.elements
    if not is_rim:
        # Eyeball-spot pattern: dark pupil -> white sclera -> crimson iris ring -> lavender/purple shell -> green accent
        el[0].position = 0.00
        el[0].color = (0.18, 0.02, 0.08, 1.0)
        el[1].position = 0.14
        el[1].color = (0.94, 0.90, 0.96, 1.0)
        e2 = el.new(0.28)
        e2.color = (0.78, 0.14, 0.22, 1.0)
        e3 = el.new(0.46)
        e3.color = (0.68, 0.32, 0.88, 1.0)
        e4 = el.new(0.72)
        e4.color = (0.48, 0.18, 0.68, 1.0)
        e5 = el.new(0.86)
        e5.color = (0.16, 0.76, 0.38, 1.0)
    else:
        # Vertical barcode stripes on shell rim
        el[0].position = 0.00
        el[0].color = (0.28, 0.08, 0.24, 1.0)
        el[1].position = 0.25
        el[1].color = (0.68, 0.34, 0.76, 1.0)
        e2 = el.new(0.50)
        e2.color = (0.54, 0.16, 0.22, 1.0)
        e3 = el.new(0.75)
        e3.color = (0.14, 0.52, 0.48, 1.0)
    links.new(n_vor.outputs["Distance"], n_ramp.inputs["Fac"])

    shader_out = _append_1997_depth_fog_and_ambient(
        nodes, links, n_ramp.outputs["Color"], None, props, specular_weight=0.0, roughness=1.0
    )
    links.new(shader_out, n_out.inputs["Surface"])
    return mat


def build_ps1_lsd_turtle_limb_material(props: Any, is_indigo: bool = False) -> Any:
    """Dark Teal-Green & Deep Indigo-Purple pixelated prism material for the LSD Turtle's legs and head."""
    mat_name = "SDS_Mat_LSD_TurtleLimb_Indigo" if is_indigo else "SDS_Mat_LSD_TurtleLimb_Teal"
    mat, nodes, links = _get_or_create_material(mat_name)
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (1420, 100)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-1140, 120)
    snap_vec = _build_ps1_texel_coord(
        nodes, links, n_coord.outputs["Object"], scale_xyz=(1.2, 1.2, 1.2), texel_res=24.0, affine_shear=0.15, loc_x=-880.0, loc_y=120.0
    )

    n_noise = nodes.new("ShaderNodeTexNoise")
    n_noise.location = (-240, 120)
    set_socket(n_noise, ("Scale",), 3.5)
    set_socket(n_noise, ("Detail",), 1.0)
    links.new(snap_vec, n_noise.inputs["Vector"])

    n_ramp = nodes.new("ShaderNodeValToRGB")
    n_ramp.location = (40, 120)
    n_ramp.color_ramp.interpolation = "CONSTANT"
    el = n_ramp.color_ramp.elements
    if is_indigo:
        el[0].position = 0.0
        el[0].color = (0.14, 0.04, 0.36, 1.0)
        el[1].position = 0.52
        el[1].color = (0.24, 0.08, 0.56, 1.0)
    else:
        el[0].position = 0.0
        el[0].color = (0.04, 0.34, 0.32, 1.0)
        el[1].position = 0.52
        el[1].color = (0.08, 0.54, 0.48, 1.0)
    links.new(n_noise.outputs["Fac"], n_ramp.inputs["Fac"])

    shader_out = _append_1997_depth_fog_and_ambient(
        nodes, links, n_ramp.outputs["Color"], None, props, specular_weight=0.0, roughness=1.0
    )
    links.new(shader_out, n_out.inputs["Surface"])
    return mat


def build_ps1_lsd_kanji_giant_material(props: Any, role: str = "BODY") -> Any:
    """
    New Ref Image 2 (`image_33a178.png`):
    - `BODY`: Glowing electric purple-magenta monument skin with crisp orange-gold pixelated Kanji glyph grid rows!
    - `EYE`: Recessed glowing emerald-green iris & black pupil with dark purple eyelid rim!
    - `GREEN_BLUE_TILE`: Square ground tiles with neon-green, cobalt-blue & white pixelated organic waves!
    - `MOSS_WALL`: Crunchy pixelated dark-green & brown mossy compound wall!
    """
    mat, nodes, links = _get_or_create_material(f"SDS_Mat_LSD_Kanji_{role}")
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (1520, 100)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-1240, 120)

    if role == "EYE":
        snap_vec = _build_ps1_texel_coord(
            nodes, links, n_coord.outputs["Generated"], scale_xyz=(1.0, 1.0, 1.0), texel_res=24.0, affine_shear=0.0, loc_x=-940.0, loc_y=120.0
        )
        n_vor = nodes.new("ShaderNodeTexVoronoi")
        n_vor.location = (-260, 120)
        set_socket(n_vor, ("Scale",), 1.0)
        set_socket(n_vor, ("Randomness",), 0.0)
        links.new(snap_vec, n_vor.inputs["Vector"])

        n_ramp = nodes.new("ShaderNodeValToRGB")
        n_ramp.location = (40, 120)
        n_ramp.color_ramp.interpolation = "CONSTANT"
        el = n_ramp.color_ramp.elements
        el[0].position = 0.00
        el[0].color = (0.02, 0.14, 0.04, 1.0)  # Dark pupil center
        el[1].position = 0.16
        el[1].color = (0.12, 0.94, 0.24, 1.0)  # Vivid emerald-green iris
        e2 = el.new(0.36)
        e2.color = (0.88, 0.94, 0.88, 1.0)     # White sclera rim
        e3 = el.new(0.48)
        e3.color = (0.18, 0.04, 0.24, 1.0)     # Dark purple eye socket
        links.new(n_vor.outputs["Distance"], n_ramp.inputs["Fac"])

        shader_out = _append_1997_depth_fog_and_ambient(nodes, links, n_ramp.outputs["Color"], None, props)
        links.new(shader_out, n_out.inputs["Surface"])
        return mat

    if role == "BODY":
        snap_vec = _build_ps1_texel_coord(
            nodes, links, n_coord.outputs["Object"], scale_xyz=(0.85, 0.85, 0.85), texel_res=28.0, affine_shear=0.15, loc_x=-940.0, loc_y=120.0
        )
        # Create grid of character cells (`Brick`) modulated by high-frequency glyph stroke noise (`Noise`)
        n_brick = nodes.new("ShaderNodeTexBrick")
        n_brick.location = (-360, 220)
        n_brick.offset = 0.0
        n_brick.squash = 1.0
        set_socket(n_brick, ("Scale",), 1.45)
        set_socket(n_brick, ("Mortar Size",), 0.14)
        set_socket(n_brick, ("Mortar Smooth",), 0.0)
        set_socket(n_brick, ("Color1",), (1.0, 1.0, 1.0, 1.0))
        set_socket(n_brick, ("Color2",), (1.0, 1.0, 1.0, 1.0))
        set_socket(n_brick, ("Mortar",), (0.0, 0.0, 0.0, 1.0))
        links.new(snap_vec, n_brick.inputs["Vector"])

        n_glyph = nodes.new("ShaderNodeTexNoise")
        n_glyph.location = (-360, -40)
        set_socket(n_glyph, ("Scale",), 6.8)
        set_socket(n_glyph, ("Detail",), 2.0)
        links.new(snap_vec, n_glyph.inputs["Vector"])

        n_gt = nodes.new("ShaderNodeMath")
        n_gt.operation = "GREATER_THAN"
        n_gt.location = (-120, -40)
        n_gt.inputs[1].default_value = 0.51
        links.new(n_glyph.outputs["Fac"], n_gt.inputs[0])

        n_mask = nodes.new("ShaderNodeMath")
        n_mask.operation = "MULTIPLY"
        n_mask.location = (120, 120)
        links.new(n_brick.outputs["Fac"], n_mask.inputs[0])
        links.new(n_gt.outputs["Value"], n_mask.inputs[1])

        _, m_fac, m_c1, m_c2, body_col = _new_mix_color(nodes, links, location=(360, 120))
        m_c1.default_value = (0.76, 0.14, 0.96, 1.0)  # Luminous magenta-purple monument skin
        m_c2.default_value = (0.98, 0.64, 0.32, 1.0)  # Glowing orange-gold Kanji character strokes
        links.new(n_mask.outputs["Value"], m_fac)

        shader_out = _append_1997_depth_fog_and_ambient(nodes, links, body_col, None, props)
        links.new(shader_out, n_out.inputs["Surface"])
        return mat

    if role == "MOSS_WALL":
        snap_vec = _build_ps1_texel_coord(
            nodes, links, n_coord.outputs["Object"], scale_xyz=(1.4, 1.4, 1.4), texel_res=24.0, affine_shear=0.20, loc_x=-940.0, loc_y=120.0
        )
        n_ns = nodes.new("ShaderNodeTexNoise")
        n_ns.location = (-280, 120)
        set_socket(n_ns, ("Scale",), 5.5)
        set_socket(n_ns, ("Detail",), 2.0)
        links.new(snap_vec, n_ns.inputs["Vector"])

        n_ramp = nodes.new("ShaderNodeValToRGB")
        n_ramp.location = (20, 120)
        n_ramp.color_ramp.interpolation = "CONSTANT"
        el = n_ramp.color_ramp.elements
        el[0].position = 0.00
        el[0].color = (0.06, 0.14, 0.08, 1.0)
        el[1].position = 0.34
        el[1].color = (0.16, 0.38, 0.16, 1.0)
        e2 = el.new(0.68)
        e2.color = (0.34, 0.28, 0.22, 1.0)
        links.new(n_ns.outputs["Fac"], n_ramp.inputs["Fac"])

        shader_out = _append_1997_depth_fog_and_ambient(nodes, links, n_ramp.outputs["Color"], None, props)
        links.new(shader_out, n_out.inputs["Surface"])
        return mat

    # GREEN_BLUE_TILE: Crisp square ground tiles with neon-green, electric-blue & white pixelated pattern
    snap_vec = _build_ps1_texel_coord(
        nodes, links, n_coord.outputs["Object"], scale_xyz=(0.65, 0.65, 0.65), texel_res=28.0, affine_shear=0.35, loc_x=-940.0, loc_y=120.0
    )
    n_vor = nodes.new("ShaderNodeTexVoronoi")
    n_vor.location = (-320, 180)
    if hasattr(n_vor, "distance"):
        try:
            n_vor.distance = "CHEBYSHEV"
        except Exception:
            pass
    set_socket(n_vor, ("Scale",), 1.0)
    set_socket(n_vor, ("Randomness",), 0.0)
    links.new(snap_vec, n_vor.inputs["Vector"])

    n_wave = nodes.new("ShaderNodeTexWave")
    n_wave.location = (-320, -60)
    set_socket(n_wave, ("Scale",), 1.6)
    set_socket(n_wave, ("Distortion",), 2.8)
    links.new(snap_vec, n_wave.inputs["Vector"])

    n_add = nodes.new("ShaderNodeMath")
    n_add.operation = "MULTIPLY_ADD"
    n_add.location = (-40, 80)
    n_add.inputs[1].default_value = 0.55
    links.new(n_vor.outputs["Distance"], n_add.inputs[0])
    links.new(n_wave.outputs["Fac"], n_add.inputs[2])

    n_ramp = nodes.new("ShaderNodeValToRGB")
    n_ramp.location = (220, 80)
    n_ramp.color_ramp.interpolation = "CONSTANT"
    el = n_ramp.color_ramp.elements
    el[0].position = 0.00
    el[0].color = (0.04, 0.88, 0.14, 1.0)  # Neon green center
    el[1].position = 0.30
    el[1].color = (0.12, 0.56, 0.36, 1.0)  # Teal-green mid
    e2 = el.new(0.52)
    e2.color = (0.82, 0.88, 0.94, 1.0)     # Crisp white-lavender Foam ring
    e3 = el.new(0.68)
    e3.color = (0.14, 0.24, 0.86, 1.0)     # Cobalt-blue outer tile band
    links.new(n_add.outputs["Value"], n_ramp.inputs["Fac"])

    shader_out = _append_1997_depth_fog_and_ambient(nodes, links, n_ramp.outputs["Color"], None, props)
    links.new(shader_out, n_out.inputs["Surface"])
    return mat


def build_ps1_lsd_kyoto_night_material(props: Any, role: str = "SAND_STREET") -> Any:
    """
    New Ref Image 3 (`image_33a151.png` — Kyoto Night Street & Low-Poly Kimono Woman):
    - `SAND_STREET`: Pixelated sandy-beige gravel foreground (`Y < -3.5`) meeting dark slate-blue street (`Y >= -3.5`)
    - `MACHIYA_WALL`: Dark timber frame & crisp white-and-black vertical wooden lattice windows (`Koshi-mado`)
    - `CYAN_ROOF`: Cyan-and-black striped pitched Japanese tile roof (`Kawara`)
    - `KIMONO_SILK`: Crisp cream-white silk kimono with pixelated orange & green floral motifs
    - `KIMONO_RED`: Crimson lower kimono hem (`Susoyoke`) & collar
    - `WHITE_FACE`: Stark flat white polygonal face & Tabi socks
    """
    mat, nodes, links = _get_or_create_material(f"SDS_Mat_LSD_Kyoto_{role}")
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (1520, 100)

    if role in ("KIMONO_RED", "WHITE_FACE", "BLACK_HAIR"):
        n_rgb = nodes.new("ShaderNodeRGB")
        n_rgb.location = (-200, 120)
        if role == "KIMONO_RED":
            n_rgb.outputs[0].default_value = (0.64, 0.10, 0.12, 1.0)
        elif role == "WHITE_FACE":
            n_rgb.outputs[0].default_value = (0.90, 0.90, 0.88, 1.0)
        else:
            n_rgb.outputs[0].default_value = (0.04, 0.04, 0.05, 1.0)
        shader_out = _append_1997_depth_fog_and_ambient(nodes, links, n_rgb.outputs["Color"], None, props)
        links.new(shader_out, n_out.inputs["Surface"])
        return mat

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-1240, 120)
    snap_vec = _build_ps1_texel_coord(
        nodes, links, n_coord.outputs["Object"], scale_xyz=(1.0, 1.0, 1.0), texel_res=32.0, affine_shear=0.18, loc_x=-940.0, loc_y=120.0
    )

    if role == "CYAN_ROOF":
        n_wave = nodes.new("ShaderNodeTexWave")
        n_wave.location = (-280, 120)
        n_wave.wave_type = "BANDS"
        if hasattr(n_wave, "bands_direction"):
            n_wave.bands_direction = "X"
        set_socket(n_wave, ("Scale",), 6.5)
        links.new(snap_vec, n_wave.inputs["Vector"])

        n_ramp = nodes.new("ShaderNodeValToRGB")
        n_ramp.location = (40, 120)
        n_ramp.color_ramp.interpolation = "CONSTANT"
        el = n_ramp.color_ramp.elements
        el[0].position = 0.00
        el[0].color = (0.04, 0.08, 0.12, 1.0)  # Deep black tile trough
        el[1].position = 0.48
        el[1].color = (0.18, 0.66, 0.82, 1.0)  # Crisp cyan-blue glazed roof ridge
        links.new(n_wave.outputs["Fac"], n_ramp.inputs["Fac"])

        shader_out = _append_1997_depth_fog_and_ambient(nodes, links, n_ramp.outputs["Color"], None, props)
        links.new(shader_out, n_out.inputs["Surface"])
        return mat

    if role == "MACHIYA_WALL":
        # Dark timber wall with crisp white/grey vertical lattice window bars
        n_brick = nodes.new("ShaderNodeTexBrick")
        n_brick.location = (-280, 120)
        n_brick.offset = 0.0
        n_brick.squash = 0.28
        set_socket(n_brick, ("Scale",), 5.5)
        set_socket(n_brick, ("Mortar Size",), 0.18)
        set_socket(n_brick, ("Mortar Smooth",), 0.0)
        set_socket(n_brick, ("Color1",), (0.68, 0.72, 0.74, 1.0))  # Lattice window highlight
        set_socket(n_brick, ("Color2",), (0.16, 0.08, 0.04, 1.0))  # Dark cedar timber panel
        set_socket(n_brick, ("Mortar",), (0.06, 0.03, 0.02, 1.0))  # Dark timber beam frame
        links.new(snap_vec, n_brick.inputs["Vector"])

        shader_out = _append_1997_depth_fog_and_ambient(nodes, links, n_brick.outputs["Color"], None, props)
        links.new(shader_out, n_out.inputs["Surface"])
        return mat

    if role == "KIMONO_SILK":
        # Cream-white silk kimono with pixelated orange & leaf-green floral bursts
        n_vor = nodes.new("ShaderNodeTexVoronoi")
        n_vor.location = (-280, 120)
        set_socket(n_vor, ("Scale",), 2.6)
        set_socket(n_vor, ("Randomness",), 0.65)
        links.new(snap_vec, n_vor.inputs["Vector"])

        n_ramp = nodes.new("ShaderNodeValToRGB")
        n_ramp.location = (40, 120)
        n_ramp.color_ramp.interpolation = "CONSTANT"
        el = n_ramp.color_ramp.elements
        el[0].position = 0.00
        el[0].color = (0.88, 0.44, 0.14, 1.0)  # Persimmon-orange flower center
        el[1].position = 0.22
        el[1].color = (0.42, 0.64, 0.22, 1.0)  # Matcha-green leaf motif
        e2 = el.new(0.36)
        e2.color = (0.82, 0.80, 0.72, 1.0)     # Warm ivory-white kimono silk
        links.new(n_vor.outputs["Distance"], n_ramp.inputs["Fac"])

        shader_out = _append_1997_depth_fog_and_ambient(nodes, links, n_ramp.outputs["Color"], None, props)
        links.new(shader_out, n_out.inputs["Surface"])
        return mat

    # SAND_STREET: Sandy-beige gravel in foreground (`Y < 124.5` in +128.5 shifted space) + slate-blue night road behind
    n_sep = nodes.new("ShaderNodeSeparateXYZ")
    n_sep.location = (-360, 260)
    links.new(snap_vec, n_sep.inputs["Vector"])

    n_is_road = nodes.new("ShaderNodeMath")
    n_is_road.operation = "GREATER_THAN"
    n_is_road.location = (-120, 260)
    n_is_road.inputs[1].default_value = 123.5
    links.new(n_sep.outputs["Y"], n_is_road.inputs[0])

    n_ns = nodes.new("ShaderNodeTexNoise")
    n_ns.location = (-360, -20)
    set_socket(n_ns, ("Scale",), 8.5)
    set_socket(n_ns, ("Detail",), 1.0)
    links.new(snap_vec, n_ns.inputs["Vector"])

    n_sand_ramp = nodes.new("ShaderNodeValToRGB")
    n_sand_ramp.location = (-80, 40)
    n_sand_ramp.color_ramp.interpolation = "CONSTANT"
    s_el = n_sand_ramp.color_ramp.elements
    s_el[0].position = 0.00
    s_el[0].color = (0.58, 0.56, 0.36, 1.0)
    s_el[1].position = 0.45
    s_el[1].color = (0.72, 0.70, 0.48, 1.0)
    e_s2 = s_el.new(0.75)
    e_s2.color = (0.82, 0.80, 0.58, 1.0)
    links.new(n_ns.outputs["Fac"], n_sand_ramp.inputs["Fac"])

    n_road_ramp = nodes.new("ShaderNodeValToRGB")
    n_road_ramp.location = (-80, -180)
    n_road_ramp.color_ramp.interpolation = "CONSTANT"
    r_el = n_road_ramp.color_ramp.elements
    r_el[0].position = 0.00
    r_el[0].color = (0.14, 0.18, 0.42, 1.0)
    r_el[1].position = 0.50
    r_el[1].color = (0.28, 0.32, 0.52, 1.0)
    links.new(n_ns.outputs["Fac"], n_road_ramp.inputs["Fac"])

    _, m_fac, m_c1, m_c2, gnd_col = _new_mix_color(nodes, links, location=(260, 100))
    links.new(n_is_road.outputs["Value"], m_fac)
    links.new(n_sand_ramp.outputs["Color"], m_c1)
    links.new(n_road_ramp.outputs["Color"], m_c2)

    shader_out = _append_1997_depth_fog_and_ambient(nodes, links, gnd_col, None, props)
    links.new(shader_out, n_out.inputs["Surface"])
    return mat


def build_ps1_lsd_purple_plaza_material(props: Any, role: str = "FLOOR") -> Any:
    """
    Ref Image 2 (`0e0277d1...jpg`):
    - `FLOOR`: Electric purple-magenta cobblestone brick floor with dark indigo mortar & red/cyan border carpets
    - `GLYPH_WALL`: Repeating neon blue-violet rectangular glyph/window wall blocks
    - `GRAY_MAN`: Ominous dark charcoal-black dithered silhouette of The Gray Man
    - `SUN_EMBLEM`: Glowing blue-violet spiked sun emblem in the magenta sky
    """
    mat, nodes, links = _get_or_create_material(f"SDS_Mat_LSD_Plaza_{role}")
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (1280, 100)

    if role == "GRAY_MAN":
        n_rgb = nodes.new("ShaderNodeRGB")
        n_rgb.location = (-200, 120)
        n_rgb.outputs[0].default_value = (0.05, 0.06, 0.08, 1.0)
        shader_out = _append_1997_depth_fog_and_ambient(
            nodes, links, n_rgb.outputs["Color"], None, props, specular_weight=0.0, roughness=1.0
        )
        links.new(shader_out, n_out.inputs["Surface"])
        return mat

    if role == "SUN_EMBLEM":
        n_emit = nodes.new("ShaderNodeEmission")
        n_emit.location = (420, 120)
        set_socket(n_emit, ("Color",), (0.32, 0.14, 1.00, 1.0))
        set_socket(n_emit, ("Strength",), 2.4)
        links.new(n_emit.outputs["Emission"], n_out.inputs["Surface"])
        return mat

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-1200, 120)
    warp_scale = max(0.0, float(getattr(props, "ps1_affine_warp", 70.0))) / 65.0
    snap_vec = _build_ps1_texel_coord(
        nodes,
        links,
        n_coord.outputs["Object"],
        scale_xyz=(0.65, 0.65, 0.65) if role == "FLOOR" else (0.85, 0.85, 0.85),
        texel_res=22.0,
        affine_shear=0.45 * warp_scale,
        loc_x=-940.0,
        loc_y=120.0,
    )

    n_brick = nodes.new("ShaderNodeTexBrick")
    n_brick.location = (-240, 120)
    if role == "FLOOR":
        n_brick.offset = 0.5
        n_brick.squash = 1.6
        set_socket(n_brick, ("Scale",), 3.2)
        set_socket(n_brick, ("Mortar Size",), 0.045)
        set_socket(n_brick, ("Mortar Smooth",), 0.0)
        set_socket(n_brick, ("Color1",), (0.58, 0.10, 0.72, 1.0))
        set_socket(n_brick, ("Color2",), (0.44, 0.08, 0.58, 1.0))
        set_socket(n_brick, ("Mortar",), (0.12, 0.04, 0.24, 1.0))
    else:
        # GLYPH_WALL: Vertical blue-violet window/glyph tiles with magenta mortar
        n_brick.offset = 0.0
        n_brick.squash = 0.55
        set_socket(n_brick, ("Scale",), 4.0)
        set_socket(n_brick, ("Mortar Size",), 0.08)
        set_socket(n_brick, ("Mortar Smooth",), 0.0)
        set_socket(n_brick, ("Color1",), (0.22, 0.08, 0.94, 1.0))
        set_socket(n_brick, ("Color2",), (0.48, 0.12, 0.96, 1.0))
        set_socket(n_brick, ("Mortar",), (0.52, 0.04, 0.58, 1.0))
    links.new(snap_vec, n_brick.inputs["Vector"])

    shader_out = _append_1997_depth_fog_and_ambient(
        nodes, links, n_brick.outputs["Color"], None, props, specular_weight=0.0, roughness=1.0
    )
    links.new(shader_out, n_out.inputs["Surface"])
    return mat


def build_ps1_lsd_flesh_tunnel_material(props: Any, is_wall_stretched: bool = False) -> Any:
    """
    Ref Image 3 (`400e7d72...jpg`):
    - Organic mottled crimson/meat/sinew PS1 texture with extreme vertical UV clamp stretching
      on the lower side walls (`is_wall_stretched=True`), fading into blinding #ff0000 red fog!
    """
    mat_name = "SDS_Mat_LSD_FleshWallStretch" if is_wall_stretched else "SDS_Mat_LSD_FleshTunnel"
    mat, nodes, links = _get_or_create_material(mat_name)
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (1280, 100)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-1200, 120)
    warp_scale = max(0.0, float(getattr(props, "ps1_affine_warp", 80.0))) / 65.0
    # Extreme vertical Z stretch on side walls to reproduce the UV clamp streak in Ref Image 3!
    sc_xyz = (0.45, 0.45, 0.04) if is_wall_stretched else (0.55, 0.35, 0.55)
    snap_vec = _build_ps1_texel_coord(
        nodes,
        links,
        n_coord.outputs["Object"],
        scale_xyz=sc_xyz,
        texel_res=18.0,
        affine_shear=0.65 * warp_scale,
        loc_x=-940.0,
        loc_y=120.0,
    )

    n_noise = nodes.new("ShaderNodeTexNoise")
    n_noise.location = (-320, 120)
    set_socket(n_noise, ("Scale",), 3.8)
    set_socket(n_noise, ("Detail",), 2.0)
    set_socket(n_noise, ("Distortion",), 1.4)
    links.new(snap_vec, n_noise.inputs["Vector"])

    n_ramp = nodes.new("ShaderNodeValToRGB")
    n_ramp.location = (-40, 120)
    n_ramp.color_ramp.interpolation = "CONSTANT"
    el = n_ramp.color_ramp.elements
    el[0].position = 0.00
    el[0].color = (0.16, 0.04, 0.04, 1.0)  # Dark coagulated maroon
    el[1].position = 0.30
    el[1].color = (0.42, 0.12, 0.11, 1.0)  # Deep meat red
    e2 = el.new(0.56)
    e2.color = (0.64, 0.24, 0.20, 1.0)     # Raw flesh crimson
    e3 = el.new(0.78)
    e3.color = (0.78, 0.52, 0.48, 1.0)     # Pale sinew pink-grey
    links.new(n_noise.outputs["Fac"], n_ramp.inputs["Fac"])

    shader_out = _append_1997_depth_fog_and_ambient(
        nodes, links, n_ramp.outputs["Color"], None, props, specular_weight=0.0, roughness=1.0
    )
    links.new(shader_out, n_out.inputs["Surface"])
    return mat


def build_ps1_lsd_polkadot_floor_material(props: Any) -> Any:
    """
    Ref Image 4 (`5aae83fb...jpg`):
    - White floor covered in overlapping pixelated CMYK/RGB neon polka-dots!
    """
    mat, nodes, links = _get_or_create_material("SDS_Mat_LSD_PolkaDotFloor")
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (1320, 100)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-1200, 120)
    warp_scale = max(0.0, float(getattr(props, "ps1_affine_warp", 75.0))) / 65.0
    snap_vec = _build_ps1_texel_coord(
        nodes,
        links,
        n_coord.outputs["Object"],
        scale_xyz=(0.75, 0.75, 0.75),
        texel_res=22.0,
        affine_shear=0.50 * warp_scale,
        loc_x=-940.0,
        loc_y=120.0,
    )

    n_vor = nodes.new("ShaderNodeTexVoronoi")
    n_vor.location = (-360, 120)
    set_socket(n_vor, ("Scale",), 2.2)
    set_socket(n_vor, ("Randomness",), 0.75)
    links.new(snap_vec, n_vor.inputs["Vector"])

    # Inside circle mask (Distance < 0.44 -> colorful dot, >= 0.44 -> white floor)
    n_lt = nodes.new("ShaderNodeMath")
    n_lt.operation = "LESS_THAN"
    n_lt.location = (-80, 240)
    n_lt.inputs[1].default_value = 0.44
    links.new(n_vor.outputs["Distance"], n_lt.inputs[0])

    n_sep = nodes.new("ShaderNodeSeparateXYZ")
    n_sep.location = (-80, -20)
    links.new(n_vor.outputs["Color"], n_sep.inputs["Vector"])

    n_ramp = nodes.new("ShaderNodeValToRGB")
    n_ramp.location = (160, -20)
    n_ramp.color_ramp.interpolation = "CONSTANT"
    el = n_ramp.color_ramp.elements
    el[0].position = 0.00
    el[0].color = (0.00, 0.78, 0.96, 1.0)  # Cyan dot
    el[1].position = 0.18
    el[1].color = (0.94, 0.08, 0.56, 1.0)  # Magenta dot
    e2 = el.new(0.36)
    e2.color = (0.98, 0.92, 0.06, 1.0)     # Yellow dot
    e3 = el.new(0.54)
    e3.color = (0.12, 0.86, 0.22, 1.0)     # Acid green dot
    e4 = el.new(0.72)
    e4.color = (0.96, 0.22, 0.08, 1.0)     # Red-orange dot
    e5 = el.new(0.88)
    e5.color = (0.06, 0.08, 0.10, 1.0)     # Black dot
    links.new(n_sep.outputs["X"], n_ramp.inputs["Fac"])

    _, m_fac, m_c1, m_c2, m_out = _new_mix_color(nodes, links, location=(440, 120))
    m_c1.default_value = (0.94, 0.96, 0.92, 1.0)  # Crisp white floor background
    links.new(n_lt.outputs["Value"], m_fac)
    links.new(n_ramp.outputs["Color"], m_c2)

    shader_out = _append_1997_depth_fog_and_ambient(
        nodes, links, m_out, None, props, specular_weight=0.0, roughness=1.0
    )
    links.new(shader_out, n_out.inputs["Surface"])
    return mat


def build_ps1_lsd_graffiti_wall_material(props: Any) -> Any:
    """
    Ref Image 4 (`5aae83fb...jpg`):
    - Heavily dithered acid-green, bright-yellow, hot-red, cobalt-blue & black posterized
      collage graffiti corridor wall!
    """
    mat, nodes, links = _get_or_create_material("SDS_Mat_LSD_GraffitiWall")
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (1280, 100)

    n_coord = nodes.new("ShaderNodeTexCoord")
    n_coord.location = (-1200, 120)
    warp_scale = max(0.0, float(getattr(props, "ps1_affine_warp", 75.0))) / 65.0
    snap_vec = _build_ps1_texel_coord(
        nodes,
        links,
        n_coord.outputs["Object"],
        scale_xyz=(0.65, 0.65, 0.65),
        texel_res=20.0,
        affine_shear=0.45 * warp_scale,
        loc_x=-940.0,
        loc_y=120.0,
    )

    n_noise = nodes.new("ShaderNodeTexNoise")
    n_noise.location = (-320, 120)
    set_socket(n_noise, ("Scale",), 2.4)
    set_socket(n_noise, ("Detail",), 3.0)
    set_socket(n_noise, ("Distortion",), 1.8)
    links.new(snap_vec, n_noise.inputs["Vector"])

    n_ramp = nodes.new("ShaderNodeValToRGB")
    n_ramp.location = (-40, 120)
    n_ramp.color_ramp.interpolation = "CONSTANT"
    el = n_ramp.color_ramp.elements
    el[0].position = 0.00
    el[0].color = (0.04, 0.08, 0.04, 1.0)  # Deep black-green shadow ink
    el[1].position = 0.24
    el[1].color = (0.12, 0.78, 0.26, 1.0)  # Acid green portrait/collage tone
    e2 = el.new(0.46)
    e2.color = (0.96, 0.88, 0.08, 1.0)     # Blazing yellow patch
    e3 = el.new(0.64)
    e3.color = (0.92, 0.22, 0.14, 1.0)     # Hot red/orange collage figure
    e4 = el.new(0.82)
    e4.color = (0.14, 0.24, 0.88, 1.0)     # Cobalt blue background patch
    links.new(n_noise.outputs["Fac"], n_ramp.inputs["Fac"])

    shader_out = _append_1997_depth_fog_and_ambient(
        nodes, links, n_ramp.outputs["Color"], None, props, specular_weight=0.0, roughness=1.0
    )
    links.new(shader_out, n_out.inputs["Surface"])
    return mat


def build_ps1_lsd_red_portal_material(props: Any) -> Any:
    """Blinding #FF0000 Blood-Red Fog Portal & Red Mascot Bib Material for Ref Image 3 (`400e7d72...jpg`)."""
    mat, nodes, links = _get_or_create_material("SDS_Mat_LSD_RedPortal")
    n_out = nodes.new("ShaderNodeOutputMaterial")
    n_out.location = (420, 100)
    n_emit = nodes.new("ShaderNodeEmission")
    n_emit.location = (140, 100)
    set_socket(n_emit, ("Color",), (1.00, 0.02, 0.01, 1.0))
    set_socket(n_emit, ("Strength",), 2.8)
    links.new(n_emit.outputs["Emission"], n_out.inputs["Surface"])
    return mat
