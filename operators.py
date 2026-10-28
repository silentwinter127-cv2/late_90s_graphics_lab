# SPDX-License-Identifier: GPL-3.0-or-later
"""
Operators for Silicon Dreams Studio v1.2 (1997 Render Pipeline Edition).
"""

import random
import bpy
from bpy.props import BoolProperty, FloatProperty, StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ExportHelper, ImportHelper

from . import presets, terrain, materials, scene_composer


class SDS_OT_generate_scene(Operator):
    bl_idname = "sds.generate_scene"
    bl_label = "Generate Scene · 生成完整场景"
    bl_description = "一键生成完整的 1997 Bryce / POV-Ray 场景并配置 Whitted 光线追踪管线"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.sds_props
        scene_composer.compose_full_scene(context, props)
        self.report(
            {"INFO"},
            f"Silicon Dreams Studio v1.2: 已生成 [{props.world_preset}] (Pipeline: {props.render_engine_mode})",
        )
        return {"FINISHED"}


class SDS_OT_regenerate_terrain(Operator):
    bl_idname = "sds.regenerate_terrain"
    bl_label = "Regenerate Terrain · 重新生成地形"
    bl_description = "仅使用当前 Terrain Lab 参数与种子重新计算高度场网格与三通道高对比材质"
    bl_options = {"REGISTER", "UNDO"}

    new_seed: BoolProperty(
        name="同时更换随机种子 (New Seed)",
        default=False,
    )

    def execute(self, context):
        props = context.scene.sds_props
        if self.new_seed:
            props.seed = random.randint(100, 99999)
        col = scene_composer.ensure_sds_collection(context)
        t_mat = materials.build_terrain_material(props)
        terrain.generate_or_update_terrain(context, props, col, terrain_mat=t_mat)
        self.report({"INFO"}, f"Terrain Lab: 地形已更新 (Seed: {props.seed})")
        return {"FINISHED"}


class SDS_OT_randomize_scene(Operator):
    bl_idname = "sds.randomize_scene"
    bl_label = "Randomize · 随机化探索"
    bl_description = "随机生成新的种子与微调地形/光照参数，保持高饱和 1997 色彩对比"
    bl_options = {"REGISTER", "UNDO"}

    seed_only: BoolProperty(
        name="仅随机种子 (Seed Only)",
        default=False,
    )

    def execute(self, context):
        props = context.scene.sds_props
        rng = random.Random()
        props.seed = rng.randint(100, 99999)

        if not self.seed_only:
            was_guard = props.is_applying_preset
            props.is_applying_preset = True
            try:
                props.terrain_relief = round(rng.uniform(45.0, 82.0), 1)
                props.fractal_detail = round(rng.uniform(40.0, 68.0), 1)
                props.erosion_strength = round(rng.uniform(20.0, 50.0), 1)
                props.sharpness = round(rng.uniform(50.0, 82.0), 1)
                props.sun_elevation = round(rng.uniform(16.0, 48.0), 1)
                props.sun_azimuth = round(rng.uniform(105.0, 225.0), 1)
            finally:
                props.is_applying_preset = was_guard

        scene_composer.compose_full_scene(context, props)
        self.report({"INFO"}, f"Silicon Dreams Studio: 已随机生成新变体 (Seed: {props.seed})")
        return {"FINISHED"}


class SDS_OT_apply_world_preset(Operator):
    bl_idname = "sds.apply_world_preset"
    bl_label = "Apply World Preset · 应用世界预设"
    bl_description = "加载选定的世界预设参数并立即更新场景"
    bl_options = {"REGISTER", "UNDO"}

    preset_id: StringProperty(default="CLASSIC_BRYCE")

    def execute(self, context):
        props = context.scene.sds_props
        presets.apply_preset_to_props(props, self.preset_id)
        scene_composer.compose_full_scene(context, props)
        preset_info = presets.WORLD_PRESETS.get(self.preset_id, {})
        self.report({"INFO"}, f"已加载世界预设: {preset_info.get('name', self.preset_id)}")
        return {"FINISHED"}


class SDS_OT_set_relief_level(Operator):
    bl_idname = "sds.set_relief_level"
    bl_label = "Set Terrain Relief · 快速设置山脉起伏"
    bl_options = {"REGISTER", "UNDO"}

    level: FloatProperty(default=62.0)

    def execute(self, context):
        props = context.scene.sds_props
        props.terrain_relief = self.level
        col = scene_composer.ensure_sds_collection(context)
        t_mat = materials.build_terrain_material(props)
        terrain.generate_or_update_terrain(context, props, col, terrain_mat=t_mat)
        return {"FINISHED"}


