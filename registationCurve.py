import bpy
from bpy.types import Operator
import math
from mathutils import Vector, Euler, Matrix


from .importBvh import NodeBVH, MotionPathAnimation
from .createBlenderThing import createPolyCurve


class RegistrationCurve:
    registration_curves = []
    
    @classmethod
    def AddRegistrationCurve(cls, context, bvh_motion_0, bvh_motion_1):
        curve = RegistrationCurve(context, bvh_motion_0, bvh_motion_1)
        
        if curve != None:
            cls.registration_curves.append(curve)

        return curve

    @classmethod
    def GetBlendingMotionByName(cls, name):
        if cls.registration_curves != None:
            for r_curve in cls.registration_curves:
                if r_curve.blending_motion.name == name:
                    return r_curve
        return None

    def updateBlendingInterpolation(self, w0):
        for t in range(len(self.M_0)):
            self.w_0[t] = w0
        
        if self.blending_motion is not None:
            bpy.data.objects.remove(self.blending_motion)
            self.blending_motion = None

        self.blending_motion = self.generateBlendingMotion()
        
    def updateBlendingTransition(self):
        for t in range(len(self.M_0)):
            self.w_0[t] = 1.0 - (t / (len(self.M_0) - 1))

        if self.blending_motion is not None:
            bpy.data.objects.remove(self.blending_motion)

        self.blending_motion = self.generateBlendingMotion()

    def __init__(self, context, bvh_motion_0, bvh_motion_1):
        self.context = context
        
        self.name = bvh_motion_0.name + "_blend_" + bvh_motion_1.name

        self.bvh_motion_0 = bvh_motion_0
        self.bvh_motion_1 = bvh_motion_1

        self.blending_motion = None
        # we only accept 2 motion 
        # mean Mj and j = 0, 1

        # weight of motion 0

        def extractMotiondata(skeleton_name, roots, nodes, frame_amount):
            M = []
            for f in range(0, frame_amount):
                M_f = []
                M_f.append(roots[f].co.xyz)
                for name in skeleton_name:
                    joints = [node for node in nodes if name == node.name]
                    if joints:
                        node = joints[0]
                        data = node.getNewAnimData(f)
                        M_f.append(Vector((
                            math.radians(data[3]),
                            math.radians(data[4]),
                            math.radians(data[5]))))
                    else:
                        print("ERROR::TWO_MOTION::SKELETON::UNSAME")
                        return None

                M.append(tuple(M_f))

            return M

        def extractJointPosition(skeleton_objs, motion_name, skeleton_name, frame_amount):
            p = []
            for f in range(frame_amount):
                p_f = []
                bpy.context.scene.frame_set(f)
                for name in skeleton_name:
                    joint_position = [ob.location.xyz for ob in skeleton_objs if name in ob.name]
                    if joint_position:
                        p_f.append(joint_position[0])
                    else:
                        print("ERROR::TWO_MOTION::SKELETON::UNSAME")
                        return None
                p.append(p_f)

            return p

        self.w_0 = []
        for t in range(self.bvh_motion_0.frames_bvh):
            self.w_0.append(1.0)

        skeleton_name = []
        root = NodeBVH.getRoot(self.bvh_motion_0.nodes_bvh)
        skeleton_name.append(root.name)
        for node in self.bvh_motion_0.nodes_bvh.values():
            if node is not root:
                skeleton_name.append(node.name)


        self.M_0 = extractMotiondata(
            skeleton_name,
            self.bvh_motion_0.new_motion.data.splines[0].points.values(),
            self.bvh_motion_0.nodes_bvh.values(), 
            self.bvh_motion_0.frames_bvh)
        self.M_1 = extractMotiondata(
            skeleton_name,
            self.bvh_motion_1.new_motion.data.splines[0].points.values(),
            self.bvh_motion_1.nodes_bvh.values(), 
            self.bvh_motion_1.frames_bvh)

        skeleton_name = []
        # set skeleton order
        for ob in self.bvh_motion_0.skeleton.all_objects.values():
                if any(x in ob.name for x in ['_head', '_tail']):
                    skeleton_name.append(ob.name[ob.name.rfind("."):])


        self.p_0 = extractJointPosition(
            self.bvh_motion_0.skeleton.all_objects.values(),
            self.bvh_motion_0.name,
            skeleton_name, 
            self.bvh_motion_0.frames_bvh)
        self.p_1 = extractJointPosition(
            self.bvh_motion_1.skeleton.all_objects.values(),
            self.bvh_motion_1.name,
            skeleton_name,
            self.bvh_motion_1.frames_bvh)

        self.generateTransformMap()
        self.generateDistanceMap()

        # create registration
        self.generateTimewarpCurve()
        self.generateAligmentCurve()

    def getAlignmentTransformation(self, F0, F1, frame = 5):
        F0_end = min(F0 + frame, len(self.p_0))
        F1_end = min(F1 + frame, len(self.p_1))

        if F0_end - F0 > F1_end - F1:
            F0_end = F0 + (F1_end - F1)
        else:
            F1_end = F1 + (F0_end - F0)

        # 2D list to 1D list
        # https://www.geeksforgeeks.org/python-ways-to-flatten-a-2d-list/
        #[j for sub in ini_list for j in sub] 

        y0 = [p_i.y for i in range(F0, F0_end) for p_i in self.p_0[i] ]
        x0 = [p_i.x for i in range(F0, F0_end) for p_i in self.p_0[i] ]
        y1 = [p_i.y for i in range(F1, F1_end) for p_i in self.p_1[i] ]
        x1 = [p_i.x for i in range(F1, F1_end) for p_i in self.p_1[i] ]

        n = len(y0)
        w_i = 1.0 / n

        y0_bar = sum(w_i * y0[i] for i in range(n))
        x0_bar = sum(w_i * x0[i] for i in range(n))
        y1_bar = sum(w_i * y1[i] for i in range(n))
        x1_bar = sum(w_i * x1[i] for i in range(n))


        theta = math.atan(
            (sum(w_i * (y0[i] * x1[i] - y1[i] * x0[i]) for i in range(n)) - (y0_bar * x1_bar - y1_bar * x0_bar)) / 
            (sum(w_i * (y0[i] * y1[i] + x0[i] * x1[i]) for i in range(n)) - (y0_bar * y1_bar + x0_bar * x1_bar)) )

        y_0 = y0_bar - y1_bar * math.cos(theta) - x1_bar * math.sin(theta)
        x_0 = x0_bar + y1_bar * math.sin(theta) - x1_bar * math.cos(theta)

        return (theta, y_0, x_0)

    # (theta, y, x) to transform matrix 
    @staticmethod
    def transformVectorToMatrix(vec):
        return Matrix.Translation(Vector((vec[2], vec[1], 0.0))) @ Matrix.Rotation(vec[0], 4, 'Z')

    @staticmethod
    def transformMatrixToVector(mat):
        loc, rot, sca = mat.decompose()
        eul = rot.to_euler()
        return Vector((eul.z, loc.y, loc.x))


    def generateTransformMap(self):
        self.transform_map = []
        for F0 in range(len(self.p_0)):
            row = []
            for F1 in range(len(self.p_1)):
                row.append(self.getAlignmentTransformation(F0, F1))
            self.transform_map.append(row)

    def generateDistanceMap(self):
        # F0 is frame idx of motion 1
        # F1 is frame idx of motion 2 
        def D(F0, F1):
            n = len(self.p_0[F0])
            w_i = 1.0 / n

            distance = 0.0

            T = self.transformVectorToMatrix(self.transform_map[F0][F1])
            for p0_i, p1_i in zip(self.p_0[F0], self.p_1[F1]):
                distance += w_i * (p0_i - T @ p1_i).length_squared

            return distance

        self.distance_map = []
        for F0 in range(len(self.p_0)):
            row = []
            for F1 in range(len(self.p_1)):    
                row.append(D(F0, F1))
            self.distance_map.append(row)

    def generateTimewarpCurve(self):
        # refer: https://blog.csdn.net/seagal890/article/details/95028066
        def minimal_cost_connecting_path(cost):
            w = len(cost)
            h = len(cost[0])
            dp = [[0 for y in range(h)] for x in range(w)]

            for i in range(1,w):
                dp[i][0] = dp[i - 1][0] + cost[i][0] 
            
            for j in range(1,h):
                dp[0][j] = dp[0][j - 1] + cost[0][j]


            for j in range(1,h):
                for i in range(1,w):
                    min_cost = min(dp[i - 1][j - 1], dp[i - 1][j], dp[i][j - 1])
                    dp[i][j] = min_cost + cost[i][j]

            
            # track path
            # S[u] = (S1, S2)
            S = []
            i = w - 1
            j = h - 1
            S.append((i, j))
            while i > 0 and j > 0:
                min_cost = min(dp[i - 1][j - 1], dp[i - 1][j], dp[i][j - 1])
                if min_cost == dp[i][j - 1]:
                    j -= 1
                elif min_cost == dp[i - 1][j]:
                    i -= 1
                else:
                    i -= 1
                    j -= 1
                S.append((i, j))
            S.reverse()
            return S
                
        self.S = minimal_cost_connecting_path(self.distance_map)
                    
    def generateAligmentCurve(self):
        
        self.A = []
        for u in range(len(self.S)):
            S0_u = self.S[u][0]
            S1_u = self.S[u][1]
            
            self.A.append((
                Vector((0.0, 0.0, 0.0)), 
                Vector(self.transform_map[S0_u][S1_u])))

        for u in range(1, len(self.A)):
            
            # if delta thete > 0.7 radian, we will inverse that(+- pi radian) 
            if math.fabs(self.A[u][1][0] - self.A[u-1][1][0]) > 0.7:
                old_radian = self.A[u][1][0]
                new_radian = self.A[u][1][0] - math.pi if self.A[u][1][0] > self.A[u-1][1][0] else self.A[u][1][0] + math.pi

                old_translate = Vector((self.A[u][1][2], self.A[u][1][1], 0.0))
                new_translate = old_translate + Matrix.Rotation(old_radian, 4, 'Z') @ self.M_1[self.S[u][1]][0] - Matrix.Rotation(new_radian, 4, 'Z') @ self.M_1[self.S[u][1]][0]

                # temp1 = Matrix.Translation(old_translate) @ Matrix.Rotation(old_radian, 4, 'Z') @ self.M_1[self.S[u][1]][0]
                # temp2 = Matrix.Translation(new_translate) @ Matrix.Rotation(new_radian, 4, 'Z') @ self.M_1[self.S[u][1]][0]

                self.A[u] = (
                    Vector((0.0, 0.0, 0.0)), 
                    Vector((new_radian, new_translate.y, new_translate.x)))

    def generateBlendingMotion(self):

        def linearInterpolation(f0, f1, t):
            return f0 * (1.0 - t) + f1 * t


        def W0(f):
            low = int(f)
            high = low + 1

            if high < len(self.w_0):
                return linearInterpolation(self.w_0[low], self.w_0[high], f - low) 
            else:
                return self.w_0[-1]

        def A(u):
            low = int(u)
            high = low + 1

            if high < len(self.A):
                return (
                    linearInterpolation(self.A[low][0], self.A[high][0], u - low),
                    linearInterpolation(self.A[low][1], self.A[high][1], u - low))
            else:
                return (self.A[-1][0], self.A[-1][1])
            
        def S(u):
            low = int(u)
            high = low + 1

            if high < len(self.S):
                return (
                    linearInterpolation(self.S[low][0], self.S[high][0], u - low),
                    linearInterpolation(self.S[low][1], self.S[high][1], u - low))
            else:
                return (self.S[-1][0], self.S[-1][1])

        def M0(f):
            low = int(f)
            high = low + 1

            if high < len(self.M_0):
                return [linearInterpolation(Ml_i, Mh_i, f - low) for Ml_i, Mh_i in zip(self.M_0[low], self.M_0[high])]
            else:
                return self.M_0[-1]
        def M1(f):
            low = int(f)
            high = low + 1

            if high < len(self.M_1):
                return [linearInterpolation(Ml_i, Mh_i, f - low) for Ml_i, Mh_i in zip(self.M_1[low], self.M_1[high])]
            else:
                return self.M_1[-1]

        self.B = []

        T = []
        T.append(Vector((0.0, 0.0, 0.0)))

        t = 0
        u = 0
        delta_t = 1

        du = 1.0 / len(self.S)
        dS_0 = 1.0 / len(self.M_0)
        dS_1 = 1.0 / len(self.M_1)

        w = (W0(0.0), 1.0 - W0(0.0))
        while u < len(self.S):
            B_i = []

            A0_u = self.transformVectorToMatrix(A(u)[0])
            A1_u = self.transformVectorToMatrix(A(u)[1])

            M0_u = M0(S(u)[0])
            M1_u = M1(S(u)[1])
            # i = 0~N-1
            # N is amount of joint
            for i in range(len(M0_u)):
                if i == 0:
                    B_i.append(
                        w[0] * (A0_u @ M0_u[i]) + 
                        w[1] * (A1_u @ M1_u[i]) )
                else:
                    B_i.append(
                        w[0] * M0_u[i] + 
                        w[1] * M1_u[i] )


            B_i[0] = self.transformVectorToMatrix(T[t]) @ B_i[0]
            # B_i[0] = self.transformVectorToMatrix(T[0]) @ self.transformVectorToMatrix(A(0)[0]) @ M0(S(u)[1])[0]
            # B_i[0] = self.transformVectorToMatrix(T[0]) @ self.transformVectorToMatrix(A(0)[1]) @ M1(S(u)[1])[0]
            self.B.append(B_i)

            delta_u = w[0] * (du / dS_0) + w[1] * (du / dS_1)
            t += delta_t
            u += delta_u

            delta_T = []
            for j in range(len(w)):
                T_i_0 = self.transformVectorToMatrix(T[t-delta_t])
                A_i_0 = self.transformVectorToMatrix(A(u-delta_u)[j])
                A_i_1 = self.transformVectorToMatrix(A(u)[j])
                delta_T.append(
                    self.transformMatrixToVector(
                    T_i_0 @ A_i_0 @ A_i_1.inverted()))

            T_i = Vector((0.0, 0.0, 0.0))
            for j in range(len(w)):
                T_i += w[j] * delta_T[j]
            T.append(T_i)

            w = (W0(S(u)[0]), 1.0 - W0(S(u)[0]))
            

        return createPolyCurve(
            self.context, self.context.scene.collection, 
            self.name, [B_i[0] for B_i in self.B])

    def createMotionPathAnimation(self):

        nodes_clone = NodeBVH.nodesBVHCopy(
            self.bvh_motion_0.nodes_bvh, self.bvh_motion_0.frames_bvh)


        # set nodes to initial position
        NodeBVH.updateNodesWorldPosition(nodes_clone, -1)

        for node in nodes_clone.values():
            node.anim_data.clear()
            node.anim_data = [(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)]
            node.new_anim_data.clear()
            node.new_anim_data = [(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)]

        for B_i in self.B:
            for j, node in enumerate(nodes_clone.values()):
                if node.parent is None:
                    data = (
                        B_i[0].x, B_i[0].y, B_i[0].z, 
                        math.degrees(B_i[1].x), math.degrees(B_i[1].y), math.degrees(B_i[1].z))
                    node.anim_data.append(data)
                    node.new_anim_data.append(data)
                else:
                    data = (
                        0.0, 0.0, 0.0, 
                        math.degrees(B_i[j+1].x), math.degrees(B_i[j+1].y), math.degrees(B_i[j+1].z))
                    node.anim_data.append(data)
                    node.new_anim_data.append(data)
            
        return MotionPathAnimation.AddPathAnimationFromCreated(
            self.context, self.blending_motion.name, nodes_clone, len(self.B), self.bvh_motion_0.frame_time_bvh)   

