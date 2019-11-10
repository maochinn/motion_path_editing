bl_info = {
    "name": "BVH parser & motion path editing",
    "author": "maochinn",
    "version": (1, 1, 0),
    "blender": (2, 81, 6),
    "location": "File > Import",
    "description": "import .bvh file",
    "warning": "",
    "wiki_url": "",
    "support": 'TESTING',
    "category": "Import-Export",
}


import bpy

# ImportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator

from . import importBvh
from . import registationCurve
from . import cameraFollow
from . import footskateCleanup

class MAOImportBVH(Operator, ImportHelper):
    """This appears in the tooltip of the operator and in the generated docs"""
    bl_idname = "mao_import.bvh"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Import BVH Data"
    bl_options = {'REGISTER', 'UNDO'}

    # ImportHelper mixin class uses this
    filename_ext = ".bvh"

    filter_glob = StringProperty(
            default="*.bvh",
            options={'HIDDEN'},
            maxlen=255,  # Max internal buffer length, longer would be clamped.
            )

    # List of operator properties, the attributes will be assigned
    # to the class instance from the operator settings before calling.
    use_setting: BoolProperty(
            name="Example Boolean",
            description="Example Tooltip",
            default=True,
            )

    # blender's axis order is XYZ
    # but usually use ZXY
    axis: EnumProperty(
            name="(Right, Front, Up))",
            description="Choose between two items",
            items=(('XYZ', "XYZ", "R:X, F:Y, U:Z"),
                   ('ZXY', "ZXY", "R:Z, F:X, U:Y")),
            default='ZXY',
            )

    def execute(self, context):
        path_animation = importBvh.MotionPathAnimation.AddPathAnimation(context, 
        (self.axis[0], self.axis[1], self.axis[2]), self.filepath)
        return {'FINISHED'}

class MAOGenerateAnimation(Operator):
    bl_idname = "mao_animation.keyframe"
    bl_label = "generate key frame animation by bvh animation"
    bl_description = "OUO/"

    @classmethod
    def poll(cls, context):
        # path_animation is not empty
        animation_name = context.scene.select_collection_name

        path_animation = importBvh.MotionPathAnimation.GetPathAnimationByName(animation_name)

        if path_animation == None:
            return False

        return True
            
    def execute(self, context):
        animation_name = context.scene.select_collection_name

        path_animation = importBvh.MotionPathAnimation.GetPathAnimationByName(animation_name)

        if path_animation != None:
            scaler_factor = 1 / bpy.context.scene.bvh_animation_time_scaler
            path_animation.setFrameScaler(scaler_factor)
            path_animation.updateKeyFrame()

        return {'FINISHED'}
        #return {'CANCELLED'}

class MAOGenerateAnimationPanel(bpy.types.Panel):
    bl_idname = "MAO_PT_GENERATE_ANIMATION"
    bl_label = "mao generate animation panel"
    bl_category = "Test Addon"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene               

        row = layout.row()
        # select collection will assign to context.scene.select_animation
        # and search from bpy.data.collections
        row.prop_search(
            data=context.scene,
            property="select_collection_name",
            search_data=bpy.data,
            search_property="collections",
            text="animation")
        row = layout.row()
        row.prop_search(
            data=context.scene,
            property="select_object_name",
            search_data=bpy.data,
            search_property="objects",
            text="camera obj")

        row = layout.row()
        row.prop(context.scene,"bvh_animation_time_scaler",text="Time Scale")

        row = layout.row()
        row.operator('mao_animation.keyframe', text = "generate animation")

        row = layout.row()
        row.prop_search(
            data=context.scene,
            property="select_motion_1_name",
            search_data=bpy.data,
            search_property="collections",
            text="animation 1")
        row = layout.row()
        row.prop_search(
            data=context.scene,
            property="select_motion_2_name",
            search_data=bpy.data,
            search_property="collections",
            text="animation 2")
        row = layout.row()
        row.operator('mao_animation.registration_curve', text = "generate registration curve")

        footskateCleanup.draw(context, layout)
        cameraFollow.draw(context, layout)

class MAOGenerateRegistrationCurve(Operator):
    bl_idname = "mao_animation.registration_curve"
    bl_label = "combine two motion animation to generate registration curve"
    bl_description = "OUO/"

    @classmethod
    def poll(cls, context):
        # path_animation is not empty
        motion_1_name = context.scene.select_motion_1_name
        motion_2_name = context.scene.select_motion_2_name

        motion_1 = importBvh.MotionPathAnimation.GetPathAnimationByName(motion_1_name)
        motion_2 = importBvh.MotionPathAnimation.GetPathAnimationByName(motion_2_name)

        if motion_1 is None or motion_2 is None:
            return False

        return True

    def execute(self, context):
        motion_1_name = context.scene.select_motion_1_name
        motion_2_name = context.scene.select_motion_2_name

        motion_1 = importBvh.MotionPathAnimation.GetPathAnimationByName(motion_1_name)
        motion_2 = importBvh.MotionPathAnimation.GetPathAnimationByName(motion_2_name)

        registationCurve.RegistrationCurve.AddRegistrationCurve(context, motion_1, motion_2)

        return {'FINISHED'}


# Only needed if you want to add into a dynamic menu
def menu_func_import(self, context):
    self.layout.operator(MAOImportBVH.bl_idname, text="Motion Path Editing(.bvh)")


def register():
    bpy.utils.register_class(MAOImportBVH)
    bpy.utils.register_class(MAOGenerateRegistrationCurve)
    bpy.utils.register_class(MAOGenerateAnimation)
    bpy.utils.register_class(MAOGenerateAnimationPanel)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


    # !!! regist this is important  !!!
    # create new variable "context.scene.select_animation"
    bpy.types.Scene.select_collection_name = bpy.props.StringProperty()
    bpy.types.Scene.select_object_name = bpy.props.StringProperty()
    bpy.types.Scene.select_motion_1_name = bpy.props.StringProperty()
    bpy.types.Scene.select_motion_2_name = bpy.props.StringProperty()
    bpy.types.Scene.bvh_animation_time_scaler = bpy.props.FloatProperty(default=1,min=0.001,max=10)

    cameraFollow.register()
    footskateCleanup.register()


def unregister():
    bpy.utils.unregister_class(MAOImportBVH)
    bpy.utils.unregister_class(MAOGenerateRegistrationCurve)
    bpy.utils.unregister_class(MAOGenerateAnimation)
    bpy.utils.unregister_class(MAOGenerateAnimationPanel)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

    cameraFollow.unregister()
    footskateCleanup.unregister()

    del bpy.types.Scene.select_collection_name
    del bpy.types.Scene.select_object_name
    del bpy.types.Scene.bvh_animation_time_scaler

if __name__ == "__main__":
    register()