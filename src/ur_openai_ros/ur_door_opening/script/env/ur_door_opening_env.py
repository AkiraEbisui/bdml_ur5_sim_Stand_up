#!/usr/bin/env python
'''
    By Akira Ebisui <shrimp.prawn.lobster713@gmail.com>
'''
# Python
import copy
import numpy as np
import math
import sys
import time
from matplotlib import pyplot as plt

# ROS 
import rospy
import tf
from tf.transformations import euler_from_quaternion, quaternion_from_euler

from joint_publisher import JointPub
from joint_traj_publisher import JointTrajPub

# Gazebo
from gazebo_msgs.srv import SetModelState, SetModelStateRequest, GetModelState
from gazebo_msgs.srv import GetWorldProperties
from gazebo_msgs.msg import LinkStates 

# For reset GAZEBO simultor
from gazebo_connection import GazeboConnection
from controllers_connection import ControllersConnection

# ROS msg
from geometry_msgs.msg import Pose, Point, Quaternion, Vector3, WrenchStamped
from sensor_msgs.msg import JointState
from std_msgs.msg import String
from std_srvs.srv import SetBool, SetBoolResponse, SetBoolRequest
from std_srvs.srv import Empty

# Gym
import gym
from gym import utils, spaces
from gym.utils import seeding
from gym.envs.registration import register

# For inherit RobotGazeboEnv
from env import robot_gazebo_env_goal

# UR5 Utils
from env.ur_setups import setups
from env import ur_utils

rospy.loginfo("register...")
#register the training environment in the gym as an available one
reg = gym.envs.register(
    id='URSimDoorOpening-v0',
    entry_point='env.ur_door_opening_env:URSimDoorOpening', # Its directory associated with importing in other sources like from 'ur_reaching.env.ur_sim_env import *' 
    #timestep_limit=100000,
    )

class URSimDoorOpening(robot_gazebo_env_goal.RobotGazeboEnv):
    def __init__(self):
        rospy.logdebug("Starting URSimDoorOpening Class object...")

        # Init GAZEBO Objects
        self.set_obj_state = rospy.ServiceProxy('/gazebo/set_model_state', SetModelState)
        self.get_world_state = rospy.ServiceProxy('/gazebo/get_world_properties', GetWorldProperties)

        # Subscribe joint state and target pose
        rospy.Subscriber("/ft_sensor_topic", WrenchStamped, self.wrench_stamped_callback)
        rospy.Subscriber("/joint_states", JointState, self.joints_state_callback)
        rospy.Subscriber("/gazebo/link_states", LinkStates, self.link_state_callback)

        # Gets training parameters from param server
        self.desired_pose = Pose()
        self.running_step = rospy.get_param("/running_step")
        self.max_height = rospy.get_param("/max_height")
        self.min_height = rospy.get_param("/min_height")
        self.observations = rospy.get_param("/observations")
        
        # Joint limitation
        shp_max = rospy.get_param("/joint_limits_array/shp_max")
        shp_min = rospy.get_param("/joint_limits_array/shp_min")
        shl_max = rospy.get_param("/joint_limits_array/shl_max")
        shl_min = rospy.get_param("/joint_limits_array/shl_min")
        elb_max = rospy.get_param("/joint_limits_array/elb_max")
        elb_min = rospy.get_param("/joint_limits_array/elb_min")
        wr1_max = rospy.get_param("/joint_limits_array/wr1_max")
        wr1_min = rospy.get_param("/joint_limits_array/wr1_min")
        wr2_max = rospy.get_param("/joint_limits_array/wr2_max")
        wr2_min = rospy.get_param("/joint_limits_array/wr2_min")
        wr3_max = rospy.get_param("/joint_limits_array/wr3_max")
        wr3_min = rospy.get_param("/joint_limits_array/wr3_min")
        self.joint_limits = {"shp_max": shp_max,
                             "shp_min": shp_min,
                             "shl_max": shl_max,
                             "shl_min": shl_min,
                             "elb_max": elb_max,
                             "elb_min": elb_min,
                             "wr1_max": wr1_max,
                             "wr1_min": wr1_min,
                             "wr2_max": wr2_max,
                             "wr2_min": wr2_min,
                             "wr3_max": wr3_max,
                             "wr3_min": wr3_min
                             }

        shp_init_value0 = rospy.get_param("/init_joint_pose0/shp")
        shl_init_value0 = rospy.get_param("/init_joint_pose0/shl")
        elb_init_value0 = rospy.get_param("/init_joint_pose0/elb")
        wr1_init_value0 = rospy.get_param("/init_joint_pose0/wr1")
        wr2_init_value0 = rospy.get_param("/init_joint_pose0/wr2")
        wr3_init_value0 = rospy.get_param("/init_joint_pose0/wr3")
        self.init_joint_pose0 = [shp_init_value0, shl_init_value0, elb_init_value0, wr1_init_value0, wr2_init_value0, wr3_init_value0]

        shp_init_value1 = rospy.get_param("/init_joint_pose1/shp")
        shl_init_value1 = rospy.get_param("/init_joint_pose1/shl")
        elb_init_value1 = rospy.get_param("/init_joint_pose1/elb")
        wr1_init_value1 = rospy.get_param("/init_joint_pose1/wr1")
        wr2_init_value1 = rospy.get_param("/init_joint_pose1/wr2")
        wr3_init_value1 = rospy.get_param("/init_joint_pose1/wr3")
        self.init_joint_pose1 = [shp_init_value1, shl_init_value1, elb_init_value1, wr1_init_value1, wr2_init_value1, wr3_init_value1]