class MAOGenerateRegistrationCurve(Operator):
    bl_idname = "mao_animation.registration_curve"
    bl_label = "combine two motion animation to generate registration curve"
    bl_description = "OUO/"

    @classmethod
    def poll(cls, context):
        # path_animation is not empty
        motion_1_name = context.scene.select_motion_1_name
        motion_2_name = context.scene.select_motion_2_name

        motion_1 = MotionPathAnimation.GetPathAnimationByName(motion_1_name)
        motion_2 = MotionPathAnimation.GetPathAnimationByName(motion_2_name)

        if motion_1 is None or motion_2 is None:
            return False

        return True

    def execute(self, context):
        motion_1_name = context.scene.select_motion_1_name
        motion_2_name = context.scene.select_motion_2_name

        motion_1 = MotionPathAnimation.GetPathAnimationByName(motion_1_name)
        motion_2 = MotionPathAnimation.GetPathAnimationByName(motion_2_name)

        blending_motion = RegistrationCurve.AddRegistrationCurve(context, motion_1, motion_2)
        if bpy.context.scene.r_curve_blending_method == 'INT':
            blending_motion.updateBlendingInterpolation(bpy.context.scene.r_curve_motion_1_weight)
        elif bpy.context.scene.r_curve_blending_method == 'TRA':
            blending_motion.updateBlendingTransition()

        return {'FINISHED'}

