# SPDX-License-Identifier: GPL-3.0-or-later
"""
3D Viewport Sidebar UI (`N` Panel -> `Late-90s Lab`) for Late-90s Graphics Lab (v4.0.0).
Strictly partitions the Four Graphics Categories into separate, self-contained panels/boxes,
each containing its own dedicated Presets and Category-Specific Controls:
- Box I:   【类别 I】1997 离线 CGI · Bryce 3D & POV-Ray (6 Presets + Terrain Lab + DTE & Whitted Raytracer)
- Box II:  【类别 II】1994–1998 PS1 实时图形 &《LSD》梦境 (4 Presets — 100% Flat-Shaded Low-Poly + GTE/GPU + LSD Spatial Graph)
- Box III: 【类别 III】1998–2001 Sega Dreamcast · PowerVR2 TBDR (3 Presets + TBDR Multi-Layer Alpha Glow & Spherical EnvMap)
- Box IV:  【类别 IV】2000–2005 PS2 实时图形 · Emotion Engine & GS (3 Presets including ICO Castle Bridge + VPU & GS Bloom)
- Box V:   【全局输出】显示媒介、分辨率与配方管理 (Display Profile & Recipe System)
"""

import bpy
from bpy.types import Panel

from . import presets


class SDS_SidebarPanelBase:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Late-90s Lab"


class SDS_PT_main_panel(SDS_SidebarPanelBase, Panel):
    bl_idname = "SDS_PT_main_panel"
    bl_label = "LATE-90s GRAPHICS LAB"

    def draw(self, context):
        layout = self.layout
        props = context.scene.sds_props

        header_box = layout.box()
        col = header_box.column(align=True)
        col.label(text="Late-90s Graphics Lab · v4.0", icon="WORLD")
        preset_meta = presets.WORLD_PRESETS.get(props.world_preset, presets.WORLD_PRESETS["CLASSIC_BRYCE"])
        col.label(text=f"当前预设：{preset_meta['name']}", icon="SOLO_ON")
        col.label(text=f"特征：{preset_meta['subtitle']}")

        act_col = layout.column(align=True)
        row_main = act_col.row(align=True)
        row_main.scale_y = 1.45
        row_main.operator("sds.generate_scene", text="Generate Scene · 生成场景", icon="SCENE_DATA")

        row_sub = act_col.row(align=True)
        row_sub.scale_y = 1.2
        op_rnd = row_sub.operator("sds.randomize_scene", text="Randomize · 随机探索", icon="FILE_REFRESH")
        op_rnd.seed_only = False
        op_ter = row_sub.operator("sds.regenerate_terrain", text="Regenerate Terrain", icon="RNDCURVE")
        op_ter.new_seed = False

        layout.prop(props, "auto_update_scene", toggle=True)


