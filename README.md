# Late-90s Graphics Lab (v4.0.0)

**Late-90s Graphics Lab** 是一款专为 **Blender 3.6 – 5.x+** 打造的 20 世纪末至 21 世纪初复古 3D 图形学仿真与场景/纹理生成工作台插件。

本项目并非简单的“像素化滤镜”，而是从**第一性原理（First Principles）**出发，在 Blender 中还原了 **1994–2005 年间四大标志性 3D 图形学技术路线**的几何拓扑约束、定点/浮点坐标精度、纹理采样与调色板机制、硬件光照模型以及帧缓冲后处理管线，并提供完整的**一套四大图形学纹理合成工具箱（Texture Synthesis Workbench）**与 **22 个经典一键世界预设**。

## 核心特性概览

* **四大历史图形学硬件管线仿真**：
  * **【类别 I】1997 离线 CGI · Bryce 3D & POV-Ray (`BRYCE_1997`)**：CPU 递归 Whitted 光线追踪（零漫反射 GI 串色 `diffuse_bounces = 0` + 6 层真镜面反射/折射）、3D 实体程序化深度纹理（Bryce DTE 海拔/坡度三通道滤波）、四阶段分形侵蚀高度场与 CSG 布尔几何构图。
  * **【类别 II】1994–1998 PlayStation 1 实时图形 &《LSD》/《九龙风水传》(`PS1_1998_LSD`)**：Sony GTE 16-bit 视角定点精度截断（`6mm` LSB 微跳步，杜绝现代正弦波橡胶变形）、无 `1/z` 透视校正的仿射 UV 插值、全三角化 `16×16`/`24×24` 零平滑硬边低模、`sds_rest_pos` 静止表面锁定采样、4-bit/8-bit CLUT 调色板与预烘焙污渍做旧、14 阶定点深度雾以及 15-bit (`5-5-5 RGB`) 零抗锯齿输出。
  * **【类别 III】1998–2001 Sega Dreamcast · NEC PowerVR2 TBDR (`DC_1999_POWERVR2`)**：模拟 PowerVR2（CLX2 / Holly）`32×32` 片上分块延迟渲染（TBDR）、硬件 `1/w` 透视校正三线性过滤高饱和纹理、Gouraud 平滑顶点色光照、`GL_SPHERE_MAP` 球面环境反射贴图，以及片上硬件顺序无关多层半透明叠加（Order-Independent Alpha Blending）。
  * **【类别 IV】2000–2005 PlayStation 2 · Emotion Engine & GS (`PS2_2000_EE`)**：模拟 Emotion Engine `VU1` 向量协处理器 32-bit 连续正弦顶点风场微变形（`SDS_PS2_VPU_Wave_GN`）、Graphics Synthesizer（4MB 片上 eDRAM @ 48 GB/s）四遍混合风化贴图（Multi-Pass Weathering）、3D 多层半透明体积圣光片（God-Ray Sun-Shafts）与帧缓冲过曝柔光（Overbright Box-Blur Bloom）。
* **【纹理工具箱】四大图形学纹理合成与改造台 (`texture_workbench.py`)**：
  * 内置 **5 种年代纹理合成思路 × 10 种建筑/自然基底母型 × 6 套历史 CLUT 调色板 × 5 档纹素网格精度**。
  * 全局内置**三平面正交 UV 投影（Triplanar 2D+Z Mapping）**，自动识别水平地面 `(X, Y)` 与垂直墙面/立柱 `(X + Y, Z)`，彻底解决 Blender 2D 砖块/条纹节点在垂直墙面上丢失 Z 轴导致拉出竖条纹的问题。
  * 支持将合成材质**一键赋予任意自定义模型**、**保留原模型图片贴图并一键注入复古纹素量化管线**，以及在当前 `.blend` 文件中**一键生成 5 个标准化可复用 Shader NodeGroups**。
