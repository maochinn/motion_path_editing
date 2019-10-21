import math

import bpy
import bmesh
from mathutils import Vector, Euler, Matrix, Quaternion, geometry

from bpy.props import StringProperty, BoolProperty, FloatProperty, EnumProperty
from bpy.types import Operator

from .importBvh import NodeBVH, MotionPathAnimation

class FootskateCleanup:

    @classmethod
    def AlphaBlend(cls, t):
        return 2 * t * t * t - 3 * t * t + 1
    
    @classmethod
    def SolveIK(cls, jointPositions, jointRotations, target, useConstraint, constraint, Iterations=10, Epsilon=0.0001):
        totalLength = 0

        boneLengths = [0,] * (len(jointPositions) - 1)
        boneDirections = [None,] * (len(jointPositions) - 1)

        for i in range(len(jointPositions) - 1):
            vec = (jointPositions[i] - jointPositions[i + 1])
            boneLengths[i]    = vec.magnitude
            boneDirections[i] = vec.normalized()
            totalLength      += boneLengths[i]

        if ((jointPositions[-1] - target).magnitude > totalLength):
            for i in range(len(jointPositions) - 2, -1, -1):
                vec = (target - jointPositions[i + 1]).normalized()
                jointPositions[i] = jointPositions[i + 1] + vec * boneLengths[i]
        else:
            lastPos = jointPositions[0].copy()
            # iterate backward & forward
            for k in range(Iterations):
                jointPositions[0] = target.copy()
                for i in range(1, len(jointPositions)-1):
                    vec = (jointPositions[i] - jointPositions[i - 1]).normalized()
                    jointPositions[i] = jointPositions[i - 1] + vec * boneLengths[i - 1]

                for i in range(len(jointPositions) - 2, -1, -1):
                    vec = (jointPositions[i] - jointPositions[i + 1]).normalized()
                    jointPositions[i] = jointPositions[i + 1] + vec * boneLengths[i]

                if ((jointPositions[0] - lastPos).magnitude < Epsilon):
                    break

                lastPos = jointPositions[0].copy()

        if useConstraint:
            for i in range(1, len(jointPositions)-1):
                normal = (jointPositions[i + 1] - jointPositions[i - 1]).normalized()

                point = jointPositions[i - 1]

                projectionPole = geometry.intersect_line_plane(constraint, constraint + normal, point, normal)
                projectionBone = geometry.intersect_line_plane(jointPositions[i], jointPositions[i] + normal, point, normal)

                Va = (projectionBone - jointPositions[i - 1])
                Vb = (projectionPole - jointPositions[i - 1])

                dotV = max(-1, min(1, Va.normalized().dot(Vb.normalized())))

                angle = math.acos(dotV)
                cross = Va.cross(Vb)

                if (normal.dot(cross) < 0):
                    angle = -angle

                jointPositions[i] = Quaternion(normal, angle) @ (jointPositions[i] - jointPositions[i - 1]) + jointPositions[i - 1]

        for i in range(1, len(jointPositions)):
            boneDir = (jointPositions[i - 1] - jointPositions[i]).normalized()

            #jointRotations[i] = boneDirections[i - 1].rotation_difference(boneDir) @ jointRotations[i]
            jointRotations[i] = Vector((0,0,-1)).rotation_difference(boneDir)

        return jointPositions, jointRotations

