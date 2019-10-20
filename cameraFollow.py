import math

import bpy
import bmesh

from mathutils import Vector, Euler, Matrix, Quaternion

from bpy.props import StringProperty, BoolProperty, FloatProperty
from bpy.types import Operator

from .importBvh import MotionPathAnimation

class SmoothFollow(Operator):
    bl_idname = "view.smooth_follow"
    bl_label = "View Operation"
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}

    following = False

    @classmethod
    def poll(cls, context):
        animation_name = bpy.context.scene.select_follow_animation
        node_name = bpy.context.scene.select_follow_animation_node

        return animation_name != None and node_name != None

    def execute(self, context):
        animation_name = bpy.context.scene.select_follow_animation
        node_name = bpy.context.scene.select_follow_animation_node

        animation = MotionPathAnimation.GetPathAnimationByName(animation_name)
        if animation == None:
            return {'FINISHED'}
        
        node = animation.findNodeByName(node_name)
        if node == None:
            return {'FINISHED'}

        SmoothFollow.following = not SmoothFollow.following
        obj = animation.skeleton.all_objects[animation.name+"."+node.name+"_head"]

        self.target = obj

        self.camera = bpy.context.scene.camera

        self.camera.data.clip_end = 2000
        
        # create constraints if not exist
        self.copyLocation = self.camera.constraints.get('COPY_LOCATION')
        if self.copyLocation == None:
            self.copyLocation = self.camera.constraints.new(type='COPY_LOCATION')
            self.copyLocation.name = 'COPY_LOCATION'

        self.trackTo = self.camera.constraints.get('TRACK_TO')
        if self.trackTo == None:
            self.trackTo = self.camera.constraints.new(type='TRACK_TO')
            self.trackTo.name = 'TRACK_TO'

        self.limitDistance = self.camera.constraints.get('LIMIT_DISTANCE')
        if self.limitDistance == None:
            self.limitDistance = self.camera.constraints.new(type='LIMIT_DISTANCE')
            self.limitDistance.name = 'LIMIT_DISTANCE'

        if SmoothFollow.following:
            self.camera.location = animation.animation_center

            self.copyLocation.target = self.target
            self.copyLocation.use_x = False
            self.copyLocation.use_y = False
            self.copyLocation.use_z = True
            self.copyLocation.invert_z = False
            self.copyLocation.use_offset = False
            self.copyLocation.mute = False

            self.trackTo.target = self.target
            self.trackTo.track_axis = 'TRACK_NEGATIVE_Z'
            self.trackTo.up_axis = 'UP_Y'
            self.trackTo.mute = False

            self.limitDistance.target = self.target
            self.limitDistance.distance = bpy.context.scene.follow_target_offset
            self.limitDistance.mute = False
        else:
            self.copyLocation.mute = True
            self.trackTo.mute = True
            self.limitDistance.mute = True

        return {'FINISHED'}

def draw(context, layout):
    row = layout.row()
    row.label(text="Camera Follow")

    row = layout.row()
    row.prop(bpy.context.scene,"select_follow_animation")

    row = layout.row()
    row.prop(bpy.context.scene,"select_follow_animation_node")

    row = layout.row()
    row.operator('view.smooth_follow', text = "Unfollow" if SmoothFollow.following else "Follow")

    row.prop(bpy.context.scene,"follow_target_offset",text="offset")

def loadAnimationPathes(self, context):
    items = []
    animations = MotionPathAnimation.GetPathAnimations()
    for animation in animations:
        items.append((animation.collection_name, animation.collection_name, animation.collection_name))

    if len(items) == 0:
        items.append(("None","None","None"))

    return items

def loadJoints(self, context):
    items = []
    animation_name = bpy.context.scene.select_follow_animation
    animation = MotionPathAnimation.GetPathAnimationByName(animation_name)

    if animation != None:
        for node in animation.nodes_bvh.values():
            items.append((node.name, node.name, node.name, node.index))
    
    if len(items) == 0:
        items.append(("None","None","None"))
            
    return items


def register():
    bpy.utils.register_class(SmoothFollow)

    bpy.types.Scene.select_follow_animation = bpy.props.EnumProperty(items = loadAnimationPathes)
    bpy.types.Scene.select_follow_animation_node = bpy.props.EnumProperty(items = loadJoints)
    bpy.types.Scene.follow_target_offset = FloatProperty(default = 5, min=0.1)

def unregister():
    bpy.utils.unregister_class(SmoothFollow)

    del bpy.types.Scene.select_follow_animation
    del bpy.types.Scene.select_follow_animation_node
    del bpy.types.Scene.follow_target_offset