* **纯 Python 内存级网格构建与 Blender 3.6–5.1+ 跨版本兼容**：
  * 所有地形、布尔拱廊、古堡石桥、飞船与梦境建筑均通过 `mesh.clear_geometry()` + `mesh.from_pydata()` 原地更新，**零 `bpy.ops.mesh` 调用**，彻底杜绝频繁切换预设时的 `StructRNA of type Mesh has been removed` 崩溃。
  * 兼容 Blender 4.x/5.x 新版 `ShaderNodeMix` 颜色插槽、`NodeTree.interface` API 以及 Blender 5.0+ `compositing_node_group` 合成器架构，多帧动画渲染（`Ctrl+F12`）100% 线程安全。

## 四大图形学管线技术原理对照

| 维度 | 【类别 I】1997 离线 CGI (`BRYCE_1997`) | 【类别 II】1994–1998 PS1 (`PS1_1998_LSD`) | 【类别 III】1999 Dreamcast (`DC_1999_POWERVR2`) | 【类别 IV】2001 PS2 (`PS2_2000_EE`) |
| :--- | :--- | :--- | :--- | :--- |
| **代表硬件 / 软件** | MetaCreations Bryce 3D, POV-Ray 3.0 | Sony CXD8514Q GTE + 1MB VRAM GPU | Hitachi SH-4 + NEC PowerVR2 (CLX2) | Emotion Engine (`VU0/VU1`) + GS (`4MB eDRAM`) |
| **核心渲染机制** | CPU 递归 Whitted 光线追踪 (`diffuse_bounces=0`) | 定点几何变换 + 无 Z-Buffer 画家算法光栅化 | `32×32` 分块延迟渲染 (TBDR) + 32-bit `1/w` 深度 | 高吞吐向量几何 + 48 GB/s eDRAM 多遍混合 |
| **几何与顶点精度** | 64-bit 浮点精确几何、`128×128+` 侵蚀高度场 | `16×16`/`24×24` 全三角化硬边低模 + `6mm` 视角定点截断 | 平滑曲面网格、零顶点抖动、高多边形机械/地形 | 弧形石拱与高耸遗迹 + `VU1` 连续正弦顶点风场微变形 |
| **纹理采样与坐标** | 零 UV 3D 连续空间程序化标量场 $F(x,y,z)$ | 仿射 UV 线性插值 (`ps1_affine_warp`) + 最近邻方格纹素 (`SNAP`) | 硬件 `1/w` 透视校正 UV + 三线性 Mipmap 过滤 | 透视校正双线性过滤 + 四遍叠加风化 (Macro+Detail+Moss) |
| **光照与反射模型** | Phong 逐像素高光 + 递归真镜面反射与折射 | 恒定平面法线调制 + 局部暖/冷点光源 + 零太阳投射阴影 | Gouraud 顶点色光照 + 硬件 `GL_SPHERE_MAP` 球面反射 | Gouraud 柔和顶点照明 + 3D 多层半透明体积圣光片 |
| **帧缓冲与后处理** | 解析式指数距离雾 + `640×480` 24-bit 真彩色 | 14 阶定点深度雾 + 15-bit (`5-5-5 RGB`) + 零抗锯齿 (`filter=0.01`) | 片上硬件顺序无关多层半透明光晕 + 128 阶硬件雾化表 | GS 帧缓冲下采样过曝柔光 (`FOG_GLOW` Bloom) + 浓雾 |

## 四大图形学纹理合成思路与工具箱

插件在 **`【纹理工具箱】四大图形学纹理合成与改造台`** 面板中将不同时代的贴图制作逻辑抽象为 5 种可交互的合成思路：

