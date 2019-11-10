"""
modify from import_bvh.py
"""

import bpy
import math
import os
from mathutils import Vector, Euler, Matrix

from .createBlenderThing import createCollection, createCamera, createCube, createLine, createPyramid, createPolyCurve

# axis and index relationship
axis_idx = {
    0 : 'X',
    1 : 'Y',
    2 : 'Z',
    'X' : 0,
    'Y' : 1,
    'Z' : 2,
}

class NodeBVH:
    __slots__ = (
        # Bvh joint name.
        'name',
        # BVH_Node type or None for no parent. if it is root parent will be None
        'parent',
        # A list of children of this type..
        'children',
        # Worldspace rest location for the head of this node.
        'world_head',
        # Localspace rest location for the head of this node.
        'local_head',
        # Worldspace rest location for the tail of this node.
        'world_tail',
        # Localspace rest location for the tail of this node.
        'local_tail',
        # A list one tuple's one for each frame: (locx, locy, locz, rotx, roty, rotz),
        # euler rotation ALWAYS stored xyz order, even when native used.
        'anim_data',
        # Index from the file, not strictly needed but nice to maintain order.
        'index',
        # e.g anim_data[i] order is (Xposition Yposition Zposition Zrotation Xrotation Yrotation)
        # position_idx = {'X':0, 'Y':1, 'Z':2}
        # rotation_idx = ('X':5, 'Y':3, 'Z':4}
        'position_idx',
        'rotation_idx',
        # model_matix
        'model_mat',
    )

    def __init__(self, name, local_head, world_head,
        parent, position_idx, rotation_idx ,index):
        self.name = name
        self.local_head = local_head
        self.world_head = world_head
        self.local_tail = None
        self.world_tail = None
        self.parent = parent
        self.position_idx = position_idx
        self.rotation_idx = rotation_idx
        self.index = index

        # convenience functions
        # self.has_loc = channels[0] != -1 or channels[1] != -1 or channels[2] != -1
        # self.has_rot = channels[3] != -1 or channels[4] != -1 or channels[5] != -1

        self.children = []

        # List of 6 length tuples: (lx, ly, lz, rx, ry, rz)
        # even if the channels aren't used they will just be zero.
        self.anim_data = [(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)]
    
    def copy(self):
        node = NodeBVH(self.name, self.local_head.copy(), self.world_head.copy(), 
                        None, self.position_idx, self.rotation_idx, self.index)
        
        node.local_tail = self.local_tail.copy()
        node.world_tail = self.world_tail.copy()

        node.anim_data = []
        for data in self.anim_data:
            node.anim_data.append([data[0], data[1], data[2], data[3], data[4], data[5]])

        return node

    def hasLocation(self):
        return len(self.position_idx) != 0
    
    def hasRotation(self):
        return len(self.rotation_idx) != 0

    def getAnimData(self, frame_idx):
        idx = 0
        if frame_idx + 1 < len(self.anim_data):
            idx = frame_idx + 1
        return self.anim_data[idx]

    @classmethod
    def getRotation(cls, node, frame_idx):
        node_data = node.getAnimData(frame_idx)

        rotation_X = Matrix.Rotation(math.radians(node_data[3]), 4, 'X')
        rotation_Y = Matrix.Rotation(math.radians(node_data[4]), 4, 'Y')
        rotation_Z = Matrix.Rotation(math.radians(node_data[5]), 4, 'Z')


        rotation = Matrix.Identity(4)
        # start = min(node.rotation_idx, key=node.rotation_idx.get)
        start = min(node.rotation_idx.values())
        for i in range(start, start+3):
            if node.rotation_idx['X'] == i:
                rotation = rotation @ rotation_X
            elif node.rotation_idx['Y'] == i:
                rotation = rotation @ rotation_Y
            elif node.rotation_idx['Z'] == i:
                rotation = rotation @ rotation_Z

        return rotation
        
    # return:
    # mat:  Matrix, is local to world matrix
    # frame_idx: int, index of animation frame
    # parent_matrix: Matrix, matrix of parent
    @classmethod
    def updateWorldPosition(cls, node, parent_matrix, frame_idx):
        # compute model matrix
        # default idx is zero, self.anim_data[0] = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        node_data = node.getAnimData(frame_idx)

        offset = Matrix.Translation(node.local_head)
        translation = Matrix.Translation((node_data[0:3]))

        rotation = NodeBVH.getRotation(node, frame_idx)
        
        mat = offset @ translation @ rotation

        node.model_mat = parent_matrix @ mat

        node.world_head = node.model_mat @ Vector((0.0, 0.0, 0.0))
        node.world_tail = node.model_mat @ Vector(node.local_tail - node.local_head)
       

        for child in node.children:
            cls.updateWorldPosition(child, node.model_mat, frame_idx)
          
        return None



    # update world_head and world_tail by anim_data with anim_idx
    @classmethod
    def updateNodesWorldPosition(cls, nodes_bvh, frame_idx, model_matrix = Matrix.Identity(4)):
        # search root
        root = NodeBVH.getRoot(nodes_bvh)

        cls.updateWorldPosition(root, model_matrix, frame_idx)

    @staticmethod
    def getRoot(nodes_bvh):
        # find first root
        for node in nodes_bvh.values():
            if node.parent is None:
                return node
        return None

    @staticmethod
    def compareSkeleton(nodes_bvh0, nodes_bvh1):
        def compareNodeEqual(n0, n1):
            for c0 in n0.children:
                for c1 in n1.children:
                    if c0.name == c1.name:
                        if not compareNodeEqual(c0, c1):
                            return False
                        break
            return True

        r0 = NodeBVH.getRoot(nodes_bvh0)
        r1 = NodeBVH.getRoot(nodes_bvh1)

        return compareNodeEqual(r0, r1)
        
                    



