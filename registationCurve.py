import bpy
import math
from mathutils import Vector, Euler, Matrix

from .importBvh import NodeBVH
from .createBlenderThing import createPolyCurve


class RegistrationCurve:
    registration_curves = []
    
    @classmethod
    def AddRegistrationCurve(cls, context, bvh_motion_0, bvh_motion_1):
        curve = RegistrationCurve(context, bvh_motion_0, bvh_motion_1)
        
        if curve != None:
            cls.registration_curves.append(curve)

        return curve

    

    def __init__(self, context, bvh_motion_0, bvh_motion_1):
        self.context = context
        
        self.bvh_motion_0 = bvh_motion_0
        self.bvh_motion_1 = bvh_motion_1
        # we only accept 2 motion 
        # mean Mj and j = 0, 1
        self.w = [1.0, 0.0]

        def extractMotiondata(roots, nodes, frame_amount):
            M = []
            for f in range(0, frame_amount):
                # M[f] = (p_R(f), q_1(f), q_2(f), ... , q_n(f)) 
                # p_R is position of root
                # q_i is rotation of ith joint
                M_f = []
                # M_f.append(Vector(NodeBVH.getRoot(nodes).anim_data[f+1][0:3]))
                M_f.append(roots[f].co.xyz)
                for node in nodes.values():
                    data = node.getAnimData(f)
                    M_f.append(Vector((
                         math.radians(data[3]),
                         math.radians(data[4]),
                         math.radians(data[5]))))

                M.append(tuple(M_f))

            return M

        def extractJointPosition(skeleton_objs, nodes, frame_amount):
            p = []
            for f in range(frame_amount):
                p_f = []
                # NodeBVH.updateNodesWorldPosition(nodes, f)
                # for node in nodes.values():
                #     p_f.append(node.world_head.xyz)
                bpy.context.scene.frame_set(f)
                for ob in skeleton_objs:
                    if any(x in ob.name for x in ['_head', '_tail']):
                        p_f.append(ob.location.xyz)
                p.append(p_f)

            return p

        self.M_0 = extractMotiondata(
            self.bvh_motion_0.new_motion.data.splines[0].points.values(),
            self.bvh_motion_0.nodes_bvh, 
            self.bvh_motion_0.frames_bvh)
        self.M_1 = extractMotiondata(
            self.bvh_motion_1.new_motion.data.splines[0].points.values(), 
            self.bvh_motion_1.nodes_bvh, 
            self.bvh_motion_1.frames_bvh)

        self.p_0 = extractJointPosition(
            self.bvh_motion_0.skeleton.all_objects.values(),
            self.bvh_motion_0.nodes_bvh, 
            self.bvh_motion_0.frames_bvh)
        self.p_1 = extractJointPosition(
            self.bvh_motion_1.skeleton.all_objects.values(),
            self.bvh_motion_1.nodes_bvh,
            self.bvh_motion_1.frames_bvh)

        self.generateTransformMap()
        self.generateDistanceMap()

        # create registration
        self.generateTimewarpCurve()
        self.generateAligmentCurve()

        self.w = [1.0, 0.0]
        self.generateBlendingMotion()
        self.w = [0.5, 0.5]
        self.generateBlendingMotion()
        self.w = [0.0, 1.0]
        self.generateBlendingMotion()


    #def createAlignmentCurve(self):


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
        for F1 in range(len(self.p_1)):
            row = []
            for F0 in range(len(self.p_0)):
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
        for F1 in range(len(self.p_1)):
            row = []
            for F0 in range(len(self.p_0)):
                row.append(D(F0, F1))
            self.distance_map.append(row)

    def generateTimewarpCurve(self):
        # refer: https://blog.csdn.net/seagal890/article/details/95028066
        def minimal_cost_connecting_path(cost):
            w = len(cost[0])
            h = len(cost)
            dp = [[0 for x in range(w)] for y in range(h)]

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
            
            if math.fabs(self.A[u][1][0] - self.A[u-1][1][0]) > 3.0:
                old_radian = self.A[u][1][0]
                new_radian = self.A[u][1][0] - math.pi if self.A[u][1][0] > self.A[u-1][1][0] else self.A[u][1][0] + math.pi

                old_translate = Vector((self.A[u][1][2], self.A[u][1][1], 0.0))
                new_translate = (
                    Matrix.Translation(old_translate) @ Matrix.Rotation(old_radian - new_radian, 4, 'Z')).to_translation() 

                self.A[u] = (
                    Vector((0.0, 0.0, 0.0)), 
                    Vector((new_radian, new_translate.y, new_translate.x)))

    def generateBlendingMotion(self):

        def linearInterpolation(f0, f1, t):
            return f0 * (1.0 - t) + f1 * t

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

        B = []

        T = []
        T.append(Vector((0.0, 0.0, 0.0)))

        t = 0
        u = 0
        delta_t = 1

        du = 1.0 / len(self.S)
        dS_0 = 1.0 / len(self.M_0)
        dS_1 = 1.0 / len(self.M_1)
        while u < len(self.S):
            B_i = []
            # i = 0~N-1
            # N is amount of joint
            for i in range(len(self.M_0[0])):
                if i == 0:
                    A_0 = self.transformVectorToMatrix(A(u)[0])
                    A_1 = self.transformVectorToMatrix(A(u)[1])
                    B_i.append(
                        self.w[0] * (A_0 @ M0(S(u)[0])[i]) + 
                        self.w[1] * (A_1 @ M1(S(u)[1])[i]) )
                else:
                    B_i.append(
                        self.w[0] * M0(S(u)[0])[i] + 
                        self.w[1] * M1(S(u)[1])[i] )


            B_i[0] = self.transformVectorToMatrix(T[t]) @ B_i[0]
            # B_i[0] = self.transformVectorToMatrix(T[0]) @ self.transformVectorToMatrix(A(u)[0]) @ M1(S(u)[1])[0]
            B.append(B_i)

            delta_u = self.w[0] * (du / dS_0) + self.w[1] * (du / dS_1)
            t += delta_t
            u += delta_u

            delta_T = []
            for j in range(len(self.w)):
                T_i_0 = self.transformVectorToMatrix(T[t-delta_t])
                A_i_0 = self.transformVectorToMatrix(A(u-delta_u)[j])
                A_i_1 = self.transformVectorToMatrix(A(u)[j])
                delta_T.append(
                    self.transformMatrixToVector(
                    T_i_0 @ A_i_0 @ A_i_1.inverted()))
                # delta_T.append(T[t-delta_t] + A(u-delta_u)[j] - A(u)[j])

            T_i = Vector((0.0, 0.0, 0.0))
            for j in range(len(self.w)):
                T_i += self.w[j] * delta_T[j]
            T.append(T_i)
            


        temp = [B_i[0] for B_i in B]
        createPolyCurve(self.context, self.context.scene.collection, "blending motion", temp)


            

            


  
    
        