# ===========================================================================
# CATEGORY I — 1997 OFFLINE CGI (Bryce 3D & POV-Ray)
# ===========================================================================
class SDS_PT_cat1_bryce_panel(SDS_SidebarPanelBase, Panel):
    bl_idname = "SDS_PT_cat1_bryce_panel"
    bl_parent_id = "SDS_PT_main_panel"
    bl_label = "【类别 I】1997 离线 CGI · Bryce & POV-Ray"

    def draw(self, context):
        layout = self.layout
        props = context.scene.sds_props

        p_box = layout.box()
        p_box.label(text="[I-A] 1997 离线 CGI 专属预设 (Offline Presets):", icon="WORLD")
        grid = p_box.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=True, align=True)
        cat1_presets = [
            ("CLASSIC_BRYCE", "Classic Bryce 97", "WORLD"),
            ("INFINITE_OCEAN", "Granite Domes", "RNDCURVE"),
            ("ALIEN_DREAM", "Alien Bio-Dome", "LIGHT_SUN"),
            ("RAYTRACED_GEOMETRY", "POV-Ray CSG Arch", "SHADING_RENDERED"),
            ("SUNSET_MONOLITH", "Sunset Monolith", "MOD_OCEAN"),
            ("ABSTRACT_LAB", "Abstract Lab 97", "MESH_ICOSPHERE"),
        ]
        for pid, label, icn in cat1_presets:
            op = grid.operator(
                "sds.apply_world_preset",
                text=label,
                icon=icn,
                depress=(props.world_preset == pid),
            )
            op.preset_id = pid

        t_box = layout.box()
        t_box.label(text="[I-B] Bryce Terrain Lab · 分形高度场生成:", icon="RNDCURVE")
        t_col = t_box.column(align=True)
        t_col.prop(props, "terrain_mode", text="地貌")
        t_col.prop(props, "mesh_resolution", text="网格")
        t_col.prop(props, "terrain_relief", slider=True)

        qrow = t_col.row(align=True)
        for label, val in (("平缓 (35%)", 35.0), ("经典 (64%)", 64.0), ("险峻 (85%)", 85.0)):
            op = qrow.operator(
                "sds.set_relief_level",
                text=label,
                depress=(abs(props.terrain_relief - val) < 5.0),
            )
            op.level = val

        t_col.separator()
        t_col.prop(props, "fractal_detail", slider=True)
        t_col.prop(props, "sharpness", slider=True)
        t_col.prop(props, "erosion_strength", slider=True)
        t_col.prop(props, "terrain_scale")
        row_sc = t_col.row(align=True)
        row_sc.prop(props, "terrace_steps", text="阶地层数")
        row_sc.prop(props, "plateau_clip", text="峰顶截断")
        seed_row = t_col.row(align=True)
        seed_row.prop(props, "seed")
        op_ns = seed_row.operator("sds.regenerate_terrain", text="换种子", icon="FILE_REFRESH")
        op_ns.new_seed = True

        m_box = layout.box()
        m_box.label(text="[I-C] Bryce DTE 纹理、天幕与 Whitted 光追:", icon="MATERIAL")
        m_col = m_box.column(align=True)
        m_col.prop(props, "color_contrast_sharpness", slider=True)
        m_col.prop(props, "ambient_strength", slider=True)
        t_row = m_col.row(align=True)
        t_row.prop(props, "terrain_low_color", text="低地")
        t_row.prop(props, "terrain_mid_color", text="岩层")
        t_row.prop(props, "terrain_high_color", text="雪峰")

        m_col.separator()
        w_row = m_col.row(align=True)
        w_row.prop(props, "enable_water", text="镜面水体")
        if props.enable_water:
            w_row.prop(props, "water_level", text="水位")
            w_sub = m_col.row(align=True)
            w_sub.prop(props, "mirror_reflection", text="反射", slider=True)
            w_sub.prop(props, "wave_chop", text="横向波纹", slider=True)
            w_sub.prop(props, "water_color", text="")

        m_col.separator()
        row_sky = m_col.row(align=True)
        row_sky.prop(props, "sky_zenith_color", text="天顶")
        row_sky.prop(props, "sky_horizon_color", text="地平线")
        row_sky.prop(props, "cloud_color", text="云霞")
        row_sun = m_col.row(align=True)
        row_sun.prop(props, "sun_elevation", text="太阳仰角")
        row_sun.prop(props, "sun_azimuth", text="方位角")
        row_cld = m_col.row(align=True)
        row_cld.prop(props, "cloud_coverage", text="云量", slider=True)
        row_cld.prop(props, "far_fog", text="解析雾", slider=True)

        m_col.separator()
        m_col.prop(props, "hero_composition", text="几何构图")
        if props.hero_composition != "TERRAIN_ONLY":
            row_h = m_col.row(align=True)
            row_h.prop(props, "hero_material_style", text="材质")
            row_h.prop(props, "hero_count", text="数量")
            row_h.prop(props, "hero_scale", text="尺度")