# data structure in outliner of blender
# name.bvh              (bpy.types.collection)
# +---camera
# +---skeleton          (bpy.types.collection)
# |   +---root          (bpy.types.object)
# |       +---mesh      (bpy.types.mesh)
# |   +---other joint...
# +---path
#     +---init_path
#     |   +---curve     (bpy.types.curve)(type: 'POLY')
#     +---init_motion
#     |   +---curve     (bpy.types.curve)(type: 'POLY')
#     +---new_path
#     |   +---curve     (bpy.types.curve)(type: 'POLY')
#     +---new motion
#     |   +---curve     (bpy.types.curve)(type: 'POLY')
#     +---control_points(bpy.types.collection)
#         +---C_0
#         +---C_1
#         +---and so on...

# use bvh animation to implement Motion Path Editing
# self.collection:  bpy.types.collection, is this animation group
# self.skeleton:    bpy.types.collection
# self.path:        bpy.types.collection

# self.context
# self.nodes_bvh
# self.frames_bvh
# self.frame_time_bvh
# self.file_path: str, bvh file path
# self.name: str

# self.init_motion:     object(curve), curve of initial motion
# self.init_path:       object(curve), use least square method fit initial motion as initial path of cubic b-spline
# self.new_path:            object(curve), user can edit path_c_points to adjust this path
# self.new_motion

# self.init_to_new_matrixs: list[Matrix]


