# SPDX-License-Identifier: GPL-3.0-or-later
"""
Silicon Dreams Studio — Late-90s Graphics Lab (v4.0.0)
Unifies four late-20th-century 3D graphics traditions inside Blender (3.6 - 5.x+):
- A. 1997 Bryce 3D / POV-Ray Offline CGI (Whitted Raytracing & Deep Texture Editor)
- B. 1994-1998 PlayStation 1 Realtime Graphics (GTE Vertex Snapping, Affine UV, 15-bit RGB)
- C. 1998《LSD: Dream Emulator》Dreamspace Generator (Spatial Graph, Scale Anomalies, Texture Mismatch)
- D. 2000 PlayStation 2 Emotion Engine / GS & 1997 PC Realtime 3D (Spherical EnvMap & GS Framebuffer Bloom)
"""

bl_info = {
    "name": "Late-90s Graphics Lab",
    "author": "Silicon Dreams Studio",
    "version": (4, 0, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar (N) > Late-90s Lab",
    "description": (
        "Late-90s Graphics Lab: 1997 Bryce 3D, POV-Ray, PS1 GTE/GPU, "
        "LSD: Dream Emulator spatial graph generator, and PS2 GS bloom simulator"
    ),
    "doc_url": "",
    "category": "3D View",
}

import importlib
import bpy
from bpy.props import PointerProperty

from . import (
    presets,
    terrain,
    materials,
    texture_workbench,
    sky_atmosphere,
    dreamspace,
    scene_composer,
    properties,
    operators,
    ui,
)


def _reload_modules():
    for mod in (
        presets,
        terrain,
        materials,
    texture_workbench,
        sky_atmosphere,
        dreamspace,
        scene_composer,
        properties,
        operators,
        ui,
    ):
        try:
            importlib.reload(mod)
        except Exception:
            pass


_reload_modules()


def _get_classes():
    return (
        *properties.CLASSES,
        *operators.CLASSES,
        *ui.CLASSES,
    )




def _auto_upgrade_open_scenes():
    """
    Automatically upgrades `SDS_PS1_GTE_Quantize_GN`, materials, and camera keyframes
    in any already-open `.blend` scene as soon as the add-on is enabled or reloaded!
    """
    try:
        dreamspace.unregister_ps1_frame_handler()
        if not hasattr(bpy, "context") or bpy.context is None:
            return None
        scene = getattr(bpy.context, "scene", None)
        if scene is None or not hasattr(scene, "sds_props"):
            return None
        props = scene.sds_props
        if getattr(props, "ps1_vertex_snap", 0.0) > 0.020:
            props.ps1_vertex_snap = 0.006
        if bpy.data.node_groups.get("SDS_PS1_GTE_Quantize_GN") is not None:
            dreamspace.ensure_ps1_gte_geonodes(props)
        if bpy.data.objects.get("SDS_Terrain") is not None or bpy.data.objects.get("SDS_Camera") is not None:
            texture_workbench.ensure_reusable_texture_node_groups()
            scene_composer.compose_full_scene(bpy.context, props)
            # Rebuild existing dream/PS1 materials in-place so sds_rest_pos texture locking takes effect immediately
            for idx in range(5):
                if bpy.data.materials.get(f"SDS_Mat_DreamFacade_{idx}") is not None:
                    materials.build_dream_facade_material(props, idx)
                if bpy.data.materials.get(f"SDS_Mat_DreamWall_{idx}") is not None:
                    materials.build_dream_wall_material(props, idx)
                if bpy.data.materials.get(f"SDS_Mat_DreamMutated_{idx}") is not None:
                    materials.build_dream_mutated_material(props, idx)
            if bpy.data.materials.get("SDS_Mat_Terrain") is not None:
                materials.build_terrain_material(props)
    except Exception:
        pass
    return None


def register():
    _reload_modules()
    for cls in _get_classes():
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            try:
                bpy.utils.unregister_class(cls)
            except Exception:
                pass
            bpy.utils.register_class(cls)
    dreamspace.ensure_ps1_frame_handler_registered()
    try:
        if hasattr(bpy, "app") and hasattr(bpy.app, "timers"):
            bpy.app.timers.register(_auto_upgrade_open_scenes, first_interval=0.1)
    except Exception:
        pass
    bpy.types.Scene.sds_props = PointerProperty(
        type=properties.SDS_SceneProperties,
        name="Late-90s Graphics Lab Settings",
        description="Parameters for Silicon Dreams Studio / Late-90s Graphics Lab",
    )


def unregister():
    dreamspace.unregister_ps1_frame_handler()
    if hasattr(bpy.types.Scene, "sds_props"):
        try:
            del bpy.types.Scene.sds_props
        except Exception:
            pass
    for cls in reversed(_get_classes()):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass


if __name__ == "__main__":
    register()