| 纹理合成思路 | 还原的历史美术/算法逻辑 | 适用母型与工具化参数 |
| :--- | :--- | :--- |
| **1. 1997 Bryce DTE 3D 实体标量场** (`DTE_1997_SOLID`) | 无需 UV 展开，直接在 3D 连续空间叠加 3 组正交噪声振荡器，按海拔 $Z$ 与法线倾角 $N_z$ 执行高对比色阶滤波 | 适用于分形山体、布尔雕刻体、奇石；支持调节三通道锐度与空间缩放 |
| **2. 1997 PS1 写实预烘焙做旧流** (`PS1_PREBAKED_CLUT`) | 针对 1MB 显存且无实时 AO/凹凸的限制，在贴图内部预先合成**三平面结构层 × 18x 高频微表面颗粒 × 纵向水渍与砖缝暗角**，再执行纹素网格量化 | 复刻《九龙风水传》《寂静岭》写实脏化质感；支持调节 `预烘焙砖缝暗角与水渍` 与 `18x 高频微表面颗粒` |
| **3. 1998 PS1 4-bit CLUT 调色板置换流** (`PS1_CLUT_PSYCHEDELIC`) | 保持底层 16 色灰度几何图案不变，通过切换显存中的 CLUT 调色板查表地址实现强烈的超现实色彩突变 | 复刻《LSD: Dream Emulator》；内置 6 套历史色表并支持一键 `轮换色表` |
| **4. 1999 Dreamcast 三线性 + 球面反射流** (`DC_POWERVR2_ARCADE`) | 告别 PS1 暗沉噪点，采用高明度透视校正三线性基底，叠加视角反射向量 (`Reflection`) 与多层径向半透明发光 | 复刻 Dreamcast 街机清澈质感、金属战机装甲、水闸高塔与等离子光晕 |
| **5. 2001 PS2 GS 四遍叠加风化流** (`PS2_GS_MULTIPASS`) | 利用 PS2 GS 极高的 eDRAM 填充率，在同一表面叠加宏观错缝石块、高频砂砾细节、纵向青苔掩码与受光面柔光 | 复刻《ICO》《汪达与巨像》阳光古堡砂岩、迷雾断桥与青苔石雕 |

### 可复用 Shader NodeGroups 库 (`Add -> Group`)
点击工具箱中的 **`生成 5 大节点组库` (`sds.build_texture_nodegroups`)** 按钮，即可在当前 `.blend` 文件中生成 5 个标准化节点组，供任何自定义材质直接连线调用：
1. `SDS_NG_1_Bryce_DTE_3DSolid`：1997 Bryce 三通道海拔/坡度 3D 实体纹理组
2. `SDS_NG_2_PS1_Triplanar_Texel_Sampler`：PS1 三平面正交映射 + 最近邻纹素网格量化采样器（可直接串联在任意 `Image Texture` 节点的 `Vector` 输入端）
3. `SDS_NG_3_PS1_Prebaked_Grime_CLUT`：PS1 预烘焙微颗粒、水渍暗角与 CLUT 色彩量化组
4. `SDS_NG_4_DC_PowerVR2_SphereMap_Alpha`：Dreamcast `GL_SPHERE_MAP` 球面反射与半透明混合组
5. `SDS_NG_5_PS2_GS_MultiPass_Weathering`：PS2 GS 宏观结构 + 18x 微砂砾 + 纵向青苔四遍混合风化组

## 内置 22 个世界预设一览