class MAORegistrationCurveToPathAnimation(Operator):
    bl_idname = "mao_animation.registration_curve_to_path_animation"
    bl_label = "generate registration curve to motion path animation"
    bl_description = "OUO/"

    @classmethod
    def poll(cls, context):
        for ob in context.selected_objects:
            r_curve = RegistrationCurve.GetBlendingMotionByName(ob.name)
            if r_curve is not None:
                return True
        return False

    def execute(self, context):
        for ob in context.selected_objects:
            r_curve = RegistrationCurve.GetBlendingMotionByName(ob.name)
            if r_curve is not None:
                r_curve.createMotionPathAnimation()

        return {'FINISHED'}


def draw(context, layout):
    row = layout.row()
    row.prop_search(
        data=context.scene,
        property="select_motion_1_name",
        search_data=bpy.data,
        search_property="collections",
        text="motion 1")
    row = layout.row()
    row.prop_search(
        data=context.scene,
        property="select_motion_2_name",
        search_data=bpy.data,
        search_property="collections",
        text="motion 2")
    row = layout.row()
    row.prop(context.scene,"r_curve_motion_1_weight",text="motion 1 w")
    
    row = layout.row()
    row.prop(context.scene,"r_curve_blending_method",text="blending mehod")

    row = layout.row()
    row.operator('mao_animation.registration_curve', text = "generate registration curve")

    row = layout.row()
    row.operator('mao_animation.registration_curve_to_path_animation', text = "generate motion path")

