# SPDX-License-Identifier: GPL-3.0-or-later
"""
Scene PropertyGroup definitions for Silicon Dreams Studio v2.1.
Adds `_on_live_terrain_param_changed` so dragging any slider or switching landform mode
in `02 — TERRAIN LAB` immediately updates the terrain mesh and shader in the viewport!
"""

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
)
from bpy.types import PropertyGroup

from . import presets, terrain, materials, sky_atmosphere, scene_composer


def _on_preset_changed(self, context):
    if getattr(self, "is_applying_preset", False):
        return
    presets.apply_preset_to_props(self, self.world_preset)
    if getattr(self, "auto_update_scene", True) and context is not None:
        scene_composer.compose_full_scene(context, self)


def _on_live_terrain_param_changed(self, context):
    """Live updates the terrain heightfield mesh & material whenever a Terrain Lab control changes."""
    if getattr(self, "is_applying_preset", False) or context is None:
        return
    if not getattr(self, "auto_update_scene", True):
        return
    col = scene_composer.ensure_sds_collection(context)
    if col is None:
        return
    try:
        t_mat = materials.build_terrain_material(self)
        terrain.generate_or_update_terrain(context, self, col, terrain_mat=t_mat)
    except Exception:
        pass


def _on_live_shader_param_changed(self, context):
    if getattr(self, "is_applying_preset", False) or context is None:
        return
    if not getattr(self, "auto_update_scene", True):
        return
    col = bpy.data.collections.get(scene_composer.COLLECTION_NAME)
    if col is None:
        return
    try:
        materials.build_terrain_material(self)
        scene_composer._setup_water_plane(context, self, col)
        sky_atmosphere.setup_sky_and_atmosphere(context, self, col)
        scene_composer.apply_render_profile(context, self)
    except Exception:
        pass


def _on_live_hero_param_changed(self, context):
    if getattr(self, "is_applying_preset", False) or context is None:
        return
    if not getattr(self, "auto_update_scene", True):
        return
    col = scene_composer.ensure_sds_collection(context)
    if col is None:
        return
    try:
        scene_composer._compose_hero_objects(context, self, col)
        scene_composer.setup_camera_framing(context, self, col)
    except Exception:
        pass



def _on_era_pipeline_changed(self, context):
    if getattr(self, "is_applying_preset", False):
        return
    was_guard = self.is_applying_preset
    self.is_applying_preset = True
    try:
        era = self.era_pipeline
        if era == "BRYCE_1997":
            self.render_engine_mode = "WHITTED_1997"
            self.reflection_model = "WHITTED_RAYTRACE"
            self.shading_interpolation = "PHONG_SMOOTH"
            self.flat_shaded_terrain = False
            self.low_poly_primitives = False
            self.vintage_specular = True
            self.ps1_vertex_snap = 0.0
            self.ps1_affine_warp = 0.0
            self.ps2_bloom_intensity = 0.0
            self.ps2_vpu_wave = 0.0
            self.color_quantization_steps = 255
            self.render_profile = "RES_640"
        elif era == "PS1_1998_LSD":
            self.render_engine_mode = "WHITTED_1997"
            self.reflection_model = "SPHERICAL_ENVMAP"
            self.shading_interpolation = "FLAT_FACETED"
            self.flat_shaded_terrain = True
            self.low_poly_primitives = True
            self.vintage_specular = False
            self.mesh_resolution = "RES_24"
            self.ps1_vertex_snap = 0.006
            self.ps1_affine_warp = 65.0
            self.ps2_bloom_intensity = 0.0
            self.ps2_vpu_wave = 0.0
            self.color_quantization_steps = 32
            self.render_profile = "RES_320"
        elif era == "DC_1999_POWERVR2":
            self.render_engine_mode = "WHITTED_1997"
            self.reflection_model = "SPHERICAL_ENVMAP"
            self.shading_interpolation = "GOURAUD_VERTEX"
            self.flat_shaded_terrain = False
            self.low_poly_primitives = False
            self.vintage_specular = True
            self.mesh_resolution = "RES_64"
            self.ps1_vertex_snap = 0.0
            self.ps1_affine_warp = 0.0
            self.dc_alpha_glow = 90.0
            self.dc_trilinear_sharpness = 90.0
            self.ps2_bloom_intensity = 35.0
            self.color_quantization_steps = 255
            self.render_profile = "RES_640"
        elif era == "PS2_2000_EE":
            self.render_engine_mode = "WHITTED_1997"
            self.reflection_model = "SPHERICAL_ENVMAP"
            self.shading_interpolation = "GOURAUD_VERTEX"
            self.flat_shaded_terrain = False
            self.low_poly_primitives = False
            self.vintage_specular = False
            self.mesh_resolution = "RES_64"
            self.ps1_vertex_snap = 0.0
            self.ps1_affine_warp = 0.0
            self.ps2_bloom_intensity = 78.0
            self.ps2_vpu_wave = 25.0
            self.color_quantization_steps = 255
            self.render_profile = "RES_640"
        elif era == "PC_1997_REALTIME":
            self.render_engine_mode = "EEVEE_REALTIME"
            self.reflection_model = "SPHERICAL_ENVMAP"
            self.shading_interpolation = "GOURAUD_VERTEX"
            self.flat_shaded_terrain = True
            self.low_poly_primitives = True
            self.vintage_specular = True
            self.mesh_resolution = "RES_64"
            self.ps1_vertex_snap = 0.0
            self.ps1_affine_warp = 0.0
            self.ps2_bloom_intensity = 0.0
            self.color_quantization_steps = 64
            self.render_profile = "RES_640"
    finally:
        self.is_applying_preset = was_guard
    if getattr(self, "auto_update_scene", True) and context is not None:
        scene_composer.compose_full_scene(context, self)


