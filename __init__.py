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

# global
path_animation = None


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
    use_setting = BoolProperty(
            name="Example Boolean",
            description="Example Tooltip",
            default=True,
            )

    type = EnumProperty(
            name="Example Enum",
            description="Choose between two items",
            items=(('OPT_A', "First Option", "Description one"),
                   ('OPT_B', "Second Option", "Description two")),
            default='OPT_A',
            )

    def execute(self, context):
        
        from . import importBvh
        
        global path_animation
        path_animation = importBvh.MotionPathAnimation(context)

        return path_animation.load_bvh(self.filepath)

class MAOGenerateAnimation(Operator):
    bl_idname = "mao_animation.keyframe"
    bl_label = "generate key frame animation by bvh animation"
    bl_description = "OUO/"

    @classmethod
    def poll(cls, context):
        if path_animation is not None:
            if context.collection is path_animation.collection:
                return True
        return False        
            
    def execute(self, context):
        path_animation.updateKeyFrame()
        return {'FINISHED'}

class MAOGenerateAnimationPanel(bpy.types.Panel):
    bl_idname = "MAO_PT_GENERATE_ANIMATION"
    bl_label = "mao generate animation panel"
    bl_category = "Test Addon"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    
    def draw(self, context):
        layout = self.layout
        
        row = layout.row()
        row.operator('mao_animation.keyframe', text = "generate animation")


# Only needed if you want to add into a dynamic menu
def menu_func_import(self, context):
    self.layout.operator(MAOImportBVH.bl_idname, text="Motion Path Editing(.bvh)")


def register():
    bpy.utils.register_class(MAOImportBVH)
    bpy.utils.register_class(MAOGenerateAnimation)
    bpy.utils.register_class(MAOGenerateAnimationPanel)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    


def unregister():
    bpy.utils.unregister_class(MAOImportBVH)
    bpy.utils.unregister_class(MAOGenerateAnimation)
    bpy.utils.unregister_class(MAOGenerateAnimationPanel)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)


if __name__ == "__main__":
    register()

    # test call
    bpy.ops.import_test.some_data('INVOKE_DEFAULT')