import os
import math 
import numpy as np
import time
import pybullet 
import random
from datetime import datetime
import pybullet_data
from collections import namedtuple
from attrdict import AttrDict

from lively import OrientationLivelinessObjective, Solver, Translation, Rotation,Transform,SmoothnessMacroObjective, Size, PositionLivelinessObjective, CollisionAvoidanceObjective, JointLimitsObjective, BoxShape, CollisionSettingInfo, PositionMatchObjective,ScalarRange
from lxml import etree



ROBOT_URDF_PATH = "./ur_e_description/urdf/ur5e.urdf"
TABLE_URDF_PATH = os.path.join(pybullet_data.getDataPath(), "table/table.urdf")

class UR5Sim():
  
    def __init__(self, camera_attached=False):
        pybullet.connect(pybullet.GUI)
        #pybullet.setRealTimeSimulation(True)
        
        self.end_effector_index = 7
        self.ur5 = self.load_robot()
        self.num_joints = pybullet.getNumJoints(self.ur5)
        
        self.control_joints = ["shoulder_pan_joint", "shoulder_lift_joint", "elbow_joint", "wrist_1_joint", "wrist_2_joint", "wrist_3_joint"]
        self.joint_type_list = ["REVOLUTE", "PRISMATIC", "SPHERICAL", "PLANAR", "FIXED"]
        self.joint_info = namedtuple("jointInfo", ["id", "name", "type", "lowerLimit", "upperLimit", "maxForce", "maxVelocity", "controllable"])

        self.joints = AttrDict()
        for i in range(self.num_joints):
            info = pybullet.getJointInfo(self.ur5, i)
            jointID = info[0]
            jointName = info[1].decode("utf-8")
            jointType = self.joint_type_list[info[2]]
            jointLowerLimit = info[8]
            jointUpperLimit = info[9]
            jointMaxForce = info[10]
            jointMaxVelocity = info[11]
            controllable = True if jointName in self.control_joints else False
            info = self.joint_info(jointID, jointName, jointType, jointLowerLimit, jointUpperLimit, jointMaxForce, jointMaxVelocity, controllable)
            if info.type == "REVOLUTE":
                pybullet.setJointMotorControl2(self.ur5, info.id, pybullet.VELOCITY_CONTROL, targetVelocity=0, force=0)
            self.joints[info.name] = info     


    def load_robot(self):
        flags = pybullet.URDF_USE_SELF_COLLISION
        table = pybullet.loadURDF(TABLE_URDF_PATH, [0.5, 0, -0.6300], [0, 0, 0, 1])
        robot = pybullet.loadURDF(ROBOT_URDF_PATH, [0, 0, 0], [0, 0, 0, 1], flags=flags)
        return robot
    

    def set_joint_angles(self, joint_angles):
        poses = []
        indexes = []
        forces = []

        for name, pose in joint_angles.items():
            joint = self.joints[name]
            poses.append(pose)
            indexes.append(joint.id)
            forces.append(joint.maxForce)

        

        pybullet.setJointMotorControlArray(
            self.ur5, indexes,
            pybullet.POSITION_CONTROL,
            targetPositions=poses,
            targetVelocities=[0]*len(poses),
            positionGains=[0.04]*len(poses), forces=forces
        )


    def get_joint_angles(self):
        j = pybullet.getJointStates(self.ur5, [1,2,3,4,5,6])
        joints = [i[0] for i in j]
        return joints
    

    def check_collisions(self):
        collisions = pybullet.getContactPoints()
        if len(collisions) > 0:
            print("[Collision detected!] {}".format(datetime.now()))
            return True
        return False


    def calculate_ik(self, position, orientation):
        quaternion = pybullet.getQuaternionFromEuler(orientation)
        lower_limits = [-math.pi]*6
        upper_limits = [math.pi]*6
        joint_ranges = [2*math.pi]*6
        rest_poses = [0, -math.pi/2, -math.pi/2, -math.pi/2, -math.pi/2, 0]

        joint_angles = pybullet.calculateInverseKinematics(
            self.ur5, self.end_effector_index, position, quaternion, 
            jointDamping=[0.01]*6, upperLimits=upper_limits, 
            lowerLimits=lower_limits, jointRanges=joint_ranges, 
            restPoses=rest_poses
        )
        return joint_angles
       

    def add_gui_sliders(self):
        self.sliders = []
        self.sliders.append(pybullet.addUserDebugParameter("X", 0, 1, 0.4))
        self.sliders.append(pybullet.addUserDebugParameter("Y", -1, 1, 0))
        self.sliders.append(pybullet.addUserDebugParameter("Z", 0.3, 1, 0.4))
        self.sliders.append(pybullet.addUserDebugParameter("Rx", -math.pi/2, math.pi/2, 0))
        self.sliders.append(pybullet.addUserDebugParameter("Ry", -math.pi/2, math.pi/2, 0))
        self.sliders.append(pybullet.addUserDebugParameter("Rz", -math.pi/2, math.pi/2, 0))


    def read_gui_sliders(self):
        x = pybullet.readUserDebugParameter(self.sliders[0])
        y = pybullet.readUserDebugParameter(self.sliders[1])
        z = pybullet.readUserDebugParameter(self.sliders[2])
        Rx = pybullet.readUserDebugParameter(self.sliders[3])
        Ry = pybullet.readUserDebugParameter(self.sliders[4])
        Rz = pybullet.readUserDebugParameter(self.sliders[5])
        return [x, y, z, Rx, Ry, Rz]
        
    def get_current_pose(self):
        linkstate = pybullet.getLinkState(self.ur5, self.end_effector_index, computeForwardKinematics=True)
        position, orientation = linkstate[0], linkstate[1]
        return (position, orientation)