def _on_live_dreamspace_changed(self, context):
    if getattr(self, "is_applying_preset", False) or context is None:
        return
    if not getattr(self, "auto_update_scene", True):
        return
    col = scene_composer.ensure_sds_collection(context)
    if col is None:
        return
    try:
        from . import dreamspace
        t_mat = materials.build_terrain_material(self)
        t_obj = bpy.data.objects.get("SDS_Terrain")
        if t_obj is not None and t_obj.type == "MESH":
            if len(t_obj.data.materials) == 0:
                t_obj.data.materials.append(t_mat)
            else:
                t_obj.data.materials[0] = t_mat
            dreamspace.apply_era_geometry_modifiers(t_obj, self)
        dreamspace.compose_dreamspace(context, self, col)
        dreamspace.ensure_ps1_gte_geonodes(self)
        dreamspace.ensure_ps2_vpu_geonodes(self)
    except Exception:
        pass




def _on_live_workbench_changed(self, context):
    if getattr(self, "is_applying_preset", False) or context is None:
        return
    if not getattr(self, "auto_update_scene", True):
        return
    try:
        from . import texture_workbench
        texture_workbench.build_workbench_material(self)
    except Exception:
        pass


class SDS_SceneProperties(PropertyGroup):
    is_applying_preset: BoolProperty(
        name="Internal Preset Guard",
        default=False,
        options={"SKIP_SAVE", "HIDDEN"},
    )
    auto_update_scene: BoolProperty(
        name="实时同步地形与材质 (Live Sync)",
        description="开启后，在 Terrain Lab 或色彩面板中拖动滑块会立即实时更新 3D 场景",
        default=True,
    )

    # 01 — ERA PIPELINE & WORLD PRESET (`a.txt`, `b.txt`, `c.txt`)
    era_pipeline: EnumProperty(
        name="技术年代路线 (Era Hardware Pipeline)",
        description="选择四类 20 世纪末至 21 世纪初经典 3D 图形学硬件与渲染管线",
        items=[
            ("BRYCE_1997", "I. 1997 Bryce / POV-Ray 离线光线追踪", "DTE 程序化实体纹理 + Whitted 递归真镜面 + 零 GI 串色"),
            ("PS1_1998_LSD", "II. 1994–1998 PS1 实时硬件 (GTE 顶点抖动 + 折面低模)", "全硬边三角形网格 + GTE 坐标量化抖动 + 邻近像素采样 + 15-bit 色深"),
            ("DC_1999_POWERVR2", "III. 1998–2001 Sega Dreamcast · PowerVR2 TBDR", "透视校正三线性纹理 + Gouraud 光照 + 球面环境映射 + 硬件多层半透明光晕"),
            ("PS2_2000_EE", "IV. 2000–2005 PS2 Emotion Engine & GS 帧缓冲", "透视校正纹理 + 高吞吐古堡遗迹几何 + GS 帧缓冲过曝柔光 (Bloom) 与深雾"),
            ("PC_1997_REALTIME", "V. 1997 PC 早期 3D 加速 (3dfx / OpenGL)", "Gouraud/Flat 着色 + 球面环境反射贴图 (GL_SPHERE_MAP) + Z-Buffer 雾"),
        ],
        default="BRYCE_1997",
        update=_on_era_pipeline_changed,
    )
    reflection_model: EnumProperty(
        name="反射技术路线 (Reflection Model)",
        description="区分离线光线追踪真反射与实时球面环境映射 (a.txt Section 2.06)",
        items=[
            ("WHITTED_RAYTRACE", "离线 Whitted 递归光线追踪 (True Raytracing)", "精确反射场景中的棋盘格、山体与其它球体"),
            ("SPHERICAL_ENVMAP", "实时球面环境映射 (1997 Spherical EnvMap)", "使用 Reflection 向量直接查表映射天空地平线，零光线追踪开销"),
        ],
        default="WHITTED_RAYTRACE",
        update=_on_live_shader_param_changed,
    )
    shading_interpolation: EnumProperty(
        name="多边形着色插值 (Shading Interpolation)",
        description="区分 Flat 平面着色、Gouraud 顶点插值与 Phong 法线插值 (a.txt Section 2.04)",
        items=[
            ("FLAT_FACETED", "Flat Shading · 平面折面着色", "突出每个三角形/四边形面片的硬朗明暗边界"),
            ("GOURAUD_VERTEX", "Gouraud Style · 早期顶点插值风格", "柔和无锐利镜面高光的早期实时多边形插值"),
            ("PHONG_SMOOTH", "Phong Shading · 法线插值与锐利高光", "平滑插值表面法线并计算紧凑高光"),
        ],
        default="PHONG_SMOOTH",
        update=_on_live_terrain_param_changed,
    )
    dream_architecture_mode: EnumProperty(
        name="LSD 梦境空间拼接 (Spatial Graph Stitching)",
        description="《LSD: Dream Emulator》式空间图拼接：在自然地貌与人工建筑走廊之间制造超现实连接 (b.txt Section 3.1)",
        items=[
            ("NONE", "无梦境建筑 (Pure Landscape / Primitives)", "仅生成 Bryce 地形与经典几何体"),
            ("BRIGHT_MOON_COTTAGE", "LSD 明月庄 (Bright Moon Cottage P3-P6)", "复刻 P3-P6：四层像素混凝土大楼、一楼黑白棋盘吧台、障子门与低模六棱树"),
            ("KOWLOON_WALLED_ALLEY", "九龙风水传城寨暗巷 (Kowloon's Gate P1-P2)", "复刻 P1-P2：铁卷门、瓷砖柱、头顶管道、发光招牌与红消防栓"),
            ("LSD_TURTLE_HILLS", "LSD 靶心原野与低模巨龟 (Psychedelic Turtle)", "复刻新参考图1：墨绿黑夜像素云、同心圆彩虹靶心像素砖山坡与低模巨龟"),
            ("LSD_GRAY_MAN_PLAZA", "LSD 紫天符文墙与灰衣帽子男 (The Gray Man)", "复刻新参考图2：紫红魔天、刺日图腾、蓝紫符文墙、紫砖广场与灰衣帽子男"),
            ("LSD_FLESH_TUNNEL", "LSD 红雾血肉扭曲隧道 (Flesh Tunnel & Doll)", "复刻新参考图3：八角血肉隧道、下壁极端纵向UV拉伸、刺眼纯红浓雾与中央玩偶"),
            ("LSD_GRAFFITI_CORRIDOR", "LSD 波点地板与噪点涂鸦长廊 (Graffiti Hall)", "复刻新参考图4：白底彩色波点地板、重度抖动噪点绿/黄/红涂鸦墙与纯黑深雾"),
            ("LSD_KANJI_EYE_GIANT", "LSD 独眼汉字巨像与绿蓝方砖 (Kanji Eye Giant)", "复刻上传图2：绿蓝像素波纹方砖广场、苔藓矮墙、十字星芒太阳与紫色汉字独眼巨像"),
            ("LSD_KYOTO_KIMONO_NIGHT", "LSD 京都夜街木屋与低模和服女 (Kyoto Kimono Night)", "复刻上传图3：深邃夜空、砂石地面、青黑条纹瓦顶京都木屋与平面着色低模和服女"),
            ("ICO_CASTLE_BRIDGE", "PS2《ICO》古堡拱桥与铁栏长阶 (2001 ICO Viaduct)", "复刻 PS2 实机图：高架石砌双拱桥墩、悬崖突出石台、上升石阶与尖刺铁护栏"),
            ("DC_WATERFALL_ARENA", "Dreamcast 瀑布峡谷与战机尾焰 (PowerVR2 Arena)", "复刻 DC 实机图：半环形青白瀑布崖壁、3 座青铜水闸塔、翡翠发光岩与双喷口战机"),
            ("ICO_CASTLE_BRIDGE", "PS2《ICO》古堡拱桥与铁栏长阶 (2001 ICO Viaduct)", "复刻 PS2 实机图：高架石砌双拱桥墩、悬崖突出石台、上升石阶与尖刺铁护栏"),
            ("DC_WATERFALL_ARENA", "Dreamcast 瀑布峡谷与战机尾焰 (PowerVR2 Arena)", "复刻 DC 实机图：半环形青白瀑布崖壁、3 座青铜水闸塔、翡翠发光岩与双喷口战机"),
            ("ICO_CASTLE_BRIDGE", "PS2《ICO》古堡拱桥与铁栏长阶 (2001 ICO Viaduct)", "复刻 PS2 实机图：高架石砌双拱桥墩、悬崖突出石台、上升石阶与尖刺铁护栏"),
            ("DC_WATERFALL_ARENA", "Dreamcast 瀑布峡谷与战机尾焰 (PowerVR2 Arena)", "复刻 DC 实机图：半环形青白瀑布崖壁、3 座青铜水闸塔、翡翠发光岩与双喷口战机"),
            ("ICO_CASTLE_BRIDGE", "PS2《ICO》古堡拱桥与铁栏长阶 (2001 ICO Viaduct)", "复刻 PS2 实机图：高架石砌双拱桥墩、悬崖突出石台、上升石阶与尖刺铁护栏"),
            ("DC_WATERFALL_ARENA", "Dreamcast 瀑布峡谷与战机尾焰 (PowerVR2 Arena)", "复刻 DC 实机图：半环形青白瀑布崖壁、3 座青铜水闸塔、翡翠发光岩与双喷口战机"),
            ("ICO_CASTLE_BRIDGE", "PS2《ICO》古堡拱桥与铁栏长阶 (2001 ICO Viaduct)", "复刻 PS2 实机图：高架石砌双拱桥墩、悬崖突出石台、上升石阶与尖刺铁护栏"),
            ("DC_WATERFALL_ARENA", "Dreamcast 瀑布峡谷与战机尾焰 (PowerVR2 Arena)", "复刻 DC 实机图：半环形青白瀑布崖壁、3 座青铜水闸塔、翡翠发光岩与双喷口战机"),
            ("CORRIDOR_TO_HILLS", "走廊直通山坡 (Corridor to Hillside)", "前景封闭走廊出口直接通往室外分形山坡与湖泊"),
            ("WALLED_COMPOUND", "空旷围墙院落与无功能楼群 (Hollow Compound)", "带门窗却无内部用途的重复空心建筑与围合院落"),
            ("IMPOSSIBLE_STAIRS_TOWERS", "断头浮空长阶与高塔 (Floating Stairs & Towers)", "通往半空的失重阶梯与高耸立面塔楼"),
            ("MIXED_DREAM_GRAPH", "完整 LSD 空间图拼接 (Full Dream Graph)", "走廊 + 失重断梯 + 异质高塔完整梦境空间组合"),
        ],
        default="NONE",
        update=_on_live_dreamspace_changed,
    )
    texture_mismatch_mode: EnumProperty(
        name="异质纹理分配系统 (Heterogeneous Textures)",
        description="控制物体与纹理类别的匹配或跨类别错配关系 (b.txt Section 3.3)",
        items=[
            ("SEMANTIC", "语义匹配 (Semantic Match)", "建筑使用砖墙/立面网格，山体使用自然岩石与草地"),
            ("WEAK_RANDOM", "弱随机似曾相识 (Weak Random Variants)", "重复建筑模块随机切换不同配色与窗户密度"),
            ("CROSS_MISMATCH", "跨类别异质错配 (Cross-Category Mismatch)", "山体表面出现重复建筑窗户立面，建筑表面出现水面/棋盘格/彩虹纹理"),
            ("LOCAL_MUTATION", "局部纹理突变 (Local Patch Mutation)", "在同一表面内突发混入另一类异质纹理斑块"),
        ],
        default="SEMANTIC",
        update=_on_live_dreamspace_changed,
    )
    dream_scale_anomaly: FloatProperty(
        name="尺度与比例异常 (Scale Anomaly)",
        description="制造建筑尺度突变与门窗高宽比失调 (b.txt Section 3.2)",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
        update=_on_live_dreamspace_changed,
    )
    dream_tilt_anomaly: FloatProperty(
        name="局部重力倾斜 (Gravity / Ground Tilt)",
        description="制造建筑与走廊的微妙重力方向偏移 (度数)",
        default=0.0,
        min=-25.0,
        max=25.0,
        update=_on_live_dreamspace_changed,
    )
    ps1_vertex_snap: FloatProperty(
        name="PS1 顶点坐标量化抖动 (GTE Vertex Wobble)",
        description="模拟 PS1 16-bit 整数坐标截断导致的顶点网格吸附与几何抖动 (米)",
        default=0.0,
        min=0.0,
        max=0.025,
        update=_on_live_dreamspace_changed,
    )
    ps1_affine_warp: FloatProperty(
        name="PS1 仿射纹理扭曲 (Affine UV Warp)",
        description="模拟缺乏 1/z 透视校正导致的斜面纹理拉伸与剪切变形",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
        update=_on_live_dreamspace_changed,
    )
    ps1_vram_grit: FloatProperty(
        name="PS1 4×4 硬件抖动与显存脏化颗粒 (Bayer Dither & Grit)",
        description="模拟 PS1 4-bit/8-bit CLUT 调色板抖动矩阵、像素噪点颗粒与顶点暗角污渍，消除过于干净的现代感",
        default=82.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
        update=_on_live_dreamspace_changed,
    )
    ps2_vpu_wave: FloatProperty(
        name="PS2 VPU 顶点风场微变形 (VPU Vertex Wave)",
        description="模拟 PS2 VU1 向量协处理器对环境与水面施加的实时正弦顶点微变形 (c.txt Section 1)",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
        update=_on_live_dreamspace_changed,
    )
    dc_alpha_glow: FloatProperty(
        name="PowerVR2 多层半透明光晕 (TBDR Alpha Glow)",
        description="模拟 Sega Dreamcast PowerVR2 硬件顺序无关多层半透明叠加尾焰与等离子光晕 (d.txt Section 4)",
        default=85.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
        update=_on_live_shader_param_changed,
    )
    dc_trilinear_sharpness: FloatProperty(
        name="PowerVR2 透视校正三线性锐度 (Trilinear Clarity)",
        description="模拟 Dreamcast 透视校正 UV 与三线性过滤的高清锐利大尺度自然纹理 (d.txt Section 2)",
        default=85.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
        update=_on_live_shader_param_changed,
    )
    ps2_bloom_intensity: FloatProperty(
        name="PS2 帧缓冲过曝柔光 (GS Framebuffer Bloom)",
        description="模拟 PS2《ICO》《汪达与巨像》利用高带宽帧缓冲实现的柔光发光后处理 (c.txt Section 2.4)",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
        update=_on_live_shader_param_changed,
    )
    world_preset: EnumProperty(
        name="风格预设 (World Preset)",
        description="选择 1997 Bryce 3D / POV-Ray 3.0 风格预设配方",
        items=presets.PRESET_ENUM_ITEMS,
        default="CLASSIC_BRYCE",
        update=_on_preset_changed,
    )

    # 02 — TERRAIN LAB (All wired to `_on_live_terrain_param_changed`!)
    terrain_mode: EnumProperty(
        name="地貌算法 (Landform Mode)",
        items=[
            ("FRACTAL_MOUNTAINS", "经典 Bryce 分形雪山 (Bryce Mountains)", "复刻 1997 Bryce 3D 主峰 + 两侧绿丘 + 前景镜面湖构图"),
            ("KARST_DOMES", "群峰花岗岩穹顶 (Bryce Granite Domes)", "复刻经典多层次花岗岩圆顶群峰与翠绿山谷"),
            ("ISOLATED_PEAKS", "异星孤峰与海岸礁石 (Alien Island Spire)", "险峻火山孤岛主峰与远方次峰"),
            ("COASTAL_ARCHIPELAGO", "海岸与群岛 (Coastal Archipelago)", "柔和起伏的海岸线与群岛"),
            ("BASIN_CRATER", "盆地与环形山 (Basin & Crater)", "中央凹陷的环形山与盆地结构"),
            ("CANYON_CLIFFS", "悬崖与峡谷 (Canyon Cliffs)", "曲折河谷切割的高原悬崖"),
            ("FLOATING_ISLANDS", "浮空岛屿 (Floating Islands)", "超现实主义悬浮分形岛群"),
            ("CHECKER_PLANE", "无尽平面 (Infinite Plane)", "用于棋盘格布尔拱门、落日苔原或云纹实验室的无尽地面"),
        ],
        default="FRACTAL_MOUNTAINS",
        update=_on_live_terrain_param_changed,
    )
    terrain_relief: FloatProperty(
        name="山脉起伏 (Mountain Relief)",
        default=64.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
        update=_on_live_terrain_param_changed,
    )
    fractal_detail: FloatProperty(
        name="分形细节 (Fractal Detail)",
        default=54.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
        update=_on_live_terrain_param_changed,
    )
    erosion_strength: FloatProperty(
        name="侵蚀沟壑 (Erosion & Gullies)",
        default=36.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
        update=_on_live_terrain_param_changed,
    )
    sharpness: FloatProperty(
        name="山脊尖锐度 (Ridge Sharpness)",
        default=66.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
        update=_on_live_terrain_param_changed,
    )
    terrain_scale: FloatProperty(
        name="起伏尺度 (Terrain Scale)",
        default=2.6,
        min=0.5,
        max=8.0,
        update=_on_live_terrain_param_changed,
    )
    terrace_steps: IntProperty(
        name="阶地层数 (Terrace Strata)",
        default=0,
        min=0,
        max=24,
        update=_on_live_terrain_param_changed,
    )
    plateau_clip: FloatProperty(
        name="峰顶截断 (Mesa Clip)",
        default=1.0,
        min=0.3,
        max=1.2,
        update=_on_live_terrain_param_changed,
    )
    seed: IntProperty(
        name="随机种子 (Seed)",
        default=1997,
        min=0,
        max=999999,
        update=_on_live_terrain_param_changed,
    )
    scatter_rocks: BoolProperty(
        name="散布岩石 (Optional Rocks)",
        default=False,
        update=_on_live_terrain_param_changed,
    )
    rock_density: FloatProperty(
        name="岩石密度 (Rock Density)",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
        update=_on_live_terrain_param_changed,
    )

    # 03 — 1997 DTE COLOR & ILLUMINATION LAB
    color_contrast_sharpness: FloatProperty(
        name="DTE 色带切割锐度 (Channel Contrast)",
        default=90.0,
        min=10.0,
        max=99.0,
        subtype="PERCENTAGE",
        update=_on_live_shader_param_changed,
    )
    saturation_boost: FloatProperty(
        name="1997 色彩饱和度倍增 (CRT Saturation)",
        default=1.35,
        min=0.8,
        max=2.2,
        update=_on_live_shader_param_changed,
    )
    ambient_strength: FloatProperty(
        name="1997 恒定环境光 (Constant Ambient k_a)",
        default=22.0,
        min=0.0,
        max=60.0,
        subtype="PERCENTAGE",
        update=_on_live_shader_param_changed,
    )
    mirror_reflection: FloatProperty(
        name="纯镜面反射率 (Mirror Reflection)",
        default=95.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
        update=_on_live_shader_param_changed,
    )
    far_fog: FloatProperty(
        name="1997 解析距离雾 (Analytic Depth Fog)",
        default=28.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
        update=_on_live_shader_param_changed,
    )
    enable_water: BoolProperty(
        name="启用水面 / 网格平面 (Enable Water/Grid)",
        default=True,
        update=_on_live_shader_param_changed,
    )
    water_style: EnumProperty(
        name="水面材质风格 (Water Style)",
        items=[
            ("RIPPLE_MIRROR", "Bryce 横向拉丝镜面水 (Ripple Mirror)", "恒定高反射宝蓝拉丝波纹水面"),
            ("CYBER_GRID", "电光蓝发光线框网格 (Electric Cyber Grid)", "复刻 90 年代电光蓝发光坐标网格地面"),
        ],
        default="RIPPLE_MIRROR",
        update=_on_live_shader_param_changed,
    )
    water_level: FloatProperty(
        name="水位高度 (Water Level)",
        default=0.0,
        min=-5.0,
        max=5.0,
        update=_on_live_shader_param_changed,
    )
    wave_chop: FloatProperty(
        name="横向拉丝水波 (Horizontal Ripple)",
        default=32.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
        update=_on_live_shader_param_changed,
    )
    water_color: FloatVectorProperty(
        name="水体色调 (Water Color)",
        subtype="COLOR",
        default=(0.01, 0.06, 0.48),
        min=0.0,
        max=1.0,
        update=_on_live_shader_param_changed,
    )
    sky_zenith_color: FloatVectorProperty(
        name="天顶颜色 (Zenith Color)",
        subtype="COLOR",
        default=(0.18, 0.26, 0.78),
        min=0.0,
        max=1.0,
        update=_on_live_shader_param_changed,
    )
    sky_horizon_color: FloatVectorProperty(
        name="地平线颜色 (Horizon Color)",
        subtype="COLOR",
        default=(0.86, 0.94, 1.00),
        min=0.0,
        max=1.0,
        update=_on_live_shader_param_changed,
    )
    sky_ground_color: FloatVectorProperty(
        name="地底环境色 (Ground Color)",
        subtype="COLOR",
        default=(0.04, 0.06, 0.22),
        min=0.0,
        max=1.0,
        update=_on_live_shader_param_changed,
    )
    cloud_color: FloatVectorProperty(
        name="云霞色彩 (Bryce Cloud Tint)",
        subtype="COLOR",
        default=(0.94, 0.60, 0.66),
        min=0.0,
        max=1.0,
        update=_on_live_shader_param_changed,
    )
    sun_color: FloatVectorProperty(
        name="太阳光色 (Sun Color)",
        subtype="COLOR",
        default=(1.0, 0.96, 0.82),
        min=0.0,
        max=1.0,
        update=_on_live_shader_param_changed,
    )
    sun_elevation: FloatProperty(
        name="太阳高度角 (Sun Elevation)",
        default=28.0,
        min=2.0,
        max=88.0,
        update=_on_live_shader_param_changed,
    )
    sun_azimuth: FloatProperty(
        name="太阳方位角 (Sun Azimuth)",
        default=132.0,
        min=0.0,
        max=360.0,
        update=_on_live_shader_param_changed,
    )
    sun_intensity: FloatProperty(
        name="直射光强度 (Sun Intensity)",
        default=4.2,
        min=0.2,
        max=12.0,
        update=_on_live_shader_param_changed,
    )
    cloud_coverage: FloatProperty(
        name="横向云层密度 (Cloud Coverage)",
        default=58.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
        update=_on_live_shader_param_changed,
    )
    cloud_scale: FloatProperty(
        name="云层尺度 (Cloud Scale)",
        default=3.5,
        min=0.8,
        max=12.0,
        update=_on_live_shader_param_changed,
    )
    enable_celestial_orb: BoolProperty(
        name="巨型天体 / 行星 (Giant Horizon Planet)",
        default=False,
        update=_on_live_shader_param_changed,
    )
    celestial_orb_scale: FloatProperty(
        name="天体尺寸 (Planet Scale)",
        default=18.0,
        min=4.0,
        max=45.0,
        update=_on_live_shader_param_changed,
    )
    terrain_low_color: FloatVectorProperty(
        name="林地翠绿色 (Foothill Green)",
        subtype="COLOR",
        default=(0.02, 0.30, 0.02),
        min=0.0,
        max=1.0,
        update=_on_live_shader_param_changed,
    )
    terrain_mid_color: FloatVectorProperty(
        name="横纹赭石岩色 (Striated Rock)",
        subtype="COLOR",
        default=(0.54, 0.18, 0.02),
        min=0.0,
        max=1.0,
        update=_on_live_shader_param_changed,
    )
    terrain_high_color: FloatVectorProperty(
        name="高亮暖白雪斑 (Bright Snow Patch)",
        subtype="COLOR",
        default=(1.00, 0.96, 0.76),
        min=0.0,
        max=1.0,
        update=_on_live_shader_param_changed,
    )

    # 04 — SCENE LAB & 1997 RENDER PIPELINE
    render_engine_mode: EnumProperty(
        name="1997 渲染管线模式 (Render Pipeline)",
        items=[
            ("WHITTED_1997", "1997 Whitted 光线追踪 (Cycles Zero-GI)", "推荐：关闭漫反射反弹与天空串色，启用 6 次递归真镜面反射与硬阴影"),
            ("EEVEE_REALTIME", "EEVEE 实时光栅预览 (Viewport Raster)", "使用 EEVEE 快速预览"),
        ],
        default="WHITTED_1997",
        update=_on_live_shader_param_changed,
    )
    hero_composition: EnumProperty(
        name="几何体构图 (Hero Composition)",
        items=[
            ("TERRAIN_ONLY", "纯自然 Bryce 数字景观 (Landscape Only)", "复刻 1997 Bryce 3D 纯净山水湖泊与云霞"),
            ("RAYTRACED_SHOWCASE", "1997 CSG 镀铬布尔拱廊与铬球 (POV-Ray Arch & Orbs)", "四向圆拱掏空镀铬方亭 + 8 颗环绕纯镜面铬球"),
            ("ISLAND_BIODOME", "异星孤岛镀铬基地与绿晶台 (Island Bio-Dome)", "镀铬圆顶基地 + 红方尖碑 + 黄金绿晶圆台"),
            ("RUBY_MONOLITH_DESERT", "落日红宝石方碑与竖立铜环 (Ruby Monolith & Torus)", "半透明红宝石方碑 + 竖立铜环 + 悬浮眼球天体"),
            ("CYBER_GLASS_SLAB", "电光网格与折射玻璃方体 (Cyber Glass Box)", "前景透明折射玻璃方体"),
            ("CLASSIC_MONOLITH", "孤立镀铬球与环轨 (Classic Orb & Ring)", "湖面中央悬浮的镀铬球与轨道环"),
            ("SPHERES_PYRAMIDS", "金字塔与漂浮彩球 (Pyramids & Floating Orbs)", "黄金砂岩金字塔与多材质漂浮球"),
            ("AERO_BUBBLES", "透明生态气泡群 (Aero Glass Bubbles)", "Frutiger Aero 风格漂浮透明折射球体"),
            ("SURREAL_MEGASCALE", "超尺度天体光环 (Surreal Megascale)", "悬浮在山脉上空的巨型彩虹球体与金属光环"),
        ],
        default="TERRAIN_ONLY",
        update=_on_live_hero_param_changed,
    )
    hero_material_style: EnumProperty(
        name="主几何材质 (Hero Material)",
        items=[
            ("CHROME", "纯镜面镀铬 (1997 Mirror Chrome)", "零粗糙度 100% 递归光线追踪镀铬"),
            ("GLASS", "透明折射玻璃 (Raytraced Glass)", "清澈折射玻璃"),
            ("RUBY_GLASS", "红宝石半透明碑 (Ruby Monolith Glass)", "落日红宝石透光玻璃"),
            ("COPPER_METAL", "落日黄铜金属 (Sunset Copper)", "高反射暖橙黄铜金属"),
            ("MARBLE_ORB", "程序化云纹大理石 (Bryce Cloud Marble)", "Bryce 标志性程序化云纹反射球材质"),
            ("PLASTIC", "高光饱和塑料 (Vintage Glossy Plastic)", "90 年代 CGI 强高光饱和塑料"),
            ("RAINBOW", "彩虹光谱渐变 (Rainbow Spectrum)", "高饱和光谱金属渐变"),
            ("PLANET_LAVA", "熔岩发光体 (KPT Lava Planet)", "KPT Bryce 1.0 风格发光火山熔岩纹理"),
        ],
        default="CHROME",
        update=_on_live_hero_param_changed,
    )
    hero_count: IntProperty(
        name="几何体数量 (Object Count)",
        default=8,
        min=1,
        max=12,
        update=_on_live_hero_param_changed,
    )
    hero_scale: FloatProperty(
        name="几何体尺度 (Object Scale)",
        default=1.15,
        min=0.3,
        max=3.5,
        update=_on_live_hero_param_changed,
    )
    camera_preset: EnumProperty(
        name="镜头构图预设 (Camera Framing)",
        items=[
            ("LAKE_REFLECTION", "Bryce 湖面倒影构图 (Lake Reflection)", "复刻 Bryce 3D 经典平视雪山与湖面倒影"),
            ("BMC_LAWN_VIEW", "LSD 明月庄草坪视角 (Bright Moon Cottage P3/P6)", "站在像素绿草坪看向明月庄四层大楼、低模树与一楼吧台"),
            ("KOWLOON_ALLEY_VIEW", "九龙风水传暗巷视角 (Kowloon's Gate P1/P2)", "站在狭窄幽暗城寨巷道看向铁卷门、招牌与红消防栓"),
            ("ICO_BRIDGE_VIEW", "PS2《ICO》古堡拱桥俯角 (ICO Viaduct View)", "斜向俯视石阶、尖刺铁栏杆、悬崖石台与高架双拱桥墩"),
            ("DC_STARFIGHTER_VIEW", "Dreamcast 战机追尾视角 (DC Starfighter Chase)", "在侧倾战机后方平视半环瀑布崖壁、青铜水闸塔与多层半透明尾焰"),
            ("LSD_TURTLE_VIEW", "LSD 靶心原野巨龟视角 (Turtle Hills View)", "低角度平视彩色靶心像素砖斜坡与中央低模巨龟"),
            ("LSD_GRAY_MAN_VIEW", "LSD 灰衣帽子男对峙视角 (Gray Man Encounter)", "正对紫砖广场中央的灰衣帽子男、左侧棱锥与天顶蓝日图腾"),
            ("LSD_FLESH_TUNNEL_VIEW", "LSD 血肉隧道红雾视角 (Flesh Tunnel View)", "沿扭曲血肉隧道看向中央玩偶与尽头刺眼红雾"),
            ("LSD_GRAFFITI_VIEW", "LSD 波点涂鸦长廊斜视 (Graffiti Corridor View)", "斜向观察左侧绿面孔迷幻涂鸦墙、彩色波点地板与深黑远雾"),
            ("LSD_KANJI_GIANT_VIEW", "LSD 独眼汉字巨像仰视 (Kanji Giant View)", "平视绿蓝方砖地面并微仰望紫色汉字独眼巨像与左上角十字星芒太阳"),
            ("LSD_KYOTO_NIGHT_VIEW", "LSD 京都夜街和服女视角 (Kyoto Kimono View)", "前景右侧低模和服女与左侧京都格子窗木屋对望"),
            ("ICO_BRIDGE_VIEW", "PS2《ICO》古堡拱桥俯角 (ICO Viaduct View)", "斜向俯视石阶、尖刺铁栏杆、悬崖石台与高架双拱桥墩"),
            ("DC_STARFIGHTER_VIEW", "Dreamcast 战机追尾视角 (DC Starfighter Chase)", "在侧倾战机后方平视半环瀑布崖壁、青铜水闸塔与多层半透明尾焰"),
            ("ICO_BRIDGE_VIEW", "PS2《ICO》古堡拱桥俯角 (ICO Viaduct View)", "斜向俯视石阶、尖刺铁栏杆、悬崖石台与高架双拱桥墩"),
            ("DC_STARFIGHTER_VIEW", "Dreamcast 战机追尾视角 (DC Starfighter Chase)", "在侧倾战机后方平视半环瀑布崖壁、青铜水闸塔与多层半透明尾焰"),
            ("ICO_BRIDGE_VIEW", "PS2《ICO》古堡拱桥俯角 (ICO Viaduct View)", "斜向俯视石阶、尖刺铁栏杆、悬崖石台与高架双拱桥墩"),
            ("DC_STARFIGHTER_VIEW", "Dreamcast 战机追尾视角 (DC Starfighter Chase)", "在侧倾战机后方平视半环瀑布崖壁、青铜水闸塔与多层半透明尾焰"),
            ("ICO_BRIDGE_VIEW", "PS2《ICO》古堡拱桥俯角 (ICO Viaduct View)", "斜向俯视石阶、尖刺铁栏杆、悬崖石台与高架双拱桥墩"),
            ("DC_STARFIGHTER_VIEW", "Dreamcast 战机追尾视角 (DC Starfighter Chase)", "在侧倾战机后方平视半环瀑布崖壁、青铜水闸塔与多层半透明尾焰"),
            ("ARCH_OVERVIEW", "POV-Ray 布尔拱门俯视 (Arch Overview)", "复刻 1997 棋盘格 CSG 拱门与环绕铬球俯拍视角"),
            ("LOW_HORIZON", "低地平线广角仰视 (Low Horizon 24mm)", "强调辽阔天空与超尺度漂浮物"),
            ("MONUMENT_CENTER", "中心纪念碑构图 (Monument Center)", "聚焦前景金字塔与漂浮球体阵列"),
            ("ISLAND_COAST", "孤岛海岸远眺 (Island Coast)", "斜向眺望险峻岛礁与基地"),
            ("AERIAL_OVERVIEW", "半空鸟瞰全景 (Aerial Overview)", "俯瞰整个分形盆地与水系"),
        ],
        default="LAKE_REFLECTION",
        update=_on_live_hero_param_changed,
    )

    mesh_resolution: EnumProperty(
        name="地形网格精度 (Terrain Mesh Grid)",
        items=[
            ("RES_16", "16 × 16 · PS1 极简大三角面 (Coarse Triangles)", "1995-1997 PS1 大块棱角三角面高度场"),
            ("RES_24", "24 × 24 · PS1 粗折面低模 (PS1 Low-Poly)", "1996-1998 PS1 硬边三角化折面地形"),
            ("RES_64", "64 × 64 · Dreamcast / 中精度网格", "快速预览或 1999 主机高度场"),
            ("RES_128", "128 × 128 · 经典 Bryce 高度场 (推荐)", "还原 Bryce 3D 细腻山脊与侵蚀沟壑"),
            ("RES_192", "192 × 192 · 高精度分形高度场", "展现更丰富的岩层褶皱"),
            ("RES_256", "256 × 256 · 极精细高度场", "超高密度高度场网格"),
        ],
        default="RES_128",
        update=_on_live_terrain_param_changed,
    )
    flat_shaded_terrain: BoolProperty(
        name="折面硬边法线 (Faceted Normals)",
        default=False,
        update=_on_live_terrain_param_changed,
    )
    low_poly_primitives: BoolProperty(
        name="几何体低分段 (Low-Segment Primitives)",
        default=False,
        update=_on_live_hero_param_changed,
    )
    vintage_specular: BoolProperty(
        name="早期 Phong 式强高光 (90s Specular)",
        default=True,
        update=_on_live_shader_param_changed,
    )
    hard_shadows: BoolProperty(
        name="1997 锐利光线追踪硬阴影 (Hard Raytraced Shadows)",
        default=True,
        update=_on_live_shader_param_changed,
    )

    # 05 — RENDER PROFILE
    render_profile: EnumProperty(
        name="渲染尺寸配置 (Render Profile)",
        items=[
            ("RES_320", "320 × 240 · 低分辨率测试", "QVGA (4:3)"),
            ("RES_640", "640 × 480 · 经典 1997 CGI", "VGA (4:3) 1997 Bryce 3D 标准分辨率"),
            ("RES_1024", "1024 × 768 · 高分辨率", "XGA (4:3)"),
            ("RES_1920", "1920 × 1080 · 现代高清", "1080p (16:9)"),
        ],
        default="RES_640",
        update=_on_live_shader_param_changed,
    )
    enable_retro_compositor: BoolProperty(
        name="启用 1997 饱和度与对比度增强管线 (1997 Color Boost)",
        default=True,
        update=_on_live_shader_param_changed,
    )
    color_quantization_steps: IntProperty(
        name="色彩量化阶数 (255=无色带)",
        default=255,
        min=16,
        max=255,
        update=_on_live_shader_param_changed,
    )
    retro_pixel_scale: FloatProperty(
        name="像素采样缩放 (Pixel Scale)",
        default=1.0,
        min=1.0,
        max=4.0,
    )



    # =========================================================================
    # 05 — TEXTURE SYNTHESIS WORKBENCH (四大图形学纹理思路与工具台)
    # =========================================================================
    tex_synth_paradigm: EnumProperty(
        name="图形学纹理思路 (Texture Paradigm)",
        description="选择四类历史图形学的核心纹理生成思路",
        items=[
            ("DTE_1997_SOLID", "I. 1997 Bryce DTE · 3D 实体标量场合成", "零 UV 接缝 3D 连续空间多频噪声 + 海拔/坡度色阶滤波"),
            ("PS1_PREBAKED_CLUT", "II-A. 1997 PS1 写实预烘焙做旧 + 纹素网格", "九龙风水传/寂静岭思路：三平面投影 + 预烘焙砖缝暗角/水渍 + 微颗粒 + CLUT 量化"),
            ("PS1_CLUT_PSYCHEDELIC", "II-B. 1998 PS1 4-bit CLUT 调色板置换", "LSD 梦境模拟器思路：方格纹素量化 + 16 色 CLUT 调色板查表置换"),
            ("DC_POWERVR2_ARCADE", "III. 1999 Dreamcast · 三线性清澈贴图 + 球面反射", "PowerVR2 透视校正三线性过滤 + GL_SPHERE_MAP 金属环境贴图"),
            ("PS2_GS_MULTIPASS", "IV. 2001 PS2 GS · 四遍叠加风化 (Multi-Pass)", "ICO/汪达思路：宏观砌块 + 18x 高频微砂砾细节 + 纵向青苔水痕 + eDRAM 柔光"),
        ],
        default="PS1_PREBAKED_CLUT",
        update=_on_live_workbench_changed,
    )
    tex_archetype: EnumProperty(
        name="基底纹理母型 (Material Archetype)",
        description="选择要合成的纹理结构母型（均采用三平面正交映射，绝不在墙面拉出竖条纹）",
        items=[
            ("CERAMIC_MOSAIC", "城寨马赛克磁砖与灰缝水渍 (Ceramic Mosaic)", "10cm×10cm 方块磁砖 + 凹槽灰缝 + 纵向污垢"),
            ("CORRUGATED_SHUTTER", "做旧瓦楞铁卷门与氧化斑 (Corrugated Shutter)", "细密横向金属瓦楞条 + 铁锈油污微颗粒"),
            ("ASHLAR_SANDSTONE", "古堡风化砂岩石砌与青苔 (Ashlar Sandstone)", "ICO 风格错缝砂岩石块 + 微细砂砾 + 青苔水痕"),
            ("WEATHERED_TIMBER", "传统木构板材与木格 (Weathered Timber)", "京都町家/排档做旧木纹板与暗角"),
            ("DAMP_ASPHALT_STONE", "潮湿深色石板路与水洼 (Damp Stone Paving)", "城寨/夜街深色潮湿石板与暗部水迹"),
            ("CAST_IRON_PAINT", "掉漆铸铁与复古金属 (Chipped Cast Iron)", "消防栓/水闸塔做旧掉漆金属表面"),
            ("NEON_LIGHTBOX", "港式背光亚克力灯箱 (Backlit Lightbox)", "自发光暖黄亚克力灯箱与金属边框"),
            ("BRYCE_STRIATED_ROCK", "Bryce DTE 三通道条纹岩 (DTE Striated Rock)", "1997 离线 3D 实体分层岩脉与斑驳植被"),
            ("LSD_CLUT_PATTERN", "LSD 靶心/波点迷幻方砖 (LSD CLUT Tiles)", "高饱和 4-bit CLUT 几何图案方砖"),
            ("DC_WATERFALL_ENERGY", "Dreamcast 飞瀑流光/等离子 (DC Waterfall/Plasma)", "高明度透视三线性流光纹理"),
        ],
        default="CERAMIC_MOSAIC",
        update=_on_live_workbench_changed,
    )
    tex_res_grid: EnumProperty(
        name="纹素网格精度 (Texel Resolution)",
        items=[
            ("TEX_16", "16 × 16 · 极粗 4-bit 像素块", "早期微缩贴图网格"),
            ("TEX_32", "32 × 32 · 经典 PS1 子贴图", "标准 PS1 像素颗粒感"),
            ("TEX_64", "64 × 64 · 细腻 PS1 / 城寨贴图 (推荐)", "兼顾像素质感与丰富表面细节"),
            ("TEX_128", "128 × 128 · 高清复古贴图", "Dreamcast / PS2 级精细贴图"),
            ("TEX_CONT", "无损连续过滤 (Trilinear / 3D Solid)", "无像素马赛克网格"),
        ],
        default="TEX_64",
        update=_on_live_workbench_changed,
    )
    tex_clut_palette: EnumProperty(
        name="CLUT 调色板色表 (Color Look-Up Table)",
        items=[
            ("REALISTIC_GRIME", "九龙写实墨绿灰 (Kowloon Grime)", "城寨做旧淡绿灰与暗铁锈色表"),
            ("WARM_LANTERN", "夜市暖橙街灯 (Warm Lantern)", "暖橙琥珀与深褐木质色表"),
            ("COLD_FLUORESCENT", "冷光日光灯管 (Cold Fluorescent)", "青灰冷白与深海蓝暗巷色表"),
            ("ICO_SUNLIT_OCHRE", "古堡暖阳砂岩 (ICO Sunlit Ochre)", "暖米黄砂岩与暗绿苔藓色表"),
            ("LSD_ACID_RAINBOW", "LSD 迷幻霓虹 (LSD Acid Rainbow)", "高饱和青/品红/亮黄/酸绿撞色表"),
            ("BLOOD_RUST", "寂静铁锈暗红 (Silent Blood Rust)", "焦黑、铁锈褐与暗红血肉色表"),
        ],
        default="REALISTIC_GRIME",
        update=_on_live_workbench_changed,
    )
    tex_prebaked_grit: FloatProperty(
        name="预烘焙污渍与水痕强度 (Pre-Baked Grime & AO)",
        description="在贴图内部预先烘焙砖缝凹槽暗角、墙根潮湿水渍与纵向流淌污垢",
        default=68.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
        update=_on_live_workbench_changed,
    )
    tex_detail_overlay: FloatProperty(
        name="高频微表面细节叠加 (Micro-Grain Detail Pass)",
        description="叠加 18x 高频微表面砂砾/金属拉丝颗粒，消除单层程序化色块的粗糙塑料感",
        default=65.0,
        min=0.0,
        max=100.0,
        subtype="PERCENTAGE",
        update=_on_live_workbench_changed,
    )
    tex_scale_factor: FloatProperty(
        name="纹理空间密度缩放 (Texture Scale)",
        default=1.0,
        min=0.2,
        max=5.0,
        update=_on_live_workbench_changed,
    )


CLASSES = (SDS_SceneProperties,)
