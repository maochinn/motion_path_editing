import math

import bpy
import bmesh

from mathutils import Vector, Euler, Matrix, Quaternion

from bpy.props import StringProperty, BoolProperty, FloatProperty
from bpy.types import Operator

class SmoothFollow(Operator):
    bl_idname = "view.smooth_follow"
    bl_label = "View Operation"
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}

    following = False

    @classmethod
    def poll(cls, context):
        objname = bpy.context.scene.select_collection_follow_target_name
        obj = bpy.data.objects.get(objname)
        return obj != None

    def execute(self, context):
        SmoothFollow.following = not SmoothFollow.following

        objname = bpy.context.scene.select_collection_follow_target_name
        obj = bpy.data.objects.get(objname)

        self.target = obj

        self.camera = bpy.context.scene.camera
        # create constraints if not exist
        self.trackTo = self.camera.constraints.get('TRACK_TO')
        if self.trackTo == None:
            self.trackTo = self.camera.constraints.new(type='TRACK_TO')
            self.trackTo.name = 'TRACK_TO'

        self.limitDistance = self.camera.constraints.get('LIMIT_DISTANCE')
        if self.limitDistance == None:
            self.limitDistance = self.camera.constraints.new(type='LIMIT_DISTANCE')
            self.limitDistance.name = 'LIMIT_DISTANCE'

        if SmoothFollow.following:
            self.trackTo.target = self.target
            self.trackTo.track_axis = 'TRACK_NEGATIVE_Z'
            self.trackTo.up_axis = 'UP_Y'
            self.trackTo.mute = False

            self.limitDistance.target = self.target
            self.limitDistance.distance = bpy.context.scene.follow_target_offset
            self.limitDistance.mute = False
        else:
            self.trackTo.mute = True
            self.limitDistance.mute = True

        return {'FINISHED'}

def draw(context, layout):
    row = layout.row()

    row.label(text="Camera Follow")
    row = layout.row()

    row.prop_search(
        data=bpy.context.scene,
        property="select_collection_follow_target_name",
        search_data = bpy.data,
        search_property = "objects",
        text="Target")

    row = layout.row()
    row.operator('view.smooth_follow', text = "Unfollow" if SmoothFollow.following else "Follow")

    row.prop(bpy.context.scene,"follow_target_offset",text="offset")

def register():
    bpy.utils.register_class(SmoothFollow)

    bpy.types.Scene.select_collection_follow_target_name = StringProperty()
    bpy.types.Scene.follow_target_offset = FloatProperty(default = 5, min=0.1)

def unregister():
    bpy.utils.unregister_class(SmoothFollow)

    del bpy.types.Scene.select_collection_follow_target_name
    del bpy.types.Scene.follow_target_offset