def register():
    bpy.utils.register_class(MAOGenerateRegistrationCurve)
    bpy.utils.register_class(MAORegistrationCurveToPathAnimation)
    
    bpy.types.Scene.select_motion_1_name = bpy.props.StringProperty()
    bpy.types.Scene.select_motion_2_name = bpy.props.StringProperty()

    def updateBlendingWeight(self, context):
        # print(bpy.context.scene.r_curve_motion_1_weight)
        for ob in context.selected_objects:
            r_curve = RegistrationCurve.GetBlendingMotionByName(ob.name)
            if r_curve is not None:
                r_curve.updateBlendingInterpolation(bpy.context.scene.r_curve_motion_1_weight)
                r_curve.blending_motion.select_set(True)

    bpy.types.Scene.r_curve_motion_1_weight = bpy.props.FloatProperty(default=1.0,min=0.0,max=1.0, update=updateBlendingWeight)

    bpy.types.Scene.r_curve_blending_method = bpy.props.EnumProperty(
            name="blending method",
            description="Select blending method",
            items=(('INT', "Interpolation", "weight is fixed"),
                   ('TRA', "Transition", "weight will 0 to 1")),
            default='INT',
            )

def unregister():
    bpy.utils.unregister_class(MAOGenerateRegistrationCurve)
    bpy.utils.unregister_class(MAORegistrationCurveToPathAnimation)

    del bpy.types.Scene.select_motion_1_name
    del bpy.types.Scene.select_motion_2_name
    del bpy.types.Scene.r_curve_motion_1_weight
    
        