| 所属类别面板 | 预设 ID | 预设名称与视觉特征 |
| :--- | :--- | :--- |
| **【类别 I】1997 离线 CGI** | `CLASSIC_BRYCE` | **Classic Bryce 97**：DTE 三通道高饱和雪山、赭石横纹岩与宝蓝拉丝镜湖 |
| **【类别 I】1997 离线 CGI** | `INFINITE_OCEAN` | **Granite Domes**：错落高耸的条纹花岗岩穹顶群峰、翠绿山谷与钴蓝远雾 |
| **【类别 I】1997 离线 CGI** | `ALIEN_DREAM` | **Alien Bio-Dome**：异星镀铬圆顶基地、红色方尖碑阵列与黄金绿晶圆台 |
| **【类别 I】1997 离线 CGI** | `RAYTRACED_GEOMETRY` | **POV-Ray CSG Arch**：红黄棋盘格大地、四向圆拱布尔方亭与 8 颗环绕真镜面铬球 |
| **【类别 I】1997 离线 CGI** | `SUNSET_MONOLITH` | **Sunset Monolith**：裂纹地衣荒漠、半透明红宝石方碑、竖立铜环与悬浮天体 |
| **【类别 I】1997 离线 CGI** | `ABSTRACT_LAB` | **Abstract Lab 97**：云海棋盘格与超尺度悬浮金属天体光环 |
| **【类别 II】PS1 &《LSD》** | `LSD_VIOLENCE_TOWERS` | **九龙风水传 (城寨巷)**：暖橙街灯与冷白灯管交织的幽暗港式城寨巷道、10cm 墨绿马赛克磁砖柱、做旧横纹铁卷门、发光招牌与铸铁红消防栓 |
| **【类别 II】PS1 &《LSD》** | `LSD_DREAM_EMULATOR` | **LSD: 明月庄 (楼/吧台)**：四层像素混凝土公寓楼、一楼黑白棋盘吧台、日式障子门与六棱低模树 |
| **【类别 II】PS1 &《LSD》** | `LSD_PSYCHEDELIC_TURTLE` | **LSD: 靶心巨龟**：墨绿黑夜像素云、切比雪夫青框同心圆彩虹靶心方砖山坡与八面体斜坡眼斑巨龟 |
| **【类别 II】PS1 &《LSD》** | `LSD_KANJI_EYE_GIANT` | **LSD: 独眼汉字巨像**：绿蓝波纹像素方砖广场、苔藓矮墙、左上角十字星芒日与紫色发光汉字独眼巨像 |
| **【类别 II】PS1 &《LSD》** | `LSD_KYOTO_KIMONO_NIGHT` | **LSD: 京都夜街和服女**：深蓝夜空、砂石地面、青黑条纹瓦顶木格窗町家木屋与折面无阴影低模和服艺伎 |
| **【类别 II】PS1 &《LSD》** | `LSD_GRAY_MAN_PLAZA` | **LSD: 紫天灰衣帽男**：紫红魔天、八角蓝紫刺日图腾、紫砖广场、蓝紫符文围墙与中央灰衣帽子男剪影 |
| **【类别 II】PS1 &《LSD》** | `LSD_FLESH_TUNNEL` | **LSD: 红雾血肉隧道**：八角暗红血肉走廊、下壁纵向 UV 截断拉伸条纹、尽头 `#FF0000` 纯红距离雾与中央白红玩偶 |
| **【类别 II】PS1 &《LSD》** | `LSD_GRAFFITI_CORRIDOR` | **LSD: 波点涂鸦长廊**：白底彩色 CMYK 波点地板、酸绿/亮黄/艳红拼贴涂鸦长墙与纯黑深雾 |
| **【类别 II】PS1 &《LSD》** | `PS1_AFFINE_DUNGEON` | **PS1 Classic 1996**：`16×16` 显式三角化粗折面峡谷、走廊出口与八面体低模金属晶球 |
| **【类别 II】PS1 &《LSD》** | `IMPOSSIBLE_GEOGRAPHY` | **PS1 Cyber Grid**：`24×24` 全硬边三角阶梯孤峰、像素电光蓝线框海面与棱角方体 |
| **【类别 III】Dreamcast** | `DC_GEIST_WATERFALL` | **DC 瀑布峡谷战机**：半环形青白飞瀑崖壁、3 座青铜水闸高塔、右侧翡翠绿发光岩、球面反射战机与 6 层 PowerVR2 半透明青白尾焰 |
| **【类别 III】Dreamcast** | `DC_SONIC_COAST` | **DC 翡翠海岸碧海**：高饱和透视校正三线性碧海、翠绿海岸群岛与黄金环轨 |
| **【类别 III】Dreamcast** | `DC_REZ_CYBERSPACE` | **DC Rez 赛博矩阵**：电光蓝线框矩阵与多层半透明能量光环 |
| **【类别 IV】PS2 EE & GS** | `PS2_MISTY_RUINS` | **PS2 ICO 古堡拱桥**：暖阳斑驳砂岩石砌双拱高架桥墩、左侧突出悬崖石台、上升石阶、18 根尖刺锻铁护栏、3 层斜射体积圣光片与 GS 帧缓冲柔光 |
| **【类别 IV】PS2 EE & GS** | `PS2_COLOSSUS_VALLEY` | **PS2 旺达禁忌峡谷**：宏大阶梯花岗岩峡谷、远景高耸断桥古塔、`VU1` 顶点风场与浓厚大气散射雾 |
| **【类别 IV】PS2 EE & GS** | `AERO_PARADISE` | **PS2 / Y2K 生态乌托邦**：千禧年高透生态气泡群、碧海环礁与柔和光晕 |

## 安装与快速上手