class ApplyFootskateCleanup(Operator):
    bl_idname = "bvh.animation_apply_footskate_cleanup"
    bl_label = "Animation Operation"
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}

    selected_animation = None

    plane_height = 0

    def loadJoints(self, context):
        items = []

        if ApplyFootskateCleanup.selected_animation != None:
            for node in ApplyFootskateCleanup.selected_animation.nodes_bvh.values():
                items.append((node.name, node.name, node.name, node.index))
        
        if len(items) == 0:
            items.append(("None","None","None"))
        
        return items

    left_foot = bpy.props.EnumProperty(name="LeftFootJoint", items = loadJoints)
    right_foot = bpy.props.EnumProperty(name="RightFootJoint", items = loadJoints)

    @classmethod
    def poll(cls, context):
        animation_name = bpy.context.scene.footskate_cleanup_select_collection_name
        path_animation = MotionPathAnimation.GetPathAnimationByName(animation_name)

        if path_animation == None:
            return False

        return True

    def invoke(self, context, event):
        wm = context.window_manager

        animation_name = bpy.context.scene.footskate_cleanup_select_collection_name
        path_animation = MotionPathAnimation.GetPathAnimationByName(animation_name)

        ApplyFootskateCleanup.selected_animation = path_animation

        return wm.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.label(text="Select Foot Joints")

        row = layout.row()
        row.prop(self, "left_foot")
        row = layout.row()
        row.prop(self, "right_foot")

    def execute(self, context):

        def isValidFootNode(node):
            return (node != None and (node.parent != None and (node.parent.parent != None and (node.parent.parent.parent != None))))

        if ApplyFootskateCleanup.selected_animation != None:
            path_animation = ApplyFootskateCleanup.selected_animation

            left_foot_node  = path_animation.findNodeByName(self.left_foot)
            right_foot_node = path_animation.findNodeByName(self.right_foot)

            if not (isValidFootNode(left_foot_node) and isValidFootNode(right_foot_node)):
                self.report({'ERROR'}, 'Illegal Joint Node!!!')
                return {'CANCELLED'}

            self.ReplaceAnimation(context, path_animation, left_foot_node, right_foot_node)

        return {'FINISHED'}

    def ReplaceAnimation(self, context, animation, left, right):
         # set key frame start and end
        animation.context.scene.frame_start = 0
        animation.context.scene.frame_end = animation.frames_bvh - 1

        root = NodeBVH.getRoot(animation.nodes_bvh)

        for frame_idx in range(animation.frames_bvh):
            animation.context.scene.frame_set(frame_idx * animation.interpolation_scaler)

            self.SolveFootNode(animation, left, frame_idx)
            self.SolveFootNode(animation, right, frame_idx)

    def SolveFootNode(self, animation, footNode, frame_idx):
        kneeNode = footNode.parent
        hipNode  = kneeNode.parent

        nodes = (footNode, kneeNode, hipNode)

        jointPoses = []
        jointRots  = []

        for node in nodes:
            ob = animation.skeleton.all_objects[animation.name+"."+node.name+"_head"]
            jointPoses.append(ob.location.copy())
            jointRots.append(ob.rotation_quaternion.copy())

        intersection = geometry.intersect_line_plane(jointPoses[0], jointPoses[0] + Vector((0,0,1)), Vector((0,0,self.plane_height)), Vector((0,0,1)))

        if intersection[2] > jointPoses[0][2]:
            jointPoses, jointRots = FootskateCleanup.SolveIK(jointPoses, jointRots, intersection, True, jointPoses[1].copy(), Iterations=15)
            
            for i in range(len(nodes)):
                # translation
                translation = Matrix.Translation(jointPoses[i])
                # rotation
                rotation = jointRots[i].to_matrix()
                for x in range(3):
                    for y in range(3):
                        translation[x][y] = rotation[x][y]

                nodes[i].model_mat = translation
                nodes[i].world_head = nodes[i].model_mat @ Vector((0.0, 0.0, 0.0))
                nodes[i].world_tail = nodes[i].model_mat @ Vector(nodes[i].local_tail - nodes[i].local_head)

            # update foot node's children
            for child in footNode.children:
                NodeBVH.updateWorldPosition(child, footNode.model_mat, frame_idx)
            
            # recursive set animation keyframe from hip node
            self.SetAnimationFrame(animation, hipNode)

    def SetAnimationFrame(self, animation, node):
        # head
        ob = animation.skeleton.all_objects[animation.name+"."+node.name+"_head"]

        ob.location = (node.world_head.xyz)
        ob.keyframe_insert(data_path="location", index=-1)

        # is leaf
        if len(node.children) == 0:
            ob = animation.skeleton.all_objects[animation.name+"."+node.name+"_tail"]

            ob.location = (node.world_tail.xyz)
            ob.keyframe_insert(data_path="location", index=-1)

        # line of head_to_tail
        ob = animation.skeleton.all_objects[animation.name+"."+node.name]

        ob.location = (node.world_head.xyz)
        ob.keyframe_insert(data_path="location", index=-1)

        ob.rotation_quaternion = (node.model_mat).to_quaternion()
        ob.keyframe_insert(data_path="rotation_quaternion", index=-1)

        for child in node.children:
            self.SetAnimationFrame(animation, child)

def draw(context, layout):
    row = layout.row()
    row.label(text="Inverse Kinematics")

    row = layout.row()
    row.prop_search(
            data=bpy.context.scene,
            property="footskate_cleanup_select_collection_name",
            search_data=bpy.data,
            search_property="collections",
            text="animation")

    row = layout.row()
    row.operator("bvh.animation_apply_footskate_cleanup",text = "Apply To Animation")

def register():
    bpy.utils.register_class(ApplyFootskateCleanup)
    bpy.types.Scene.footskate_cleanup_select_collection_name = bpy.props.StringProperty()

def unregister():
    bpy.utils.unregister_class(ApplyFootskateCleanup)
    del bpy.types.Scene.footskate_cleanup_select_collection_name
