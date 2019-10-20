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
        if SmoothFollow.following:
            return False

        objname = bpy.context.scene.select_collection_follow_target_name
        obj = bpy.data.objects.get(objname)

        return obj != None

    def draw_callback(self, context):
        pass

    def modal(self, context, event):

        if event.type == 'ESC':
            self.exit()
            return {'FINISHED'}
            #return {'RUNNING_MODAL'}

        return {'PASS_THROUGH'}

    def invoke(self, context, event):

        SmoothFollow.following = True
        
        self.areatype = bpy.types.SpaceView3D
        self._handle = self.areatype.draw_handler_add(
                                                self.draw_callback,
                                                (context,),
                                                'WINDOW', 'POST_VIEW'
                                                )

        context.window_manager.modal_handler_add(self)

        objname = bpy.context.scene.select_collection_follow_target_name
        obj = bpy.data.objects.get(objname)

        self.target = obj

        self.camera = bpy.context.scene.camera
        # create constraints if not exist
        self.trackTo = self.camera.constraints.get('TRACK_TO')
        if self.trackTo == None:
            self.trackTo = self.camera.constraints.new(type='TRACK_TO')
            self.trackTo.name = 'TRACK_TO'
        self.trackTo.target = self.target
        self.trackTo.track_axis = 'TRACK_NEGATIVE_Z'
        self.trackTo.up_axis = 'UP_Y'
        self.trackTo.mute = False

        self.limitDistance = self.camera.constraints.get('LIMIT_DISTANCE')
        if self.limitDistance == None:
            self.limitDistance = self.camera.constraints.new(type='LIMIT_DISTANCE')
            self.limitDistance.name = 'LIMIT_DISTANCE'

        self.limitDistance.target = self.target
        self.limitDistance.distance = bpy.context.scene.follow_target_offset
        self.limitDistance.mute = False

        return {'RUNNING_MODAL'}

    def exit(self):
        SmoothFollow.following = False

        self.trackTo.mute = True
        self.limitDistance.mute = True

        self.areatype.draw_handler_remove(self._handle, 'WINDOW') 

def draw(context, layout):
    row = layout.row()

    row.label(text="Camera Follow")

    row.prop_search(
        data=bpy.context.scene,
        property="select_collection_follow_target_name",
        search_data = bpy.data,
        search_property = "objects",
        text="Target")

    row = layout.row()
    row.operator('view.smooth_follow', text = "Follow Target")

    row.prop(bpy.context.scene,"follow_target_offset",text="offset")

def register():
    bpy.utils.register_class(SmoothFollow)

    bpy.types.Scene.select_collection_follow_target_name = StringProperty()
    bpy.types.Scene.follow_target_offset = FloatProperty(default = 5, min=0.1)

def unregister():
    bpy.utils.unregister_class(SmoothFollow)

    del bpy.types.Scene.select_collection_follow_target_name
    del bpy.types.Scene.follow_target_offset