# context: bpy.context
# axis: dict, blender default:{(blender_axis:data_axis))}
class MotionPathAnimation:
    path_animations = []

    @classmethod
    def AddPathAnimationFromFile(cls, context, axis, filepath):
        if cls.path_animations == None:
            cls.path_animations = []

        path_animation = MotionPathAnimation(context, axis)

        if path_animation != None:
            path_animation.load_bvh(filepath)

            cls.path_animations.append(path_animation)
        
        return path_animation

    @classmethod
    def AddPathAnimation(cls, path_animation):
        if cls.path_animations == None:
            cls.path_animations = []

        cls.path_animations.append(path_animation)
        
        return path_animation

    @classmethod
    def GetPathAnimations(cls):
        return cls.path_animations

    @classmethod
    def GetPathAnimationByName(cls, name):
        if cls.path_animations != None:
            for animation in cls.path_animations:
                if animation.collection_name == name:
                    return animation
        return None

    @classmethod
    def RemovePathAnimationByName(cls, name):
        if cls.path_animations != None:
            for animation in cls.path_animations:
                if animation.collection_name == name:
                    cls.path_animations.remove(animation)
                    return True
        
        return False
    
    @classmethod
    def ClearPathAnimation(cls):
        cls.path_animations.clear()

    def findNodeByName(self, nodeName):
        if self.nodes_bvh:
            for node in self.nodes_bvh.values():
                if node.name == nodeName:
                    return node
        
        return None

    def setFrameScaler(self, scaler_factor):
        self.interpolation_scaler = scaler_factor

    def __init__(self, context, axis=('X', 'Y', 'Z')):
        self.context = context
        self.init_to_new_matrixs = None

        self.axis = axis
        self.axis_b2d = {'X':axis[0], 'Y':axis[1], 'Z':axis[2]}
        self.axis_d2b = {axis[0]:'X', axis[1]:'Y', axis[2]:'Z'}

        # parameter
        self.t = []
        # re-parameter
        self.re_t = []

        self.interpolation_scaler = 1

        self.animation_center = Vector()

        self.collection = None

        self.nodes_bvh = None
        self.frames_bvh = None
        self.frame_time_bvh = None

        self.skeleton_data = None

    def copy(self):
        path_animation = MotionPathAnimation(self.context, self.axis)

        path_animation.frames_bvh     = self.frames_bvh    
        path_animation.frame_time_bvh = self.frame_time_bvh

        path_animation.skeleton_data = self.skeleton_data

        # copy nodes
        path_animation.nodes_bvh = {}
        for node in self.nodes_bvh.values():
            path_animation.nodes_bvh[node.name] = node.copy()

        # remap nodes' child & parent node
        for node in self.nodes_bvh.values():
            copyNode = path_animation.nodes_bvh[node.name]

            copyNode.children = []
            for c in node.children:
                copyNode.children.append(path_animation.nodes_bvh[c.name])

            copyNode.parent = None
            if node.parent != None:
                copyNode.parent = path_animation.nodes_bvh[node.parent.name]

        return path_animation

    # return:
    # nodes_bvh: dict[name:NodeBVH]
    # frames: int, number of frames
    # frame_time: float, time per frame(sec/frame)
    # parameter:
    # context: bpy.context
    # file_path: str, path of bvh
    def load_bvh(self, file_path):
        self.file_path = file_path
        self.nodes_bvh, self.frames_bvh, self.frame_time_bvh = self.readNodeBVH(self.file_path)

        base = os.path.basename(file_path)
        self.name = os.path.splitext(base)[0]

        if self.frame_time_bvh is None:
            # default is 1 sec
            frame_time_bvh = 1

        if self.frames_bvh is None:
            report(
                {'WARNING'},
                "The BVH file does not contain frame duration in its MOTION "
                "section, assuming the BVH and Blender scene have the same "
                "frame rate"
            )
        else:
            self.readKeyFrameBVH(self.file_path)

            self.init_animation_object()
    
    # call once to create skeleton and path edit event
    def init_animation_object(self):
        if self.collection != None:
            return
        # create collection(or group) to collect object
        self.collection = createCollection(self.context.scene.collection, self.name)
        self.collection_name = self.collection.name

        self.createSkeleton()

        self.createPath()
        root = NodeBVH.getRoot(self.nodes_bvh)
        self.camera = createCamera(self.collection, self.name+".camera", root.world_head)
        # create initial key frame animation
        self.createKeyFrame()

        # register handler to trigger event
        from bpy.app.handlers import persistent

        @persistent
        def change_cotrol_point_handler(scene):
            for ob in self.context.selected_objects:
                # is control point
                # if ob.name in {point.name for point in self.path_c_points_ob}:
                if ob.users_collection[0] is self.control_points:
                    # update bspline
                    self.updateNewPathAndMotionCurve()
                    break
        
        # clear handler, if only one animation you can enable this!
        # bpy.app.handlers.depsgraph_update_pre.clear()

        bpy.app.handlers.depsgraph_update_pre.append(change_cotrol_point_handler)
                    
        return {'FINISHED'}

    
    # read all node of bvh
    # return:
    # nodes_bvh: dict[name:NodeBVH]
    # frames:       int, number of frames
    # frame_time:   float, time per frame(sec/frame) 
    # parameter:
    # file_path:    str, path of file
    def readNodeBVH(self, file_path):
        file = open(file_path, 'rU')

        file_lines = file.readlines()

        file.close()

        # convert to 2D list
        file_lines = [ll for ll in [l.split() for l in file_lines] if ll]
        
        # for line in file_lines:
        #     print(line)
        
         # Create hierarchy as empties
        if file_lines[0][0].lower() == 'hierarchy':
            # print 'Importing the BVH Hierarchy for:', file_path
            pass
        else:
            raise Exception("This is not a BVH file")



        nodes_bvh = {None:None}
        nodes_stack = [None]
        frames = None
        frame_time = None

        line_idx = 0
        while line_idx < len(file_lines):
            #root or joint
            if file_lines[line_idx][0].lower() in {'root', 'joint'}:
                

                name = file_lines[line_idx][1]
                local_offset = Vector()
                world_offset = Vector()
                # position_idx = {'x': -1, 'y': -1, 'z': -1}
                position_idx = {}
                rotation_idx = {}

                
                # offset
                line_idx += 2
                
                local_offset = Vector((
                    float(file_lines[line_idx][axis_idx[self.axis_b2d['X']]+1]),
                    float(file_lines[line_idx][axis_idx[self.axis_b2d['Y']]+1]),
                    float(file_lines[line_idx][axis_idx[self.axis_b2d['Z']]+1]),
                ))
                


                # channels
                line_idx += 1
                
                channelIndex = 0
                for channel in file_lines[line_idx][2:]:
                    channel = channel.lower()

                    if channel == 'xposition':
                        position_idx[self.axis_d2b['X']] = channelIndex
                    elif channel == 'yposition':
                        position_idx[self.axis_d2b['Y']] = channelIndex
                    elif channel == 'zposition':
                        position_idx[self.axis_d2b['Z']] = channelIndex

                    elif channel == 'xrotation':
                        rotation_idx[self.axis_d2b['X']] = channelIndex
                    elif channel == 'yrotation':
                        rotation_idx[self.axis_d2b['Y']] = channelIndex
                    elif channel == 'zrotation':
                        rotation_idx[self.axis_d2b['Z']] = channelIndex

                    channelIndex += 1
                    
                parent = nodes_stack[-1]
                 # Apply the parents offset accumulatively
                if parent is None:   # is root
                    world_offset = Vector(local_offset)
                else:
                    world_offset = parent.world_head + local_offset

                nodes_bvh[name] = NodeBVH(
                    name,
                    local_offset,
                    world_offset,
                    parent,
                    position_idx,
                    rotation_idx,
                    len(nodes_bvh) - 1,
                )

                nodes_stack.append(nodes_bvh[name])
                        
            elif file_lines[line_idx][0].lower() == 'end' and file_lines[line_idx][1].lower() == 'site' :
                #offset
                line_idx += 2
                offset = Vector((
                    float(file_lines[line_idx][axis_idx[self.axis_b2d['X']]+1]),
                    float(file_lines[line_idx][axis_idx[self.axis_b2d['Y']]+1]),
                    float(file_lines[line_idx][axis_idx[self.axis_b2d['Z']]+1]),
                ))
                nodes_stack[-1].local_tail = nodes_stack[-1].local_head + offset
                nodes_stack[-1].world_tail = nodes_stack[-1].world_head + offset

                # Just so we can remove the parents in a uniform way,
                # the end has kids so this is a placeholder.
                nodes_stack.append(None)
                
            elif file_lines[line_idx][0] == '}':
                nodes_stack.pop()

            elif file_lines[line_idx][0].lower() in {"motion"}:
                # Frames:
                line_idx += 1
                frames = int(file_lines[line_idx][1])
                # Frame Time:
                line_idx += 1
                frame_time = float(file_lines[line_idx][2])

            line_idx += 1


        # remove None element
        nodes_bvh.pop(None)

        # assign child
        for node in nodes_bvh.values():
            node_parent = node.parent
            if node_parent:
                node_parent.children.append(node)

        # set tail
        for node in nodes_bvh.values():
            # have no child
            if(len(node.children) == 0):
                pass
            elif(len(node.children) == 1):
                node.world_tail = Vector(node.children[0].world_head)
                node.local_tail = node.local_head + node.children[0].local_head
            else:
                # compute mean of all children's head
                world_mean = Vector((0.0, 0.0, 0.0))
                local_mean = Vector((0.0, 0.0, 0.0))

                for child in node.children:
                    world_mean += child.world_head
                    local_mean += child.local_head

                world_mean *= (1.0 / len(node.children))
                local_mean *= (1.0 / len(node.children))

                node.world_tail = world_mean
                node.local_tail = node.local_head + local_mean


        return nodes_bvh, frames, frame_time
    
    # read key frame animation info to nodes_bvh
    # parameter:
    # file_path:    str, path of file
    def readKeyFrameBVH(self, file_path):
        file = open(file_path, 'rU')
        file_lines = file.readlines()
        file.close()

        # create list ane sort it by index
        nodes_list = list(self.nodes_bvh.values())
        nodes_list.sort(key=lambda node: node.index)

        # total parameter in a line
        parameter_amount = 0
        for node in nodes_list:
            parameter_amount += len(node.position_idx)
            parameter_amount += len(node.rotation_idx)

        # convert to 2D list
        file_lines = [ll for ll in [l.split() for l in file_lines] if ll]

        for line in file_lines:
            # read paremeter to node
            if len(line) == parameter_amount:
                line_idx = 0
                for node in nodes_list:
                    #default (lx, ly, lz, rx, ry, rz)
                    data = [0, 0, 0, 0, 0, 0]
                    if node.hasLocation():
                        for i in range(len(node.position_idx)):
                            # 0, 1, 2 -> lx, ly ,lz
                            axis = axis_idx[i]
                            idx = node.position_idx[axis] + line_idx
                            data[i] = float(line[idx])
                        

                    if node.hasRotation():
                        for i in range(len(node.rotation_idx)):
                            # 3, 4, 5 -> rx, ry ,rz
                            axis = axis_idx[i]
                            idx = node.rotation_idx[axis] + line_idx
                            data[i+3] = float(line[idx])

                            
                    # offset line_idx
                    line_idx += len(node.position_idx)
                    line_idx += len(node.rotation_idx)
                    
                    node.anim_data.append(list(data))


    #
    def createSkeleton(self):
        if self.skeleton_data == None:
            self.skeleton_data = {}

            for node in self.nodes_bvh.values():
                self.skeleton_data[node.name] = (node.world_head.copy(), node.world_tail.copy())

        self.skeleton = createCollection(self.collection, self.name+".skeleton")
        
        # create cube to represent node
        for nodeName, head_tail_data in self.skeleton_data.items():
            createCube(self.skeleton, self.name+"."+nodeName+"_head", head_tail_data[0].xyz)
            # is leaf
            if len(self.nodes_bvh[nodeName].children) == 0:
                    createCube(self.skeleton, self.name+"."+nodeName+"_tail", head_tail_data[1].xyz)

        # create mesh of line to represent skeleton
        for nodeName, head_tail_data in self.skeleton_data.items():
            #createLine(self.skeleton, self.name+"."+node.name, node.world_head.xyz, node.world_tail.xyz)
            createPyramid(self.skeleton, self.name+"."+nodeName, head_tail_data[0].xyz, head_tail_data[1].xyz)

        return
    #
    def updateKeyFrame(self):
        self.deleteKeyFrame()
        self.createKeyFrame()
    #
    def createKeyFrame(self):
        self.animation_center = Vector()

        # set key frame start and end
        self.context.scene.frame_start = 0
        self.context.scene.frame_end = (self.frames_bvh - 1) * self.interpolation_scaler

        root = NodeBVH.getRoot(self.nodes_bvh)

        new_curve   = self.new_path.data.splines[0].points.values()
        for frame_idx in range(self.frames_bvh):
            NodeBVH.updateNodesWorldPosition(self.nodes_bvh, frame_idx, self.init_to_new_matrixs[frame_idx])

            self.context.scene.frame_set(frame_idx * self.interpolation_scaler)

            for node in self.nodes_bvh.values():
                # head
                ob = self.skeleton.all_objects[self.name+"."+node.name+"_head"]

                ob.location = (node.world_head.xyz)
                ob.keyframe_insert(data_path="location", index=-1)

                # is leaf
                if len(node.children) == 0:
                    ob = self.skeleton.all_objects[self.name+"."+node.name+"_tail"]

                    ob.location = (node.world_tail.xyz)
                    ob.keyframe_insert(data_path="location", index=-1)

                # line of head_to_tail
                ob = self.skeleton.all_objects[self.name+"."+node.name]
                me = ob.data

                ob.location = (node.world_head.xyz)
                ob.keyframe_insert(data_path="location", index=-1)

                ob.rotation_mode = 'QUATERNION'
                ob.rotation_quaternion = (node.model_mat).to_quaternion()
                ob.keyframe_insert(data_path="rotation_quaternion", index=-1)

                # is root
                if bpy.context.scene.select_object_name == "":
                    bpy.context.scene.select_object_name = root.name

            if frame_idx > 0:
                front = new_curve[frame_idx].co.xyz - new_curve[frame_idx-1].co.xyz
            else:
                front = new_curve[frame_idx+1].co.xyz - new_curve[frame_idx].co.xyz

            self.animation_center += root.world_head.xyz
            # default camera front direct is (0, 0, -1)
            # we default is (1, 0, 0), so rotate 90 degree by x-axis
            rotation = computeOrientation(front, Vector([0, 0, 1])) @ Matrix.Rotation(math.radians(90.0), 4, 'X')

            offset = front.normalized() * 2.0
            self.camera.location = (root.world_head.xyz + offset)
            self.camera.keyframe_insert(data_path="location", index=-1)

            self.camera.rotation_mode = 'QUATERNION'
            self.camera.rotation_quaternion = (rotation.to_quaternion())
            self.camera.keyframe_insert(data_path="rotation_quaternion", index=-1)

        if self.frames_bvh > 0:
            self.animation_center /= self.frames_bvh

    #
    def deleteKeyFrame(self):
        self.has_animation = False

        for frame_idx in range(self.frames_bvh):
            for node in self.nodes_bvh.values():
                ob = self.skeleton.all_objects[self.name+"."+node.name+"_head"]
                ob.keyframe_delete(data_path="location", index=-1)
                if len(node.children) == 0:
                    ob = self.skeleton.all_objects[self.name+"."+node.name+"_tail"]
                    ob.keyframe_delete(data_path="location", index=-1)

                ob = self.skeleton.all_objects[self.name+"."+node.name]
                ob.keyframe_delete(data_path="location", index=-1)
                ob.keyframe_delete(data_path="rotation_quaternion", index=-1)


    #
    def createPath(self):
        self.path = createCollection(self.collection, self.name+".path")

        self.init_motion                = self.createInitialMotionCurve()
        self.init_path, self.new_path   = self.createPathCurve()
        self.new_motion                 = self.createNewMotionCurve()

    #
    def createInitialMotionCurve(self):
        curve = []
        
        # use root to track curve
        root = None
        for node in self.nodes_bvh.values():
            if node.parent is None:
                root = node
                break

        for frame_idx in range(self.frames_bvh):
            NodeBVH.updateNodesWorldPosition(self.nodes_bvh, frame_idx)
            curve.append((root.world_head))

        return createPolyCurve(self.context, self.path, "initial_motion", curve)
    # 
    def createPathCurve(self):

        self.control_points = createCollection(self.path, self.name+".control_points")

        c_points, self.t = solveCubicBspline(self.init_motion.data.splines[0].points.values())
        for i in range(len(c_points)):
            createCube(self.control_points, "c_"+str(i), c_points[i], 10.0)

        return (
        createCubicBspline(self.context, self.path, c_points, "init_path", self.t),
        createCubicBspline(self.context, self.path, c_points, "new_path", self.t))
    #
    def createNewMotionCurve(self):
        # use root to track curve
        root = NodeBVH.getRoot(self.nodes_bvh)
        
        curve = []

        self.init_to_new_matrixs = []
        init_curve  = self.init_path.data.splines[0].points.values()
        new_curve   = self.new_path.data.splines[0].points.values()
        for i in range(self.frames_bvh):
            p0  = init_curve[i].co
            p   = new_curve[i].co

            P0 = Matrix.Translation(p0)
            P = Matrix.Translation(p)

            R0 = Matrix.Identity(4)
            R = Matrix.Identity(4)
            if (i == 0):
                f0 = init_curve[i+1].co - init_curve[i].co
                f = new_curve[i+1].co - new_curve[i].co
            else:
                f0 = init_curve[i].co - init_curve[i-1].co
                f = new_curve[i].co - new_curve[i-1].co
                
            if f0.length > 0.001:
                R0 = computeOrientation(f0, Vector([0, 0, 1]))
            if f.length > 0.001:
                R = computeOrientation(f, Vector([0, 0, 1]))
            
                

            matrix = P @ R @ R0.inverted() @ P0.inverted()

            self.init_to_new_matrixs.append(matrix)
            
            NodeBVH.updateNodesWorldPosition(self.nodes_bvh, i, matrix)
            curve.append((root.world_head))

        return createPolyCurve(self.context, self.path, "new_motion", curve)

    #
    def createNewReparameterPathCurve(self, path_name):
        c_points = []
        for c_point_ob in self.control_points.all_objects.values():
            c_points.append(c_point_ob.location.xyz)

        Q = []
        for point in self.new_motion.data.splines[0].points.values():
            Q.append(point.co.xyz)
        self.re_t = computeChordLengthParameter(Q)

        return createCubicBspline(self.context, self.path, c_points, path_name, self.re_t)

    #
    def updateNewPathAndMotionCurve(self):

        path_name = self.new_path.name
        motion_name = self.new_motion.name

        # selected = []
        # for ob in self.context.selected_objects:
        #     if not ob.name in {path_name, motion_name}:
        #         selected.append(ob)

        # # delete "path" and create new one
        # for ob in self.context.scene.objects:
        #     if ob.name in {path_name, motion_name}:
        #         ob.select_set(True)
        #     else:
        #         ob.select_set(False)

        # bpy.ops.object.delete()
        
        # for ob in selected:
        #     ob.select_set(True)

        bpy.data.objects.remove(self.new_path)
        bpy.data.objects.remove(self.new_motion)

        c_points = []
        for c_point_ob in self.control_points.all_objects.values():
            c_points.append(c_point_ob.location.xyz)

        self.new_path = createCubicBspline(self.context, self.path, c_points, path_name, self.t)
        self.new_motion = self.createNewMotionCurve()

        # reparameter
        bpy.data.objects.remove(self.new_path)
        self.new_path = self.createNewReparameterPathCurve(path_name)
        bpy.data.objects.remove(self.new_motion)
        self.new_motion = self.createNewMotionCurve()
    