class SDS_OT_set_render_profile(Operator):
    bl_idname = "sds.set_render_profile"
    bl_label = "Set Render Profile · 切换渲染尺寸"
    bl_options = {"REGISTER", "UNDO"}

    profile: StringProperty(default="RES_640")

    def execute(self, context):
        props = context.scene.sds_props
        props.render_profile = self.profile
        scene_composer.apply_render_profile(context, props)
        return {"FINISHED"}


class SDS_OT_save_recipe(Operator, ExportHelper):
    bl_idname = "sds.save_recipe"
    bl_label = "Save Recipe · 保存 JSON 配方"

    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

    def invoke(self, context, event):
        props = context.scene.sds_props
        preset_slug = props.world_preset.lower()
        self.filepath = f"sds_recipe_{preset_slug}_{props.seed}.json"
        return super().invoke(context, event)

    def execute(self, context):
        props = context.scene.sds_props
        try:
            presets.save_recipe_json(props, self.filepath)
            self.report({"INFO"}, f"已保存风格配方至: {self.filepath}")
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, f"保存配方失败: {exc}")
            return {"CANCELLED"}


class SDS_OT_load_recipe(Operator, ImportHelper):
    bl_idname = "sds.load_recipe"
    bl_label = "Load Recipe · 导入 JSON 配方"
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context):
        props = context.scene.sds_props
        try:
            presets.load_recipe_json(props, self.filepath)
            scene_composer.compose_full_scene(context, props)
            self.report({"INFO"}, f"已加载并应用风格配方: {self.filepath}")
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, f"读取配方失败: {exc}")
            return {"CANCELLED"}


class SDS_OT_render_preview(Operator):
    bl_idname = "sds.render_preview"
    bl_label = "Render Preview · 渲染预览"
    bl_description = "按当前 1997 Whitted 光线追踪管线与分辨率打开渲染预览窗口"

    def execute(self, context):
        props = context.scene.sds_props
        scene_composer.apply_render_profile(context, props)
        if context.scene.camera is None:
            col = scene_composer.ensure_sds_collection(context)
            scene_composer.setup_camera_framing(context, props, col)
        try:
            bpy.ops.render.render("INVOKE_DEFAULT", use_viewport=True)
        except Exception:
            bpy.ops.render.render(write_still=False)
        return {"FINISHED"}




class SDS_OT_play_ps1_wobble(Operator):
    bl_idname = "sds.play_ps1_wobble"
    bl_label = "Play / Pause PS1 Wobble · 播放/暂停 PS1 顶点抖动动画"
    bl_description = "使用 C++ 原生 Geometry Nodes 时间步进节点与 240 帧循环关键帧安全播放 PS1 顶点抖动动画（渲染不崩溃）"

    def execute(self, context):
        from . import dreamspace
        props = context.scene.sds_props
        if getattr(props, "ps1_vertex_snap", 0.0) < 0.001 or getattr(props, "ps1_vertex_snap", 0.0) > 0.020:
            props.ps1_vertex_snap = 0.006
        dreamspace.unregister_ps1_frame_handler()
        dreamspace.ensure_ps1_gte_geonodes(props)
        scene_composer.setup_ps1_scene_animation(context, props)
        try:
            bpy.ops.screen.animation_play()
        except Exception:
            cur_f = int(getattr(context.scene, "frame_current", 1)) + 2
            if hasattr(context.scene, "frame_set"):
                context.scene.frame_set(cur_f)
            else:
                context.scene.frame_current = cur_f
        return {"FINISHED"}