#	print("[init_joint_pose1]: ", [shp_init_value1, shl_init_value1, elb_init_value1, wr1_init_value1, wr2_init_value1, wr3_init_value1])

        shp_init_value2 = rospy.get_param("/init_joint_pose2/shp")
        shl_init_value2 = rospy.get_param("/init_joint_pose2/shl")
        elb_init_value2 = rospy.get_param("/init_joint_pose2/elb")
        wr1_init_value2 = rospy.get_param("/init_joint_pose2/wr1")
        wr2_init_value2 = rospy.get_param("/init_joint_pose2/wr2")
        wr3_init_value2 = rospy.get_param("/init_joint_pose2/wr3")
        self.init_joint_pose2 = [shp_init_value2, shl_init_value2, elb_init_value2, wr1_init_value2, wr2_init_value2, wr3_init_value2]
#	print("[init_joint_pose2]: ", [shp_init_value2, shl_init_value2, elb_init_value2, wr1_init_value2, wr2_init_value2, wr3_init_value2])

        shp_after_rotate = rospy.get_param("/eelink_pose_after_rotate/shp")
        shl_after_rotate = rospy.get_param("/eelink_pose_after_rotate/shl")
        elb_after_rotate = rospy.get_param("/eelink_pose_after_rotate/elb")
        wr1_after_rotate = rospy.get_param("/eelink_pose_after_rotate/wr1")
        wr2_after_rotate = rospy.get_param("/eelink_pose_after_rotate/wr2")
        wr3_after_rotate = rospy.get_param("/eelink_pose_after_rotate/wr3")
        self.after_rotate = [shp_after_rotate, shl_after_rotate, elb_after_rotate, wr1_after_rotate, wr2_after_rotate, wr3_after_rotate]

        shp_after_pull = rospy.get_param("/eelink_pose_after_pull/shp")
        shl_after_pull = rospy.get_param("/eelink_pose_after_pull/shl")
        elb_after_pull = rospy.get_param("/eelink_pose_after_pull/elb")
        wr1_after_pull = rospy.get_param("/eelink_pose_after_pull/wr1")
        wr2_after_pull = rospy.get_param("/eelink_pose_after_pull/wr2")
        wr3_after_pull = rospy.get_param("/eelink_pose_after_pull/wr3")
        self.after_pull = [shp_after_pull, shl_after_pull, elb_after_pull, wr1_after_pull, wr2_after_pull, wr3_after_pull]

        r_drv_value1 = rospy.get_param("/init_grp_pose1/r_drive")
        l_drv_value1 = rospy.get_param("/init_grp_pose1/l_drive")
        r_flw_value1 = rospy.get_param("/init_grp_pose1/r_follower")
        l_flw_value1 = rospy.get_param("/init_grp_pose1/l_follower")
        r_spr_value1 = rospy.get_param("/init_grp_pose1/r_spring")
        l_spr_value1 = rospy.get_param("/init_grp_pose1/l_spring")
        self.init_grp_pose1 = [r_drv_value1, l_drv_value1, r_flw_value1, l_flw_value1, r_spr_value1, l_spr_value1]

        r_drv_value2 = rospy.get_param("/init_grp_pose2/r_drive")
        l_drv_value2 = rospy.get_param("/init_grp_pose2/l_drive")
        r_flw_value2 = rospy.get_param("/init_grp_pose2/r_follower")
        l_flw_value2 = rospy.get_param("/init_grp_pose2/l_follower")
        r_spr_value2 = rospy.get_param("/init_grp_pose2/r_spring")
        l_spr_value2 = rospy.get_param("/init_grp_pose2/l_spring")
        self.init_grp_pose2 = [r_drv_value2, l_drv_value2, r_flw_value2, l_flw_value2, r_spr_value2, l_spr_value2]

        # cartesian_limits
        self.x_max = rospy.get_param("/cartesian_limits/x_max")
        self.x_min = rospy.get_param("/cartesian_limits/x_min")
        self.y_max = rospy.get_param("/cartesian_limits/y_max")
        self.y_min = rospy.get_param("/cartesian_limits/y_min")
        self.z_max = rospy.get_param("/cartesian_limits/z_max")
        self.z_min = rospy.get_param("/cartesian_limits/z_min")

        # Fill in the Done Episode Criteria list
        self.episode_done_criteria = rospy.get_param("/episode_done_criteria")
        
        # stablishes connection with simulator
        self._gz_conn = GazeboConnection()
        self._ctrl_conn = ControllersConnection(namespace="")
        
        # Controller type for ros_control
        self._ctrl_type =  rospy.get_param("/control_type")
        self.pre_ctrl_type =  self._ctrl_type

	# Get the force and troque limit
        self.force_limit = rospy.get_param("/force_limit")
        self.torque_limit = rospy.get_param("/torque_limit")

        # We init the observations
        self.base_orientation = Quaternion()
        self.imu_link = Quaternion()
        self.door = Quaternion()
        self.quat = Quaternion()
        self.imu_link_rpy = Vector3()
        self.door_rpy = Vector3()
        self.link_state = LinkStates()
        self.wrench_stamped = WrenchStamped()
        self.joints_state = JointState()
        self.end_effector = Point() 
        self.previous_action =[]
        self.counter = 0
        self.max_rewards = 1

        # Arm/Control parameters
        self._ik_params = setups['UR5_6dof']['ik_params']
        
        # ROS msg type
        self._joint_pubisher = JointPub()
        self._joint_traj_pubisher = JointTrajPub()

        # Gym interface and action
        self.action_space = spaces.Discrete(6)
        self.observation_space = 21 #np.arange(self.get_observations().shape[0])