def cubicBspline(t, c_points):
    # Monomial Bases
    M = Vector()
    # Geometric Matrix
    G = Matrix((
        [1, 4, 1, 0],
        [-3, 0, 3, 0],
        [3, -6, 3, 0],
        [-1, 3, -3, 1],))
    G *= 0.16667
    # Control point
    p = []
    for point in c_points:
        p.append(point)
    P = Vector()

    b_point = Vector([0, 0, 0])

    M = Vector([1, t, t*t, t*t*t])

    for dimension in range(0, 3):
        P = Vector([
                p[0][dimension],
                p[1][dimension],
                p[2][dimension],
                p[3][dimension]
        ])

        b_point[dimension] = M @ G @ P

    return b_point

# c_points: list[Vector], object of control points
# t: list[float], 0.0<=t_list[i]<=1.0
def createCubicBspline(context, collection, c_points, name, t):
    
    # points of Bspline
    Bspline = []

    for i in range(len(t)):
        Bspline.append(cubicBspline(t[i], c_points))

    # for i in range(subdivision + 1):
    #     t = i / subdivision
    #     Bspline.append(cubicBspline(t, c_points))

    return createPolyCurve(context, collection, name, Bspline)

# return 
# c_points:     list[Vector], control points
# t:            parameter list
# parameter
# initial_curve:list[Vector]
def solveCubicBspline(initial_curve):
    # if initial_curve_ob.type == 'CURVE':
    #     init_curve = initial_curve_ob.data

    # # points of initial path is data point 
    # Q = []
    # for point in init_curve.splines[0].points.values():
    #     Q.append(point.co.xyz)

    Q = []
    for point in initial_curve:
        Q.append(point.co.xyz)

    # have n point, 0 <= i <= n-1
    n = len(Q)

    # use cubic b-spline to fit
    def B3_0(t):
        return 0.16667 * (1-t) * (1-t) * (1-t)
    def B3_1(t):
        return 0.16667 * (3*t*t*t - 6*t*t + 4)
    def B3_2(t):
        return 0.16667 * (-3*t*t*t + 3*t*t + 3*t + 1)
    def B3_3(t):
        return 0.16667 * t*t*t
    
    t = computeChordLengthParameter(Q)

    # use least square
    # solve Ax = b
    A = Matrix(([0, 0, 0, 0],[0, 0, 0, 0],[0, 0, 0, 0],[0, 0, 0, 0]))
    # 4 control point 
    p = [Vector(), Vector(), Vector(), Vector()]

    # A
    for i in range(0, n):
        B0 = B3_0(t[i])
        B1 = B3_1(t[i])
        B2 = B3_2(t[i])
        B3 = B3_3(t[i])

        A[0][0] +=  B0 * B0
        A[0][1] +=  B0 * B1
        A[0][2] +=  B0 * B2
        A[0][3] +=  B0 * B3

        A[1][1] +=  B1 * B1
        A[1][2] +=  B1 * B2
        A[1][3] +=  B1 * B3

        A[2][2] +=  B2 * B2
        A[2][3] +=  B2 * B3

        A[3][3] +=  B3 * B3

    A[1][0] = A[0][1]

    A[2][0] = A[0][2]
    A[2][1] = A[1][2]

    A[3][0] = A[0][3]
    A[3][1] = A[1][3]
    A[3][2] = A[2][3]

    # dimension mean is x, y, z
    for dimension in range(0, 2):
        b = Vector([0, 0, 0, 0])
        for i in range(0, n):
            b[0] += B3_0(t[i]) * Q[i][dimension]
            b[1] += B3_1(t[i]) * Q[i][dimension]
            b[2] += B3_2(t[i]) * Q[i][dimension]
            b[3] += B3_3(t[i]) * Q[i][dimension]

        x = Vector()

        # solve Ax = b
        # x = inverse(A)b
        x = A.inverted() @ b

        p[0][dimension] = x[0]
        p[1][dimension] = x[1]
        p[2][dimension] = x[2]
        p[3][dimension] = x[3]
    
    p[0][2] = 0
    p[1][2] = 0
    p[2][2] = 0
    p[3][2] = 0

    return p, t

def computeOrientation(front, world_up):
    y = front.normalized().xyz
    x = y.cross(world_up.xyz)
    z = x.cross(y)
    return Matrix((x, y, z)).transposed().to_4x4()

def computeChordLengthParameter(Q):
    # have n point, 0 <= i <= n-1
    n = len(Q)
    # computer distance of curve
    d = 0
    for i in range(1, n):
        d += (Q[i] - Q[i-1]).length

    # define t[i] with chord-length
    # t[0] = 0, t[n-1] = 1
    t = [0.0,]
    for i in range(1, n):
        t.append(t[i-1] + (Q[i] - Q[i-1]).length/d)
    t[n-1] = 1.0

    return t




    
        
      