class SDS_OT_step_ps1_wobble(Operator):
    bl_idname = "sds.step_ps1_wobble"
    bl_label = "Step Wobble (+2f) · 单步测试顶点跳格"
    bl_description = "将时间轴安全推进 2 帧，由 Blender 原生 Geometry Nodes 引擎计算 PS1 GTE 顶点跳变"

    def execute(self, context):
        from . import dreamspace
        props = context.scene.sds_props
        if getattr(props, "ps1_vertex_snap", 0.0) < 0.001 or getattr(props, "ps1_vertex_snap", 0.0) > 0.020:
            props.ps1_vertex_snap = 0.006
        dreamspace.unregister_ps1_frame_handler()
        dreamspace.ensure_ps1_gte_geonodes(props)
        cur_f = int(getattr(context.scene, "frame_current", 1)) + 2
        if cur_f > 240:
            cur_f = 1
        if hasattr(context.scene, "frame_set"):
            context.scene.frame_set(cur_f)
        else:
            context.scene.frame_current = cur_f
        self.report({"INFO"}, f"PS1 GTE Wobble: Frame {cur_f} (Snap={props.ps1_vertex_snap:.2f}m)")
        return {"FINISHED"}




class SDS_OT_apply_texture_tool(Operator):
    bl_idname = "sds.apply_texture_tool"
    bl_label = "Apply Era Texture · 赋予选中物体"
    bl_description = "按当前选定的图形学纹理思路、基底母型、CLUT 调色板与预烘焙做旧参数生成材质，并一键赋予选中的模型"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        from . import texture_workbench
        props = context.scene.sds_props
        count = texture_workbench.apply_workbench_texture_to_selected(context, props)
        self.report(
            {"INFO"},
            f"Texture Workbench: 已将 [{props.tex_synth_paradigm} / {props.tex_archetype}] 材质赋予 {count} 个物体",
        )
        return {"FINISHED"}


class SDS_OT_retrofy_materials(Operator):
    bl_idname = "sds.retrofy_materials"
    bl_label = "Retro-fy Existing Material · 改造现有贴图/材质"
    bl_description = "保留选中物体原有的贴图 (Image Texture)，自动注入最近邻纹素网格量化 (SNAP) 与年代硬件管线节点组"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        from . import texture_workbench
        props = context.scene.sds_props
        count = texture_workbench.retrofy_selected_object_materials(context, props)
        self.report({"INFO"}, f"Texture Workbench: 已对 {count} 个材质注入复古纹素量化与硬件管线")
        return {"FINISHED"}


class SDS_OT_build_texture_nodegroups(Operator):
    bl_idname = "sds.build_texture_nodegroups"
    bl_label = "Build 5 Era NodeGroups · 生成 5 大图形学节点组库"
    bl_description = "在当前 .blend 文件中生成 5 个标准化的可复用图形学纹理节点组 (可在 Shader Editor -> Add -> Group 中随时调用)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        from . import texture_workbench
        names = texture_workbench.ensure_reusable_texture_node_groups()
        self.report({"INFO"}, f"已生成 {len(names)} 个可复用图形学纹理节点组: {', '.join(names)}")
        return {"FINISHED"}


class SDS_OT_cycle_clut_palette(Operator):
    bl_idname = "sds.cycle_clut_palette"
    bl_label = "Cycle CLUT Palette · 轮换 CLUT 调色板"
    bl_description = "模拟 PS1 / LSD 在显存中直接切换 16 色 CLUT 调色板查表地址，一键切换当前材质的年代配色表"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        from . import texture_workbench
        props = context.scene.sds_props
        order = [
            "REALISTIC_GRIME",
            "WARM_LANTERN",
            "COLD_FLUORESCENT",
            "ICO_SUNLIT_OCHRE",
            "LSD_ACID_RAINBOW",
            "BLOOD_RUST",
        ]
        cur = getattr(props, "tex_clut_palette", "REALISTIC_GRIME")
        nxt = order[(order.index(cur) + 1) % len(order)] if cur in order else order[0]
        props.tex_clut_palette = nxt
        texture_workbench.apply_workbench_texture_to_selected(context, props)
        self.report({"INFO"}, f"CLUT Palette Switched -> {nxt}")
        return {"FINISHED"}


CLASSES = (
    SDS_OT_apply_texture_tool,
    SDS_OT_retrofy_materials,
    SDS_OT_build_texture_nodegroups,
    SDS_OT_cycle_clut_palette,
    SDS_OT_play_ps1_wobble,
    SDS_OT_step_ps1_wobble,
    SDS_OT_generate_scene,
    SDS_OT_regenerate_terrain,
    SDS_OT_randomize_scene,
    SDS_OT_apply_world_preset,
    SDS_OT_set_relief_level,
    SDS_OT_set_render_profile,
    SDS_OT_save_recipe,
    SDS_OT_load_recipe,
    SDS_OT_render_preview,
)
