import math

import bpy
import bmesh
from mathutils import Vector, Euler, Matrix, Quaternion, geometry

from bpy.props import StringProperty, BoolProperty, FloatProperty, EnumProperty
from bpy.types import Operator

from .importBvh import NodeBVH, MotionPathAnimation

class ConcatenateMotions(Operator):
    bl_idname = "bvh.animation_apply_concatenate_motions"
    bl_label = "Animation Operation"
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}

    selected_animation0 = None
    selected_animation1 = None

    @classmethod
    def poll(cls, context):
        animation_name0 = bpy.context.scene.concatenate_select_collection_name1
        animation_name1 = bpy.context.scene.concatenate_select_collection_name2

        selected_animation0 = MotionPathAnimation.GetPathAnimationByName(animation_name0)
        selected_animation1 = MotionPathAnimation.GetPathAnimationByName(animation_name1)

        if selected_animation0 == None or selected_animation1 == None:
            return False

        return True

    def execute(self, context):
        animation_name0 = bpy.context.scene.concatenate_select_collection_name1
        animation_name1 = bpy.context.scene.concatenate_select_collection_name2

        path_animation0 = MotionPathAnimation.GetPathAnimationByName(animation_name0)
        path_animation1 = MotionPathAnimation.GetPathAnimationByName(animation_name1)

        if not NodeBVH.compareSkeleton(path_animation0.nodes_bvh, path_animation1.nodes_bvh):
            return {'CANCELLED'}

        # create new bvh animation class
        path_animation = path_animation0.copy()
        # update new animation datas
        self.concatenate(path_animation, path_animation1)
        # rename
        path_animation.name = path_animation0.name + "$" + path_animation1.name
        # update new animation length
        path_animation.frames_bvh = path_animation0.frames_bvh + path_animation1.frames_bvh
        # create skeleton, calculate path and path edit event
        path_animation.init_animation_object()

        # add animation to list
        MotionPathAnimation.AddPathAnimation(path_animation)

        return {'FINISHED'}

    def concatenate(self, a0, a1):

        # append animation data
        for node0 in a0.nodes_bvh.values():
            node1 = a1.nodes_bvh[node0.name]
            for i in range(1, len(node1.anim_data)):
                data = node1.anim_data[i]
                node0.anim_data.append([data[0], data[1], data[2], data[3], data[4], data[5]])
            
        # change root orientation
        concatenate_frame = a0.frames_bvh + 1

        concatenate_offset = [0, 0, 0, 0, 0, 0]

        root = NodeBVH.getRoot(a0.nodes_bvh)

        for i in range(6):
            concatenate_offset[i] = root.anim_data[concatenate_frame-1][i] - root.anim_data[concatenate_frame][i]

        for i in range(concatenate_frame, len(root.anim_data)):
            for j in range(6):
                root.anim_data[i][j] += concatenate_offset[j]

        # smooth
        # for node in a0.nodes_bvh.values():
        #     self.smooth(node.anim_data, concatenate_frame-1, 30)

    def smooth(self, data, frame_concatenate, smooth_window):
        frame_count = len(data)
        for s in range(-smooth_window, smooth_window+1):
            currentFrame = frame_concatenate + s
            if currentFrame > 0 and currentFrame < frame_count:
                data_idx = currentFrame + 1

                for i in (3,4,5):
                    diff = data[frame_concatenate+1][i] - data[frame_concatenate][i]
                    data[data_idx][i] = data[data_idx][i] + diff * self.smooth_y(currentFrame, frame_concatenate, smooth_window)
    
    def smooth_y(self, f, d, s):
        res = 0

        diff = f - d
        diff_norm = (diff + s) / s

        if abs(diff) > s:
            res = 0

        elif diff > 0:
            res = 0.5 * diff_norm * diff_norm

        else:
            res = -0.5 * diff_norm * diff_norm + 2 * diff_norm - 2
        
        return res

def draw(context, layout):
    row = layout.row()
    row.label(text="Motion Concatenate")

    row = layout.row()
    row.prop_search(
            data=bpy.context.scene,
            property="concatenate_select_collection_name1",
            search_data=bpy.data,
            search_property="collections",
            text="animation")

    row = layout.row()
    row.prop_search(
            data=bpy.context.scene,
            property="concatenate_select_collection_name2",
            search_data=bpy.data,
            search_property="collections",
            text="animation")

    row = layout.row()
    row.operator("bvh.animation_apply_concatenate_motions",text = "Apply To Animation")

def register():
    bpy.utils.register_class(ConcatenateMotions)

    bpy.types.Scene.concatenate_select_collection_name1 = bpy.props.StringProperty()
    bpy.types.Scene.concatenate_select_collection_name2 = bpy.props.StringProperty()

def unregister():
    bpy.utils.unregister_class(ConcatenateMotions)

    del bpy.types.Scene.concatenate_select_collection_name1
    del bpy.types.Scene.concatenate_select_collection_name2