##        self.observation_space = 15 #np.arange(self.get_observations().shape[0])
        self.reward_range = (-np.inf, np.inf)
        self._seed()

        # Change the controller type 
        set_joint_pos_server = rospy.Service('/set_position_controller', SetBool, self._set_pos_ctrl)
        set_joint_traj_pos_server = rospy.Service('/set_trajectory_position_controller', SetBool, self._set_traj_pos_ctrl)
        set_joint_vel_server = rospy.Service('/set_velocity_controller', SetBool, self._set_vel_ctrl)
        set_joint_traj_vel_server = rospy.Service('/set_trajectory_velocity_controller', SetBool, self._set_traj_vel_ctrl)
#        set_gripper_server = rospy.Service('/set_gripper_controller', SetBool, self._set_grp_ctrl)

        self.pos_traj_controller = ['joint_state_controller',
                            'gripper_controller',
                            'pos_traj_controller']
        self.pos_controller = ["joint_state_controller",
                                "gripper_controller",
                                "ur_shoulder_pan_pos_controller",
                                "ur_shoulder_lift_pos_controller",
                                "ur_elbow_pos_controller",
                                "ur_wrist_1_pos_controller",
                                "ur_wrist_2_pos_controller",
                                "ur_wrist_3_pos_controller"]
        self.vel_traj_controller = ['joint_state_controller',
                            'gripper_controller',
                            'vel_traj_controller']
        self.vel_controller = ["joint_state_controller",
                                "gripper_controller",
                                "ur_shoulder_pan_vel_controller",
                                "ur_shoulder_lift_vel_controller",
                                "ur_elbow_vel_controller",
                                "ur_wrist_1_vel_controller",
                                "ur_wrist_2_vel_controller",
                                "ur_wrist_3_vel_controller"]

        # Helpful False
        self.stop_flag = False
        stop_trainning_server = rospy.Service('/stop_training', SetBool, self._stop_trainnig)
        start_trainning_server = rospy.Service('/start_training', SetBool, self._start_trainnig)

    def check_stop_flg(self):
        if self.stop_flag is False:
            return False
        else:
            return True

    def _start_trainnig(self, req):
        rospy.logdebug("_start_trainnig!!!!")
        self.stop_flag = False
        return SetBoolResponse(True, "_start_trainnig")

    def _stop_trainnig(self, req):
        rospy.logdebug("_stop_trainnig!!!!")
        self.stop_flag = True
        return SetBoolResponse(True, "_stop_trainnig")

    def _set_pos_ctrl(self, req):
        rospy.wait_for_service('set_position_controller')
        self._ctrl_conn.stop_controllers(self.pos_traj_controller)
        self._ctrl_conn.start_controllers(self.pos_controller)
        self._ctrl_type = 'pos'
        return SetBoolResponse(True, "_set_pos_ctrl")

    def _set_traj_pos_ctrl(self, req):
        rospy.wait_for_service('set_trajectory_position_controller')
        self._ctrl_conn.stop_controllers(self.pos_controller)
        self._ctrl_conn.start_controllers(self.pos_traj_controller)    
        self._ctrl_type = 'traj_pos'
        return SetBoolResponse(True, "_set_traj_pos_ctrl")  

    def _set_vel_ctrl(self, req):
        rospy.wait_for_service('set_velocity_controller')
        self._ctrl_conn.stop_controllers(self.vel_traj_controller)
        self._ctrl_conn.start_controllers(self.vel_controller)
        self._ctrl_type = 'vel'
        return SetBoolResponse(True, "_set_vel_ctrl")

    def _set_traj_vel_ctrl(self, req):
        rospy.wait_for_service('set_trajectory_velocity_controller')
        self._ctrl_conn.stop_controllers(self.vel_controller)
        self._ctrl_conn.start_controllers(self.vel_traj_controller)    
        self._ctrl_type = 'traj_vel'
        return SetBoolResponse(True, "_set_traj_vel_ctrl")  

    # A function to initialize the random generator
    def _seed(self, seed=None):
        self.np_random, seed = seeding.np_random(seed)
        return [seed]
        
    def link_state_callback(self, msg):
        self.link_state = msg
        self.end_effector = self.link_state.pose[7]
        self.imu_link = self.link_state.pose[5]
        self.door = self.link_state.pose[2]

    def check_all_systems_ready(self):
        """
        We check that all systems are ready
        :return:
        """
        joint_states_msg = None
        while joint_states_msg is None and not rospy.is_shutdown():
            try:
                joint_states_msg = rospy.wait_for_message("/joint_states", JointState, timeout=0.1)
                self.joints_state = joint_states_msg
                rospy.logdebug("Current joint_states READY")
            except Exception as e:
                self._ctrl_conn.start_controllers(controllers_on="joint_state_controller")                
                rospy.logdebug("Current joint_states not ready yet, retrying==>"+str(e))
        
        link_states_msg = None
        while link_states_msg is None and not rospy.is_shutdown():
            try:
                link_states_msg = rospy.wait_for_message("/gazebo/link_states", LinkStates, timeout=0.1)
                self.link_states = link_states_msg
                rospy.logdebug("Reading link_states READY")
            except Exception as e:
                rospy.logdebug("Reading link_states not ready yet, retrying==>"+str(e))

        rospy.logdebug("ALL SYSTEMS READY")

    def check_cartesian_limits(self, action):
        ee_xyz = Vector3()
        ee_xyz = self.get_xyz(action)
        if self.x_min < ee_xyz[0] and ee_xyz[0] < self.x_max and self.y_min < ee_xyz[1] and ee_xyz[1] < self.y_max and self.z_min < ee_xyz[2] and ee_xyz[2] < self.z_max:
            return True
        else:
            return False

    def get_xyz(self, q):
        """Get x,y,z coordinates 
        Args:
            q: a numpy array of joints angle positions.
        Returns:
            xyz are the x,y,z coordinates of an end-effector in a Cartesian space.
        """
        mat = ur_utils.forward(q, self._ik_params)
        xyz = mat[:3, 3]
        return xyz

    def get_current_xyz(self):
        """Get x,y,z coordinates according to currrent joint angles
        Returns:
        xyz are the x,y,z coordinates of an end-effector in a Cartesian space.
        """
        joint_states = self.joints_state
        shp_joint_ang = joint_states.position[0]
        shl_joint_ang = joint_states.position[1]
        elb_joint_ang = joint_states.position[2]
        wr1_joint_ang = joint_states.position[3]
        wr2_joint_ang = joint_states.position[4]
        wr3_joint_ang = joint_states.position[5]
        
        q = [shp_joint_ang, shl_joint_ang, elb_joint_ang, wr1_joint_ang, wr2_joint_ang, wr3_joint_ang]
        mat = ur_utils.forward(q, self._ik_params)
        xyz = mat[:3, 3]
        return xyz
            
    def get_orientation(self, q):
        """Get Euler angles 
        Args:
            q: a numpy array of joints angle positions.
        Returns:
            xyz are the x,y,z coordinates of an end-effector in a Cartesian space.
        """
        mat = ur_utils.forward(q, self._ik_params)
        orientation = mat[0:3, 0:3]
        roll = -orientation[1, 2]
        pitch = orientation[0, 2]
        yaw = -orientation[0, 1]
        
        return Vector3(roll, pitch, yaw)


    def cvt_quat_to_euler(self, quat):
        euler_rpy = Vector3()
        euler = euler_from_quaternion([self.quat.x, self.quat.y, self.quat.z, self.quat.w])

        euler_rpy.x = euler[0]
        euler_rpy.y = euler[1]
        euler_rpy.z = euler[2]
        return euler_rpy

    def init_joints_pose(self, init_pos):
        """
        We initialise the Position variable that saves the desired position where we want our
        joints to be
        :param init_pos:
        :return:
        """
        self.current_joint_pose =[]
        self.current_joint_pose = copy.deepcopy(init_pos)
