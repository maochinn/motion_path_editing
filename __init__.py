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

from . import cameraFollow

# global
path_animations = []


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
        
        from . import importBvh
        
        path_animation = importBvh.MotionPathAnimation(context, 
        (self.axis[0], self.axis[1], self.axis[2]))
        path_animation.load_bvh(self.filepath)

        global path_animations
        path_animations.append(path_animation)

        return {'FINISHED'}

class MAOGenerateAnimation(Operator):
    bl_idname = "mao_animation.keyframe"
    bl_label = "generate key frame animation by bvh animation"
    bl_description = "OUO/"

    @classmethod
    def poll(cls, context):
        # path_animation is not empty
        if path_animations:
            for animation in path_animations:
                if context.scene.select_collection_name == animation.collection.name:
                    return True
        return False        
            
    def execute(self, context):
        for animation in path_animations:
            if context.scene.select_collection_name == animation.collection.name:
                animation.updateKeyFrame()
                return {'FINISHED'}
        return {'PASS_THROUGH'}

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
        row.operator('mao_animation.keyframe', text = "generate animation")

        cameraFollow.draw(context, layout)

# Only needed if you want to add into a dynamic menu
def menu_func_import(self, context):
    self.layout.operator(MAOImportBVH.bl_idname, text="Motion Path Editing(.bvh)")


def register():
    bpy.utils.register_class(MAOImportBVH)
    bpy.utils.register_class(MAOGenerateAnimation)
    bpy.utils.register_class(MAOGenerateAnimationPanel)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    # !!! regist this is important  !!!
    # create new variable "context.scene.select_animation"
    bpy.types.Scene.select_collection_name = bpy.props.StringProperty()
    bpy.types.Scene.select_object_name = bpy.props.StringProperty()

    cameraFollow.register()
    


def unregister():
    bpy.utils.unregister_class(MAOImportBVH)
    bpy.utils.unregister_class(MAOGenerateAnimation)
    bpy.utils.unregister_class(MAOGenerateAnimationPanel)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

    cameraFollow.unregister()


if __name__ == "__main__":
    register()

    # test call
    bpy.ops.import_test.some_data('INVOKE_DEFAULT')