# ===========================================================================
# CATEGORY II — PS1 REALTIME GRAPHICS &《LSD: DREAM EMULATOR》DREAMSPACE
# ===========================================================================
class SDS_PT_cat2_ps1_lsd_panel(SDS_SidebarPanelBase, Panel):
    bl_idname = "SDS_PT_cat2_ps1_lsd_panel"
    bl_parent_id = "SDS_PT_main_panel"
    bl_label = "【类别 II】1994–1998 PS1 实时图形 &《LSD》梦境"

    def draw(self, context):
        layout = self.layout
        props = context.scene.sds_props

        p_box = layout.box()
        p_box.label(text="[II-A] PS1 硬边低模与 LSD 梦境预设 (Zero-Smooth):", icon="MOD_BUILD")
        grid = p_box.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=True, align=True)
        cat2_presets = [
            ("LSD_PSYCHEDELIC_TURTLE", "LSD: 靶心巨龟", "MESH_ICOSPHERE"),
            ("LSD_KANJI_EYE_GIANT", "LSD: 独眼汉字巨像", "HIDE_OFF"),
            ("LSD_KYOTO_KIMONO_NIGHT", "LSD: 京都夜街和服女", "OUTLINER_OB_ARMATURE"),
            ("LSD_GRAY_MAN_PLAZA", "LSD: 紫天灰衣帽男", "ARMATURE_DATA"),
            ("LSD_FLESH_TUNNEL", "LSD: 红雾血肉隧道", "SHADING_SOLID"),
            ("LSD_GRAFFITI_CORRIDOR", "LSD: 波点涂鸦长廊", "COLOR"),
            ("LSD_DREAM_EMULATOR", "LSD: 明月庄 (楼/吧台)", "MOD_BUILD"),
            ("LSD_VIOLENCE_TOWERS", "九龙风水传 (城寨巷)", "HOME"),
            ("PS1_AFFINE_DUNGEON", "PS1 Classic 1996", "MOD_TRIANGULATE"),
            ("IMPOSSIBLE_GEOGRAPHY", "PS1 Cyber Grid", "MOD_WIREFRAME"),
        ]
        for pid, label, icn in cat2_presets:
            op = grid.operator(
                "sds.apply_world_preset",
                text=label,
                icon=icn,
                depress=(props.world_preset == pid),
            )
            op.preset_id = pid

        hw_box = layout.box()
        hw_box.label(text="[II-B] PS1 硬件限制模拟 (GTE 抖动 / 硬边三角面):", icon="MOD_DECIM")
        h_col = hw_box.column(align=True)
        wob_row = h_col.row(align=True)
        wob_row.scale_y = 1.25
        wob_row.operator("sds.play_ps1_wobble", text="播放/暂停抖动动画 (Space)", icon="PLAY")
        wob_row.operator("sds.step_ps1_wobble", text="单步跳格 (+2f)", icon="FRAME_NEXT")
        h_col.prop(props, "ps1_vertex_snap", text="GTE 顶点坐标量化抖动 (Wobble)")
        h_col.prop(props, "ps1_vram_grit", text="4×4 Bayer 抖动与显存脏化颗粒", slider=True)
        h_col.prop(props, "ps1_affine_warp", text="仿射纹理扭曲 (Affine UV Warp)", slider=True)
        h_col.prop(props, "mesh_resolution", text="PS1 地形网格")
        row_fl = h_col.row(align=True)
        row_fl.prop(props, "flat_shaded_terrain", text="全硬边折面")
        row_fl.prop(props, "low_poly_primitives", text="八面体低模")
        h_col.prop(props, "color_quantization_steps", text="色深量化 (32=15-bit RGB)", slider=True)

        lsd_box = layout.box()
        lsd_box.label(text="[II-C]《LSD》梦境空间拼接与异质纹理系统:", icon="SCENE_DATA")
        l_col = lsd_box.column(align=True)
        l_col.prop(props, "dream_architecture_mode", text="空间图拼接")
        l_col.prop(props, "texture_mismatch_mode", text="异质纹理分配")
        row_an = l_col.row(align=True)
        row_an.prop(props, "dream_scale_anomaly", text="尺度比例异常", slider=True)
        row_an.prop(props, "dream_tilt_anomaly", text="局部重力倾斜")


# ===========================================================================
# CATEGORY III — 1998–2001 SEGA DREAMCAST · NEC POWERVR2 TBDR
# ===========================================================================
class SDS_PT_cat3_dreamcast_panel(SDS_SidebarPanelBase, Panel):
    bl_idname = "SDS_PT_cat3_dreamcast_panel"
    bl_parent_id = "SDS_PT_main_panel"
    bl_label = "【类别 III】1998–2001 Sega Dreamcast · PowerVR2"

    def draw(self, context):
        layout = self.layout
        props = context.scene.sds_props

        p_box = layout.box()
        p_box.label(text="[III-A] Sega Dreamcast 专属预设 (PowerVR2 TBDR):", icon="MATSPHERE")
        grid = p_box.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=True, align=True)
        cat3_dc_presets = [
            ("DC_GEIST_WATERFALL", "DC 瀑布峡谷战机", "IPO_ELASTIC"),
            ("DC_SONIC_COAST", "DC 翡翠海岸碧海", "MOD_OCEAN"),
            ("DC_REZ_CYBERSPACE", "DC Rez 赛博矩阵", "MOD_WIREFRAME"),
        ]
        for pid, label, icn in cat3_dc_presets:
            op = grid.operator(
                "sds.apply_world_preset",
                text=label,
                icon=icn,
                depress=(props.world_preset == pid),
            )
            op.preset_id = pid

        dc_box = layout.box()
        dc_box.label(text="[III-B] PowerVR2 分块延迟渲染与多层半透明特效:", icon="SHADING_RENDERED")
        d_col = dc_box.column(align=True)
        d_col.prop(props, "dc_alpha_glow", text="TBDR 多层半透明尾焰光晕 (Alpha Glow)", slider=True)
        d_col.prop(props, "dc_trilinear_sharpness", text="透视校正三线性纹理锐度", slider=True)
        d_col.prop(props, "reflection_model", text="球面环境贴图")
        d_col.prop(props, "far_fog", text="硬件雾化表 (Fog Table)", slider=True)
        d_col.prop(props, "camera_preset", text="镜头视角")