#	print("[current_joint_pose]:", self.current_joint_pose, type(self.current_joint_pose))
        return self.current_joint_pose

    def get_euclidean_dist(self, p_in, p_pout):
        """
        Given a Vector3 Object, get distance from current position
        :param p_end:
        :return:
        """
        a = numpy.array((p_in.x, p_in.y, p_in.z))
        b = numpy.array((p_pout.x, p_pout.y, p_pout.z))

        distance = numpy.linalg.norm(a - b)

        return distance

    def joints_state_callback(self,msg):
        self.joints_state = msg

    def wrench_stamped_callback(self,msg):
        self.wrench_stamped = msg

    def get_observations(self):
        """
        Returns the state of the robot needed for OpenAI QLearn Algorithm
        The state will be defined by an array
        :return: observation
        """
        joint_states = self.joints_state
        self.force = self.wrench_stamped.wrench.force
        self.torque = self.wrench_stamped.wrench.torque

        shp_joint_ang = joint_states.position[2]
        shl_joint_ang = joint_states.position[1]
        elb_joint_ang = joint_states.position[0]
        wr1_joint_ang = joint_states.position[3]
        wr2_joint_ang = joint_states.position[4]
        wr3_joint_ang = joint_states.position[5]

        shp_joint_vel = joint_states.velocity[2]
        shl_joint_vel = joint_states.velocity[1]
        elb_joint_vel = joint_states.velocity[0]
        wr1_joint_vel = joint_states.velocity[3]
        wr2_joint_vel = joint_states.velocity[4]
        wr3_joint_vel = joint_states.velocity[5]

        q = [shp_joint_ang, shl_joint_ang, elb_joint_ang, wr1_joint_ang, wr2_joint_ang, wr3_joint_ang]
        eef_x, eef_y, eef_z = self.get_xyz(q)

        observation = []