def demo_simulation():
    """ Demo program showing how to use the sim """
    sim = UR5Sim()
    #sim.add_gui_sliders()
    # Read the xml file into a string
    xml_file = ROBOT_URDF_PATH
    tree = etree.parse(xml_file)
    xml_string = etree.tostring(tree).decode()
    goal = {Translation:[1.0,0.0,0.5]}
    #print(xml_string)
    # Instantiate a new solver
    solver = Solver(
    urdf=xml_string, # Full urdf as a string
    objectives={
        # An example objective (smoothness macro)
        "position": PositionMatchObjective(name="MyPositionMatchObjective", weight=10, link="wrist_3_link"),
        "smoothness":SmoothnessMacroObjective(name="MySmoothnessObjective",weight=5, joints=True, links=True, origin=True),
        "positionLiveliness": PositionLivelinessObjective(name="MyLivelinessObjective",link="wrist_3_link",frequency=1,weight=20),
        
    },
    root_bounds=[
        ScalarRange(value=0.0,delta=0.0),ScalarRange(value=0.0,delta=0.0),ScalarRange(value=0.0,delta=0.0), # Translational, (x, y, z)
        ScalarRange(value=0.0,delta=0.0),ScalarRange(value=0.0,delta=0.0),ScalarRange(value=0.0,delta=0.0)  # Rotational, (r, p, y)
    ]
    )
    
    solver.compute_average_distance_table()
    # Run solve to get a solved state
    i=0
    current_time = time.time()
    #while i < 20:
    state = solver.solve(goals= {"position": Translation(x=0.47, y=-0.03, z=0.64),
                                 "positionLiveliness": Size(x=0.11,y=0.05,z=0.05)
                                 },weights = {},time = current_time)
        # Log the initial state
        #print(state.origin.as_dicts())
    print(state.joints)
    while True:   
        sim.set_joint_angles(state.joints)
        sim.check_collisions()
        pybullet.stepSimulation()
        delay = 1/30
        time.sleep(delay)
        current_time = time.time()
        state = solver.solve(goals= {"position": Translation(x=0.47, y=-0.03, z=0.64),
                        "positionLiveliness": Size(x=0.15,y=0.05,z=0.4)
                        },weights = {},time = current_time)
        #print(solver.goals)
        #print(solver)





    #while True:
    #    x, y, z, Rx, Ry, Rz = sim.read_gui_sliders()
    #    joint_angles = sim.calculate_ik([x, y, z], [Rx, Ry, Rz])
    #    sim.set_joint_angles(joint_angles)
    #    sim.check_collisions()

if __name__ == "__main__":
    demo_simulation()