### 1. 安装插件
1. 下载发布的完整安装包 `late_90s_graphics_lab.zip`（无需解压）。
2. 打开 Blender（支持 **Blender 3.6 LTS、4.0–4.3 及 5.0–5.1+**）。
3. 进入顶部菜单 `Edit -> Preferences -> Add-ons`。
4. 点击右上角 `Install...`（或 Blender 4.2/5.x 中的 `Install from Disk...`），选择 `late_90s_graphics_lab.zip` 并勾选启用 **3D View: Late-90s Graphics Lab**。

### 2. 打开侧边栏工作台
1. 在 3D 视口（`3D Viewport`）中按快捷键 **`N`** 展开右侧边栏。
2. 点击 **`Late-90s Lab`** 标签页，即可看到按四大图形学时代与纹理工具箱分框排列的 6 个折叠面板：
   * `LATE-90s GRAPHICS LAB`（全局场景生成、随机探索与实时更新开关）
   * `【类别 I】1997 离线 CGI · Bryce & POV-Ray`
   * `【类别 II】1994–1998 PS1 实时图形 &《LSD》梦境`
   * `【类别 III】1998–2001 Sega Dreamcast · PowerVR2`
   * `【类别 IV】2000–2005 PS2 实时图形 · EE & GS`
   * `【纹理工具箱】四大图形学纹理合成与改造台`
   * `【全局输出】显示媒介、分辨率与配方管理`

### 3. 为你自己的模型赋予/改造复古材质
1. 在 3D 视口中选中你自己的任意网格模型。
2. 展开 **`【纹理工具箱】四大图形学纹理合成与改造台`**：
   * 选择 **`生成思路`**（如 `II-A. 1997 PS1 写实预烘焙做旧` 或 `IV. 2001 PS2 GS 四遍叠加风化`）；
   * 选择 **`纹理母型`**（如 `城寨马赛克磁砖`、`做旧瓦楞铁卷门`、`古堡风化砂岩` 等）；
   * 调节 **`预烘焙砖缝暗角与水渍`**、**`18x 高频微表面颗粒`** 与 **`CLUT 色表`**；
   * 点击 **`赋予选中物体 (Apply to Selected)`** 即可一键生成材质并自动挂载对应年代的几何精度修改器；若模型已有图片贴图，点击 **`改造现有贴图/材质`** 即可在不破坏原贴图的前提下注入最近邻纹素网格量化管线。

## 项目目录结构

```text
late_90s_graphics_lab/
├── __init__.py            # 插件注册入口、模块热重载与旧场景自动热升级器 (_auto_upgrade_open_scenes)
├── blender_manifest.toml  # Blender 4.2+ / 5.x Extensions 标准清单文件
├── presets.py             # 22 个内置世界预设字典与 JSON 风格配方导入/导出管理
├── properties.py          # 场景级 PropertyGroup 参数定义与实时视口更新回调
├── terrain.py             # 四阶段可组合分形高度场生成器 (16×16 PS1 硬边三角网至 256×256 Bryce 高度场)
├── materials.py           # 四大年代着色器管线、三平面正交 UV 投影、预烘焙做旧与非 PBR 光照引擎
├── texture_workbench.py   # 四大图形学纹理合成工具台、5 大可复用节点组库与模型贴图改造工具
├── dreamspace.py          #《九龙风水传》《LSD》《ICO》与 Dreamcast 瀑布峡谷程序化建筑/角色/灯光生成器
├── sky_atmosphere.py      # 天幕程序化云霞、零漫反射串色背景与年代太阳/天体控制器
├── scene_composer.py      # 场景总装调度器、CSG 布尔几何构图、240 帧循环镜头漫游与渲染器防崩溃配置
├── operators.py           # 场景生成、预设切换、纹理工具赋予、CLUT 轮换与 JSON 配方算子
├── ui.py                  # 3D 视口 N 面板四大类别与纹理工具箱分框 UI 布局
├── README.md              # 项目文档与技术原理解析
└── recipes/               # 22 个内置世界预设对应的独立 JSON 配方文件 (*.json)
```

## 开源许可

本项目采用 **GPL-3.0-or-later** 许可证发布，与 Blender 官方扩展生态完全兼容。