# ===========================================================================
# CATEGORY IV — 2000–2005 PS2 REALTIME GRAPHICS (Emotion Engine & GS)
# ===========================================================================
class SDS_PT_cat4_ps2_panel(SDS_SidebarPanelBase, Panel):
    bl_idname = "SDS_PT_cat4_ps2_panel"
    bl_parent_id = "SDS_PT_main_panel"
    bl_label = "【类别 IV】2000–2005 PS2 实时图形 · EE & GS"

    def draw(self, context):
        layout = self.layout
        props = context.scene.sds_props

        p_box = layout.box()
        p_box.label(text="[IV-A] PS2 实时场景专属预设 (2000–2005):", icon="LIGHT_SUN")
        grid = p_box.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=True, align=True)
        cat4_presets = [
            ("PS2_MISTY_RUINS", "PS2 ICO 古堡拱桥", "LIGHT_SUN"),
            ("PS2_COLOSSUS_VALLEY", "PS2 旺达禁忌峡谷", "RNDCURVE"),
            ("AERO_PARADISE", "PS2 / Y2K 生态乌托邦", "MATSPHERE"),
        ]
        for pid, label, icn in cat4_presets:
            op = grid.operator(
                "sds.apply_world_preset",
                text=label,
                icon=icn,
                depress=(props.world_preset == pid),
            )
            op.preset_id = pid

        gs_box = layout.box()
        gs_box.label(text="[IV-B] PS2 VPU 几何与 GS 帧缓冲过曝柔光:", icon="SHADING_RENDERED")
        g_col = gs_box.column(align=True)
        g_col.prop(props, "ps2_bloom_intensity", text="GS 帧缓冲过曝柔光 (Bloom)", slider=True)
        g_col.prop(props, "ps2_vpu_wave", text="VPU 向量顶点风场变形", slider=True)
        g_col.prop(props, "far_fog", text="GS 远景大气透视浓雾", slider=True)
        g_col.prop(props, "dream_architecture_mode", text="古堡/遗迹结构")
        g_col.prop(props, "camera_preset", text="镜头构图")


# ===========================================================================
# GLOBAL OUTPUT — DISPLAY PROFILE & RECIPE SYSTEM
# ===========================================================================


