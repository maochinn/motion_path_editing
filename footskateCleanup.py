import math

import bpy
import bmesh
from mathutils import Vector, Euler, Matrix, Quaternion, geometry

class FootskateCleanup:

    @classmethod
    def AlphaBlend(cls, t):
        return 2 * t * t * t - 3 * t * t + 1
    

class FastIKSolver:
    boneDirections = []
    boneLengths = []

    totalLength = 0

    @classmethod
    def InitIK(cls,jointPositions, jointRotations):
        cls.totalLength = 0

        cls.boneLengths = [0,] * (len(jointPositions) - 1)
        cls.boneDirections = [None,] * (len(jointPositions) - 1)

        for i in range(len(jointPositions) - 1):
            vec = (jointPositions[i] - jointPositions[i + 1])
            cls.boneLengths[i]    = vec.magnitude
            cls.boneDirections[i] = vec.normalized()
            cls.totalLength      += cls.boneLengths[i]

    @classmethod
    def SolveIK(cls, jointPositions, jointRotations, target, useConstraint, constraint, Iterations=10, Epsilon=0.01):

        cls.InitIK(jointPositions, jointRotations)

        if ((jointPositions[-1] - target).magnitude > cls.totalLength):
            for i in range(len(jointPositions) - 2, -1, step = -1):
                vec = (target - jointPositions[i + 1]).normalized()
                jointPositions[i] = jointPositions[i + 1] + vec * cls.boneLengths[i]
        else:
            lastPos = jointPositions[0]
            # iterate backward & forward
            for k in range(cls.Iterations):
                jointPositions[0] = target
                for i in range(len(jointPositions)-1):
                    vec = (jointPositions[i] - jointPositions[i - 1]).normalized()
                    jointPositions[i] = jointPositions[i - 1] + vec * cls.boneLengths[i - 1]

                for i in range(len(jointPositions) - 2, -1, step = -1):
                    vec = (jointPositions[i] - jointPositions[i + 1]).normalized()
                    jointPositions[i] = jointPositions[i + 1] + vec * cls.boneLengths[i]

                if ((jointPositions[0] - lastPos).magnitude < Epsilon):
                    break

                lastPos = jointPositions[0]

        if useConstraint:
            for i in range(len(jointPositions)-1):
                normal = (jointPositions[i + 1] - jointPositions[i - 1]).normalized()

                point = jointPositions[i - 1]

                projectionPole = geometry.intersect_line_plane(constraint, constraint + normal, point, normal)
                projectionBone = geometry.intersect_line_plane(jointPositions[i], jointPositions[i] + normal, point, normal)

                Va = (projectionBone - jointPositions[i - 1])
                Vb = (projectionPole - jointPositions[i - 1])

                angle = math.acos(Va.normalize().dot(Vb.normalize()))
                cross = Va.cross(Vb)

                if (normal.dot(cross) < 0):
                    angle = -angle

                jointPositions[i] = Quaternion(normal, angle) * (jointPositions[i] - jointPositions[i - 1]) + jointPositions[i - 1]

        for i in range(1,len(jointPositions)):
            initBoneDir = cls.boneDirections[i - 1]
            boneDir = (jointPositions[i - 1] - jointPositions[i]).normalized

            jointRotations[i] = initBoneDir.rotation_difference(boneDir) * jointRotations[i]