#        rospy.logdebug("List of Observations==>"+str(self.observations))
        for obs_name in self.observations:
            if obs_name == "shp_joint_ang":
                observation.append(shp_joint_ang)
            elif obs_name == "shl_joint_ang":
                observation.append(shl_joint_ang)
            elif obs_name == "elb_joint_ang":
                observation.append(elb_joint_ang)
            elif obs_name == "wr1_joint_ang":
                observation.append(wr1_joint_ang)
            elif obs_name == "wr2_joint_ang":
                observation.append(wr2_joint_ang)
            elif obs_name == "wr3_joint_ang":
                observation.append(wr3_joint_ang)
            elif obs_name == "shp_joint_vel":
                observation.append(shp_joint_vel)
            elif obs_name == "shl_joint_vel":
                observation.append(shl_joint_vel)
            elif obs_name == "elb_joint_vel":
                observation.append(elb_joint_vel)
            elif obs_name == "wr1_joint_vel":
                observation.append(wr1_joint_vel)
            elif obs_name == "wr2_joint_vel":
                observation.append(wr2_joint_vel)
            elif obs_name == "wr3_joint_vel":
                observation.append(wr3_joint_vel)
            elif obs_name == "eef_x":
                observation.append(eef_x)
            elif obs_name == "eef_y":
                observation.append(eef_y)
            elif obs_name == "eef_z":
                observation.append(eef_z)
            elif obs_name == "force_x":
                observation.append(self.force.x)
            elif obs_name == "force_y":
                observation.append(self.force.y)
            elif obs_name == "force_z":
                observation.append(self.force.z)
            elif obs_name == "torque_x":
                observation.append(self.torque.x)
            elif obs_name == "torque_y":
                observation.append(self.torque.y)
            elif obs_name == "torque_z":
                observation.append(self.torque.z)
            else:
                raise NameError('Observation Asked does not exist=='+str(obs_name))

        return observation

    def clamp_to_joint_limits(self):
        """
        clamps self.current_joint_pose based on the joint limits
        self._joint_limits
        {
         "shp_max": shp_max,
         "shp_min": shp_min,
         ...
         }
        :return:
        """

        rospy.logdebug("Clamping current_joint_pose>>>" + str(self.current_joint_pose))
        shp_joint_value = self.current_joint_pose[0]
        shl_joint_value = self.current_joint_pose[1]
        elb_joint_value = self.current_joint_pose[2]
        wr1_joint_value = self.current_joint_pose[3]
        wr2_joint_value = self.current_joint_pose[4]
        wr3_joint_value = self.current_joint_pose[5]

        self.current_joint_pose[0] = max(min(shp_joint_value, self._joint_limits["shp_max"]), self._joint_limits["shp_min"])
        self.current_joint_pose[1] = max(min(shl_joint_value, self._joint_limits["shl_max"]), self._joint_limits["shl_min"])
        self.current_joint_pose[2] = max(min(elb_joint_value, self._joint_limits["elb_max"]), self._joint_limits["elb_min"])
        self.current_joint_pose[3] = max(min(wr1_joint_value, self._joint_limits["wr1_max"]), self._joint_limits["wr1_min"])
        self.current_joint_pose[4] = max(min(wr2_joint_value, self._joint_limits["wr2_max"]), self._joint_limits["wr2_min"])
        self.current_joint_pose[5] = max(min(wr3_joint_value, self._joint_limits["wr3_max"]), self._joint_limits["wr3_min"])

        rospy.logdebug("DONE Clamping current_joint_pose>>>" + str(self.current_joint_pose))

    # Resets the state of the environment and returns an initial observation.
    def reset(self):

	# Go to initial position
	self._gz_conn.unpauseSim()
        rospy.logdebug("set_init_pose init variable...>>>" + str(self.init_joint_pose0))
        init_pos0 = self.init_joints_pose(self.init_joint_pose0)
        self.arr_init_pos0 = np.array(init_pos0, dtype='float32')
        init_pos1 = self.init_joints_pose(self.init_joint_pose1)
        self.arr_init_pos1 = np.array(init_pos1, dtype='float32')
        init_g_pos1 = self.init_joints_pose(self.init_grp_pose1)
        arr_init_g_pos1 = np.array(init_g_pos1, dtype='float32')

        jointtrajpub = JointTrajPub()
        '''
        for update in range(500):
        	jointtrajpub.GrpCommand(arr_init_g_pos1)
        time.sleep(2)
        for update in range(1000):
        	jointtrajpub.jointTrajectoryCommand(self.arr_init_pos1)
        time.sleep(0.3)
        '''

        for update in range(1000):
        	jointtrajpub.jointTrajectoryCommand(self.arr_init_pos0)
                observation = self.get_observations()
        time.sleep(0.3)

        # 0st: We pause the Simulator
        rospy.logdebug("Pausing SIM...")
        self._gz_conn.pauseSim()

        # 1st: resets the simulation to initial values
        rospy.logdebug("Reset SIM...")
        self._gz_conn.resetSim()

        # 2nd: We Set the gravity to 0.0 so that we dont fall when reseting joints
        # It also UNPAUSES the simulation
        rospy.logdebug("Remove Gravity...")
        self._gz_conn.change_gravity_zero()

        # EXTRA: Reset JoinStateControlers because sim reset doesnt reset TFs, generating time problems
        rospy.logdebug("reset_ur_joint_controllers...")
        self._ctrl_conn.reset_ur_joint_controllers(self._ctrl_type)

        # 3rd: resets the robot to initial conditions
        rospy.logdebug("set_init_pose init variable...>>>" + str(self.init_joint_pose1))
        rospy.logdebug("set_init_pose init variable...>>>" + str(self.init_joint_pose2))

        # We save that position as the current joint desired position
        init_pos2 = self.init_joints_pose(self.init_joint_pose2)
        self.arr_init_pos2 = np.array(init_pos2, dtype='float32')
        after_rotate = self.init_joints_pose(self.after_rotate)
        self.arr_after_rotate = np.array(after_rotate, dtype='float32')
        after_pull = self.init_joints_pose(self.after_pull)
        self.arr_after_pull = np.array(after_pull, dtype='float32')

        init_g_pos2 = self.init_joints_pose(self.init_grp_pose2)
        arr_init_g_pos2 = np.array(init_g_pos2, dtype='float32')

        # 4th: We Set the init pose to the jump topic so that the jump control can update
        # We check the jump publisher has connection

        if self._ctrl_type == 'traj_pos':
            self._joint_traj_pubisher.check_publishers_connection()
        elif self._ctrl_type == 'pos':
            self._joint_pubisher.check_publishers_connection()
        elif self._ctrl_type == 'traj_vel':
            self._joint_traj_pubisher.check_publishers_connection()
        elif self._ctrl_type == 'vel':
            self._joint_pubisher.check_publishers_connection()
        else:
            rospy.logwarn("Controller type is wrong!!!!")
        
        # 5th: Check all subscribers work.
        # Get the state of the Robot defined by its RPY orientation, distance from
        # desired point, contact force and JointState of the three joints
        rospy.logdebug("check_all_systems_ready...")
        self.check_all_systems_ready()

        # 6th: We restore the gravity to original
        rospy.logdebug("Restore Gravity...")
        self._gz_conn.adjust_gravity()

        # 7th: pauses simulation
        rospy.logdebug("Pause SIM...")
        self._gz_conn.pauseSim()

        # 8th: Get the State Discrete Stringuified version of the observations
        rospy.logdebug("get_observations...")
       	observation = self.get_observations()

        return observation

    def _act(self, action):
        if self._ctrl_type == 'traj_pos':
            self.pre_ctrl_type = 'traj_pos'
            self._joint_traj_pubisher.jointTrajectoryCommand(action)
        elif self._ctrl_type == 'pos':
            self.pre_ctrl_type = 'pos'
            self._joint_pubisher.move_joints(action)
        elif self._ctrl_type == 'traj_vel':
            self.pre_ctrl_type = 'traj_vel'
            self._joint_traj_pubisher.jointTrajectoryCommand(action)
        elif self._ctrl_type == 'vel':
            self.pre_ctrl_type = 'vel'
            self._joint_pubisher.move_joints(action)
        else:
            self._joint_pubisher.move_joints(action)
        
    def training_ok(self):
        rate = rospy.Rate(1)
        while self.check_stop_flg() is True:                  
            rospy.logdebug("stop_flag is ON!!!!")
            self._gz_conn.unpauseSim()

            if self.check_stop_flg() is False:
                break 
            rate.sleep()
                
    def step(self, action):
        '''
        ('action: ', array([ 0.,  0. , -0., -0., -0. , 0. ], dtype=float32))        
        '''
        rospy.logdebug("UR step func")	# define the logger
        self.training_ok()

        # Given the action selected by the learning algorithm,
        # we perform the corresponding movement of the robot
        # Act
        self._gz_conn.unpauseSim()

        action = action + self.arr_init_pos0
        if self.check_cartesian_limits(action) is True:
            self._act(action)
        else:
            print("Doesn't act")

        # Then we send the command to the robot and let it go for running_step seconds
        time.sleep(self.running_step)
        self._gz_conn.pauseSim()

        # We now process the latest data saved in the class state to calculate
        # the state and the rewards. This way we guarantee that they work
        # with the same exact data.
        # Generate State based on observations
        observation = self.get_observations()

        # finally we get an evaluation based on what happened in the sim
        reward = self.compute_dist_rewards()
        done = self.check_done()

        return observation, reward, done, {}

    def compute_dist_rewards(self):
	return self.end_effector.position.z # for standup

    def check_done(self):
        if self.end_effector.position.z > 3: # for standup
            print("done")
            return True
        else :
        	return False