# ===========================================================================
# TEXTURE SYNTHESIS WORKBENCH — 4 ERA TEXTURE PARADIGMS & OBJECT TOOLKIT
# ===========================================================================
class SDS_PT_texture_workbench_panel(SDS_SidebarPanelBase, Panel):
    bl_idname = "SDS_PT_texture_workbench_panel"
    bl_parent_id = "SDS_PT_main_panel"
    bl_label = "【纹理工具箱】四大图形学纹理合成与改造台"

    def draw(self, context):
        layout = self.layout
        props = context.scene.sds_props

        # 1. Paradigm & Archetype Selector Box
        p_box = layout.box()
        p_box.label(text="[T-1] 四大图形学纹理生成思路 (Texture Paradigm):", icon="TEXTURE")
        p_col = p_box.column(align=True)
        p_col.prop(props, "tex_synth_paradigm", text="生成思路")
        p_col.prop(props, "tex_archetype", text="纹理母型")
        p_col.prop(props, "tex_res_grid", text="纹素精度")

        # 2. CLUT Palette, Pre-Baked Grime & Micro-Detail Controls Box
        c_box = layout.box()
        c_box.label(text="[T-2] 预烘焙做旧、微表面细节与 CLUT 调色板:", icon="COLOR")
        c_col = c_box.column(align=True)
        row_pal = c_col.row(align=True)
        row_pal.prop(props, "tex_clut_palette", text="色表")
        row_pal.operator("sds.cycle_clut_palette", text="轮换色表", icon="FILE_REFRESH")

        c_col.prop(props, "tex_prebaked_grit", text="预烘焙砖缝暗角与水渍 (Grime)", slider=True)
        c_col.prop(props, "tex_detail_overlay", text="18x 高频微表面颗粒 (Micro-Grain)", slider=True)
        c_col.prop(props, "tex_scale_factor", text="纹理空间密度缩放")

        # 3. One-Click Toolification Actions Box
        a_box = layout.box()
        a_box.label(text="[T-3] 材质赋予、贴图改造与节点组库工具:", icon="TOOL_SETTINGS")
        a_col = a_box.column(align=True)
        row_ap = a_col.row(align=True)
        row_ap.scale_y = 1.35
        row_ap.operator("sds.apply_texture_tool", text="赋予选中物体 (Apply to Selected)", icon="MATERIAL")

        row_sub = a_col.row(align=True)
        row_sub.scale_y = 1.2
        row_sub.operator("sds.retrofy_materials", text="改造现有贴图/材质", icon="NODE_MATERIAL")
        row_sub.operator("sds.build_texture_nodegroups", text="生成 5 大节点组库", icon="NODETREE")


class SDS_PT_render_recipe_panel(SDS_SidebarPanelBase, Panel):
    bl_idname = "SDS_PT_render_recipe_panel"
    bl_parent_id = "SDS_PT_main_panel"
    bl_label = "【全局输出】显示媒介、分辨率与配方管理"

    def draw(self, context):
        layout = self.layout
        props = context.scene.sds_props

        r_col = layout.column(align=True)
        for prof_id, label in (
            ("RES_320", "320 × 240 · PS1 低分辨率输出 (15-bit)"),
            ("RES_640", "640 × 480 · Bryce / Dreamcast / PS2 标准输出"),
            ("RES_1024", "1024 × 768 · Y2K 高清桌面输出"),
        ):
            op = r_col.operator(
                "sds.set_render_profile",
                text=label,
                depress=(props.render_profile == prof_id),
            )
            op.profile = prof_id

        layout.prop(props, "saturation_boost", text="CRT 色彩饱和度倍增", slider=True)

        sum_box = layout.box()
        s_col = sum_box.column(align=True)
        preset_meta = presets.WORLD_PRESETS.get(props.world_preset, presets.WORLD_PRESETS["CLASSIC_BRYCE"])
        res_labels = {
            "RES_320": "320 × 240",
            "RES_640": "640 × 480",
            "RES_1024": "1024 × 768",
            "RES_1920": "1920 × 1080",
        }
        res_str = res_labels.get(props.render_profile, "640 × 480")

        s_col.label(text="当前配方摘要 (Current Recipe)", icon="TEXT")
        s_col.label(text=f"路线：{props.era_pipeline} | 预设：{preset_meta['name']}")
        s_col.label(
            text=f"建筑/场景：{props.dream_architecture_mode} · 网格：{props.mesh_resolution}"
        )
        s_col.label(
            text=f"PS1 抖动 {props.ps1_vertex_snap:.2f}m · DC 光晕 {int(round(props.dc_alpha_glow))}% · PS2 柔光 {int(round(props.ps2_bloom_intensity))}% · {res_str}"
        )

        io_row = layout.row(align=True)
        io_row.operator("sds.save_recipe", text="Save Recipe", icon="EXPORT")
        io_row.operator("sds.load_recipe", text="Load Recipe", icon="IMPORT")

        render_row = layout.row(align=True)
        render_row.scale_y = 1.35
        render_row.operator("sds.render_preview", text="Render Preview · 渲染预览 (F12)", icon="RENDER_STILL")


CLASSES = (
    SDS_PT_main_panel,
    SDS_PT_cat1_bryce_panel,
    SDS_PT_cat2_ps1_lsd_panel,
    SDS_PT_cat3_dreamcast_panel,
    SDS_PT_cat4_ps2_panel,
    SDS_PT_texture_workbench_panel,
    SDS_PT_render_recipe_panel,
)
