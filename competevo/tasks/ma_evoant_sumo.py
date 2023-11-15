from typing import Tuple
import attr
import numpy as np
import os
import math
import torch
import random

from isaacgym import gymtorch
from isaacgym import gymapi
from isaacgym.gymtorch import *
# from torch.tensor import Tensor

from competevo.utils.torch_jit_utils import *
from competevo.robot.xml_robot import Robot
from competevo.robot.robo_utils import *

from .base.ma_evo_vec_task import MA_Evo_VecTask


# todo critic_state full obs
class MA_EvoAnt_Sumo(MA_Evo_VecTask):

    def __init__(self, cfg, sim_device, rl_device, graphics_device_id, headless, virtual_screen_capture, force_render):

        self.cfg = cfg
        self.randomization_params = self.cfg["task"]["randomization_params"]
        self.randomize = self.cfg["task"]["randomize"]

        self.max_episode_length = self.cfg["env"]["episodeLength"]

        self.termination_height = self.cfg["env"]["terminationHeight"]
        self.borderline_space = cfg["env"]["borderlineSpace"]
        self.plane_static_friction = self.cfg["env"]["plane"]["staticFriction"]
        self.plane_dynamic_friction = self.cfg["env"]["plane"]["dynamicFriction"]
        self.plane_restitution = self.cfg["env"]["plane"]["restitution"]
        self.action_scale = self.cfg["env"]["control"]["actionScale"]
        self.joints_at_limit_cost_scale = self.cfg["env"]["jointsAtLimitCost"]
        self.dof_vel_scale = self.cfg["env"]["dofVelocityScale"]

        self.draw_penalty_scale = -1000
        self.win_reward_scale = 2000
        self.move_to_op_reward_scale = 1.
        self.stay_in_center_reward_scale = 0.2
        self.action_cost_scale = -0.000025
        self.push_scale = 1.
        self.dense_reward_scale = 1.
        self.hp_decay_scale = 1.

        self.Kp = self.cfg["env"]["control"]["stiffness"]
        self.Kd = self.cfg["env"]["control"]["damping"]

        # see func: compute_ant_observations() for details
        
        # define transform2act evo obs, action dimensions
        # robot config
        robo_config = self.cfg['robot']

        # design options
        self.robot_param_scale = robo_config['robot_param_scale']
        self.skel_transform_nsteps = robo_config["skel_transform_nsteps"]
        self.clip_qvel = robo_config["obs_specs"]["clip_qvel"]
        self.use_projected_params = robo_config["obs_specs"]["use_projected_params"]
        self.abs_design = robo_config["obs_specs"]["abs_design"]
        self.use_body_ind = robo_config["obs_specs"]["use_body_ind"]

        self.sim_specs = robo_config["obs_specs"]["sim"]
        self.attr_specs = robo_config["obs_specs"]["attr"]

        # define robots: 2
        self.base_ant_path = f'/home/kjaebye/ws/competevo/assets/mjcf/ant.xml'
        self.robots = {}
        # xml tmp dir
        self.out_dir = 'out/evo_ant'
        os.makedirs(self.out_dir, exist_ok=True)
        name = "evo_ant"
        name_op = "evo_ant_op"
        self.robot = Robot(robo_config, self.base_ant_path, is_xml_str=False)
        self.robot_op = Robot(robo_config, self.base_ant_path, is_xml_str=False)

        # ant
        self.design_ref_params = get_attr_design(self.robot)
        self.design_cur_params = get_attr_design(self.robot)
        self.design_param_names = self.robot.get_params(get_name=True)
        if robo_config["obs_specs"].get('fc_graph', False):
            self.edges = get_graph_fc_edges(len(self.robot.bodies))
        else:
            self.edges = self.robot.get_gnn_edges()
        self.num_nodes = len(list(self.robot.bodies))
        # ant op
        self.design_ref_params_op = get_attr_design(self.robot_op)
        self.design_cur_params_op = get_attr_design(self.robot_op)
        self.design_param_names_op = self.robot_op.get_params(get_name=True)
        if robo_config["obs_specs"].get('fc_graph', False):
            self.edges_op = get_graph_fc_edges(len(self.robot_op.bodies))
        else:
            self.edges_op = self.robot_op.get_gnn_edges()
        self.num_nodes_op = len(list(self.robot_op.bodies))
        
        # constant variables
        self.attr_design_dim = 5
        self.attr_fixed_dim = 4
        self.gym_obs_dim = ... # 13?
        self.index_base = 5

        # actions dim: (num_nodes, action_dim)
        ###############################################################
        # action for every node:
        #    control_action      attr_action        skel_action 
        #   #-------------##--------------------##---------------#
        self.skel_num_action = 3 if robo_config["enable_remove"] else 2 # it is not an action dimension
        self.attr_action_dim = self.attr_design_dim
        self.control_action_dim = 1 
        self.action_dim = self.control_action_dim + self.attr_action_dim + 1
        
        # states dim and construction:
        # [obses, edges, stage, num_nodes, body_index]

        # obses dim (num_nodes, obs_dim)
        ###############################################################
        # observation for every node:
        #      attr_fixed            gym_obs          attr_design 
        #   #---------------##--------------------##---------------#
        self.skel_state_dim = self.attr_fixed_dim + self.attr_design_dim
        self.attr_state_dim = self.attr_fixed_dim + self.attr_design_dim
        self.obs_dim = self.attr_fixed_dim + self.gym_obs_dim + self.attr_design_dim

        self.use_central_value = False

        super().__init__(config=self.cfg, sim_device=sim_device, rl_device=rl_device,
                         graphics_device_id=graphics_device_id,
                         headless=headless, virtual_screen_capture=virtual_screen_capture,
                         force_render=force_render)

    def step(self, all_actions: dict):
        """ all action shape: (num_envs, num_nodes + num_nodes_op, action_dim)
        """
        assert all_actions.shape[1] == self.num_nodes + self.num_nodes_op
        self.cur_t += 1
        actions = all_actions[:, :self.num_nodes, :]
        actions_op = all_actions[:, self.num_nodes:, :]
        # skeleton transform stage
        if self.stage == 'skel_trans':
            # check data in a tensor are definitely equal along the first dimension
            def check_equal(tensor):
                return (tensor[0] == tensor).all()
            assert check_equal(actions) and check_equal(actions_op) is True, \
                "Skeleton transform stage needs all agents to have the same actions!"
            # ant
            skel_a = actions[0][:, :-1]
            apply_skel_action(self.robot, skel_a)
            self.design_cur_params = get_attr_design(self.robot)
            # ant op
            skel_a_op = actions_op[0][:, :-1]
            apply_skel_action(self.robot_op, skel_a_op)
            self.design_cur_params_op = get_attr_design(self.robot_op)

            # transit to attribute transform stage
            if self.cur_t == self.skel_transform_nsteps:
                self.transit_attribute_transform()
            self.compute_observations()
            self.compute_rewards()
            return
        
        # attribute transform stage
        elif self.stage == 'attr_trans':
            # check data in a tensor are definitely equal along the first dimension
            def check_equal(tensor):
                return (tensor[0] == tensor).all()
            assert check_equal(actions) and check_equal(actions_op) is True, \
                "Attribute transform stage needs all agents to have the same actions!"
            
            # ant
            design_a = actions[0][:, self.control_action_dim:-1]
            if self.abs_design:
                design_params = design_a * self.robot_param_scale
            else:
                design_params = self.design_cur_params \
                                + design_a * self.robot_param_scale
            set_design_params(self.robot, design_params, self.out_dir, "evo_ant")
            if self.use_projected_params:
                self.design_cur_params = get_attr_design(self.robot)
            else:
                self.design_cur_params = design_params.copy()
            # ant op
            design_a_op = actions_op[0][:, self.control_action_dim:-1]
            if self.abs_design:
                design_params_op = design_a_op * self.robot_param_scale
            else:
                design_params_op = self.design_cur_params_op \
                                   + design_a_op * self.robot_param_scale
            set_design_params(self.robot_op, design_params_op, self.out_dir, "evo_ant_op")
            if self.use_projected_params:
                self.design_cur_params_op = get_attr_design(self.robot_op)
            else:
                self.design_cur_params_op = design_params_op.copy()

            # transit to execution stage
            self.transit_execution()

            self.compute_observations()
            self.compute_rewards()

            ###############################################################################
            ######## Create IsaacGym sim and envs for Execution ####################
            ############################################################################### 
            self.create_sim() # create sim and envs
            self.gym.prepare_sim(self.sim)
            self.sim_initialized = True
            self.set_viewer()
            self.allocate_buffers() # init buffers

            # add border, add camera
            self.add_border_cam()
            # init gym state
            self.gym_state_init()
            self.gym_reset()

        # execution stage
        else:
            # check zero becuase in execution stage, only control action is computated
            assert torch.all(all_actions[:, :, self.control_action_dim:] == 0)
            self.control_nsteps += 1
            self.gym_step(all_actions)
    
    def gym_reset(self) -> torch.Tensor:
        """Reset all environments.
        """
        env_ids = to_torch(np.arange(self.num_envs), device=self.device, dtype=torch.long)
        self.reset_idx(env_ids)
        self.pos_before = self.obs_buf[:self.num_envs, :2].clone()
        # reset buffers
        self.allocate_buffers()

    def reset_idx(self, env_ids):
        # print('reset.....', env_ids)
        # Randomization can happen only at reset time, since it can reset actor positions on GPU
        if self.randomize:
            self.apply_randomizations(self.randomization_params)

        # ant
        positions = torch_rand_float(-0.2, 0.2, (len(env_ids), self.num_dof), device=self.device)
        velocities = torch_rand_float(-0.1, 0.1, (len(env_ids), self.num_dof), device=self.device)

        self.dof_pos[env_ids] = tensor_clamp(self.initial_dof_pos[env_ids] + positions, self.dof_limits_lower,
                                             self.dof_limits_upper)
        self.dof_vel[env_ids] = velocities
        # ant op
        positions_op = torch_rand_float(-0.2, 0.2, (len(env_ids), self.num_dof_op), device=self.device)
        velocities_op = torch_rand_float(-0.1, 0.1, (len(env_ids), self.num_dof_op), device=self.device)

        self.dof_pos_op[env_ids] = tensor_clamp(self.initial_dof_pos[env_ids] + positions_op, self.dof_limits_lower_op,
                                                self.dof_limits_upper_op)
        self.dof_vel_op[env_ids] = velocities_op

        env_ids_int32 = (torch.cat((self.actor_indices[env_ids], self.actor_indices_op[env_ids]))).to(dtype=torch.int32)
        agent_env_ids = expand_env_ids(env_ids, 2)

        rand_angle = torch.rand((len(env_ids),), device=self.device) * torch.pi * 2

        rand_pos = torch.ones((len(agent_env_ids), 2), device=self.device) * (
                self.borderline_space * torch.ones((len(agent_env_ids), 2), device=self.device) - torch.rand(
            (len(agent_env_ids), 2), device=self.device) * 2)
        rand_pos[0::2, 0] *= torch.cos(rand_angle)
        rand_pos[0::2, 1] *= torch.sin(rand_angle)
        rand_pos[1::2, 0] *= torch.cos(rand_angle + torch.pi)
        rand_pos[1::2, 1] *= torch.sin(rand_angle + torch.pi)
        rand_floats = torch_rand_float(-1.0, 1.0, (len(agent_env_ids), 3), device=self.device)
        rand_rotation = quat_from_angle_axis(rand_floats[:, 1] * np.pi, self.z_unit_tensor[agent_env_ids])
        rand_rotation2 = quat_from_angle_axis(rand_floats[:, 2] * np.pi, self.z_unit_tensor[agent_env_ids])
        self.root_states[agent_env_ids] = self.initial_root_states[agent_env_ids]
        self.root_states[agent_env_ids, :2] = rand_pos
        self.root_states[agent_env_ids[1::2], 3:7] = rand_rotation[1::2]
        self.root_states[agent_env_ids[0::2], 3:7] = rand_rotation2[0::2]
        self.gym.set_actor_root_state_tensor_indexed(self.sim,
                                                     gymtorch.unwrap_tensor(self.root_states),
                                                     gymtorch.unwrap_tensor(env_ids_int32), len(env_ids_int32))

        self.gym.set_dof_state_tensor_indexed(self.sim,
                                              gymtorch.unwrap_tensor(self.dof_state),
                                              gymtorch.unwrap_tensor(env_ids_int32), len(env_ids_int32))
        self.pos_before = self.root_states[0::2, :2].clone()

        self.progress_buf[env_ids] = 0
        self.reset_buf[env_ids] = 0

    def transit_attribute_transform(self):
        self.stage = 'attribute_transform'

    def transit_execution(self):
        self.stage = 'execution'
        self.control_nsteps = 0
    
    def add_border_cam(self):
        if self.viewer is not None:
            for env in self.envs:
                self._add_circle_borderline(env)
            cam_pos = gymapi.Vec3(15.0, 0.0, 3.0)
            cam_target = gymapi.Vec3(10.0, 0.0, 0.0)
            self.gym.viewer_camera_look_at(self.viewer, None, cam_pos, cam_target)

    def gym_state_init(self):
        # get gym GPU state tensors
        actor_root_state = self.gym.acquire_actor_root_state_tensor(self.sim) # all actors root state
        dof_state_tensor = self.gym.acquire_dof_state_tensor(self.sim) # all actors dof state

        self.gym.refresh_dof_state_tensor(self.sim)
        self.gym.refresh_actor_root_state_tensor(self.sim)

        self.root_states = gymtorch.wrap_tensor(actor_root_state)
        print(f'root_states:{self.root_states.shape}')
        self.initial_root_states = self.root_states.clone()
        self.initial_root_states[:, 7:13] = 0  # set lin_vel and ang_vel to 0

        # create some wrapper tensors for different slices
        self.dof_state = gymtorch.wrap_tensor(dof_state_tensor)
        print(f"dof states shape: {self.dof_state.shape}")
        self.dof_pos = self.dof_state.view(self.num_envs, -1, 2)[:, :self.num_dof, 0]
        self.dof_pos_op = self.dof_state.view(self.num_envs, -1, 2)[:, self.num_dof:, 0]
        self.dof_vel = self.dof_state.view(self.num_envs, -1, 2)[:, :self.num_dof, 1]
        self.dof_vel_op = self.dof_state.view(self.num_envs, -1, 2)[:, self.num_dof:, 1]

        self.initial_dof_pos = torch.zeros_like(self.dof_pos, device=self.device, dtype=torch.float)
        zero_tensor = torch.tensor([0.0], device=self.device)
        self.initial_dof_pos = torch.where(self.dof_limits_lower > zero_tensor, self.dof_limits_lower,
                                           torch.where(self.dof_limits_upper < zero_tensor, self.dof_limits_upper,
                                                       self.initial_dof_pos))
        self.initial_dof_vel = torch.zeros_like(self.dof_vel, device=self.device, dtype=torch.float)
        self.dt = self.cfg["sim"]["dt"]

        torques = self.gym.acquire_dof_force_tensor(self.sim)
        self.torques = gymtorch.wrap_tensor(torques).view(self.num_envs, self.num_dof + self.num_dof_op)

        self.x_unit_tensor = to_torch([1, 0, 0], dtype=torch.float, device=self.device).repeat((2 * self.num_envs, 1))
        self.y_unit_tensor = to_torch([0, 1, 0], dtype=torch.float, device=self.device).repeat((2 * self.num_envs, 1))
        self.z_unit_tensor = to_torch([0, 0, 1], dtype=torch.float, device=self.device).repeat((2 * self.num_envs, 1))

        self.hp = torch.ones((self.num_envs,), device=self.device, dtype=torch.float32) * 100
        self.hp_op = torch.ones((self.num_envs,), device=self.device, dtype=torch.float32) * 100

    def allocate_buffers(self):
        """Allocate the observation, states, etc. buffers.

        These are what is used to set observations and states in the environment classes which
        inherit from this one, and are read in `step` and other related functions.

        """
        # allocate buffers
        # transform2act state data
        self.obs_buf = torch.zeros(
            (self.num_envs, self.num_nodes + self.num_nodes_op, self.obs_dim), device=self.device, dtype=torch.float)
        self.edge_buf = torch.zeros(
            (self.num_envs, 2, (self.num_nodes-1)*2 + (self.num_nodes_op-1)*2), device=self.device, dtype=torch.float)
        self.stage_buf = torch.ones(
            (self.num_envs, 1), device=self.device, dtype=torch.int) * 2 # state flag == 2 means execution stage
        self.num_nodes_buf = torch.zeros(
            (self.num_envs, 2), device=self.device, dtype=torch.int)
        self.body_ind = torch.zeros(
            (self.num_envs, self.num_nodes + self.num_nodes_op), device=self.device, dtype=torch.float)
        
        self.rew_buf = torch.zeros(
            self.num_envs * self.num_agents, device=self.device, dtype=torch.float)
        self.reset_buf = torch.ones(
            self.num_envs * self.num_agents, device=self.device, dtype=torch.long)
        self.timeout_buf = torch.zeros(
            self.num_envs * self.num_agents, device=self.device, dtype=torch.long)
        self.progress_buf = torch.zeros(
            self.num_envs * self.num_agents, device=self.device, dtype=torch.long)
        self.randomize_buf = torch.zeros(
            self.num_envs * self.num_agents, device=self.device, dtype=torch.long)
        self.extras = {}


    def create_sim(self):
        self.up_axis_idx = self.set_sim_params_up_axis(self.sim_params, 'z')
        self.sim = super().create_sim(self.device_id, self.graphics_device_id, self.physics_engine, self.sim_params)

        self._create_ground_plane()
        print(f'num envs {self.num_envs} env spacing {self.cfg["env"]["envSpacing"]}')
        self._create_envs(self.cfg["env"]['envSpacing'], int(np.sqrt(self.num_envs)))

        # If randomizing, apply once immediately on startup before the fist sim step
        if self.randomize:
            self.apply_randomizations(self.randomization_params)

    def _create_ground_plane(self):
        plane_params = gymapi.PlaneParams()
        plane_params.normal = gymapi.Vec3(0.0, 0.0, 1.0)
        plane_params.static_friction = self.plane_static_friction
        plane_params.dynamic_friction = self.plane_dynamic_friction
        self.gym.add_ground(self.sim, plane_params)

    def _create_envs(self, spacing, num_per_row):
        lower = gymapi.Vec3(-spacing, -spacing, 0.0)
        upper = gymapi.Vec3(spacing, spacing, spacing)

        asset_options = gymapi.AssetOptions()
        # Note - DOF mode is set in the MJCF file and loaded by Isaac Gym
        asset_options.default_dof_drive_mode = gymapi.DOF_MODE_NONE
        asset_options.angular_damping = 0.0

        # load assets
        name = "evo_ant"
        name_op = "evo_ant_op"
        file_name = name + ".xml"
        file_name_op = name_op + ".xml"
        ant_asset = self.gym.load_mjcf(self.sim, self.out_dir, file_name, asset_options)
        ant_asset_op = self.gym.load_mjcf(self.sim, self.out_dir, file_name_op, asset_options)

        # create envs and actors
        # set agent and opponent start pose
        box_pose = gymapi.Transform()
        box_pose.p = gymapi.Vec3(0, 0, 0)
        start_pose = gymapi.Transform()
        start_pose.p = gymapi.Vec3(-self.borderline_space + 1, -self.borderline_space + 1, 1.)
        start_pose_op = gymapi.Transform()
        start_pose_op.p = gymapi.Vec3(self.borderline_space - 1, self.borderline_space - 1, 1.)

        print(start_pose.p, start_pose_op.p)
        self.start_rotation = torch.tensor([start_pose.r.x, start_pose.r.y, start_pose.r.z, start_pose.r.w],
                                           device=self.device)

        self.ant_handles = []
        self.actor_indices = []
        self.actor_handles_op = []
        self.actor_indices_op = []

        self.envs = []
        self.pos_before = torch.zeros(2, device=self.device)

        self.dof_limits_lower = []
        self.dof_limits_upper = []
        self.dof_limits_lower_op = []
        self.dof_limits_upper_op = []

        for i in range(self.num_envs):
            # create env instance
            env_ptr = self.gym.create_env(
                self.sim, lower, upper, num_per_row
            )
            name = f"evo_ant_{i}"
            name_op = f"evo_ant_op_{i}"

            #------------------------- set ant props -----------------------#
            ant_handle = self.gym.create_actor(env_ptr, ant_asset, start_pose, name, i, -1, 0)
            actor_index = self.gym.get_actor_index(env_ptr, ant_handle, gymapi.DOMAIN_SIM)
            # set def_props
            dof_props = self.gym.get_actor_dof_properties(env_ptr, ant_handle)
            self.num_dof = self.gym.get_actor_dof_count(env_ptr, ant_handle)
            self.num_bodies = self.gym.get_actor_rigid_body_count(env_ptr, ant_handle)  # num_dof + 1(torso)
            assert self.num_bodies == self.num_nodes
            for i in range(self.num_dof):
                dof_props['driveMode'][i] = gymapi.DOF_MODE_POS
                dof_props['stiffness'][i] = self.Kp
                dof_props['damping'][i] = self.Kd
            for j in range(self.num_dof):
                if dof_props['lower'][j] > dof_props['upper'][j]:
                    self.dof_limits_lower.append(dof_props['upper'][j])
                    self.dof_limits_upper.append(dof_props['lower'][j])
                else:
                    self.dof_limits_lower.append(dof_props['lower'][j])
                    self.dof_limits_upper.append(dof_props['upper'][j])

            self.gym.set_actor_dof_properties(env_ptr, ant_handle, dof_props)
            self.actor_indices.append(actor_index)
            self.gym.enable_actor_dof_force_sensors(env_ptr, ant_handle)
            # set color
            for j in range(self.num_bodies):
                self.gym.set_rigid_body_color(
                    env_ptr, ant_handle, j, gymapi.MESH_VISUAL, gymapi.Vec3(0.71, 0.49, 0.01))

            #------------------------- set ant_op props -----------------------#
            ant_handle_op = self.gym.create_actor(env_ptr, ant_asset_op, start_pose_op, name_op, i, -1, 0)
            actor_index_op = self.gym.get_actor_index(env_ptr, ant_handle_op, gymapi.DOMAIN_SIM)
            # set def_props
            dof_props_op = self.gym.get_actor_dof_properties(env_ptr, ant_handle_op)
            self.num_dof_op = self.gym.get_actor_dof_count(env_ptr, ant_handle_op)
            self.num_bodies_op = self.gym.get_actor_rigid_body_count(env_ptr, ant_handle_op)  # num_dof + 1(torso)
            assert self.num_bodies_op == self.num_nodes_op
            for i in range(self.num_dof_op):
                dof_props_op['driveMode'][i] = gymapi.DOF_MODE_POS
                dof_props_op['stiffness'][i] = self.Kp
                dof_props_op['damping'][i] = self.Kd
            for j in range(self.num_dof_op):
                if dof_props_op['lower'][j] > dof_props_op['upper'][j]:
                    self.dof_limits_lower_op.append(dof_props_op['upper'][j])
                    self.dof_limits_upper_op.append(dof_props_op['lower'][j])
                else:
                    self.dof_limits_lower_op.append(dof_props_op['lower'][j])
                    self.dof_limits_upper_op.append(dof_props_op['upper'][j])

            self.gym.set_actor_dof_properties(env_ptr, ant_handle_op, dof_props_op)
            self.actor_indices_op.append(actor_index_op)
            self.gym.enable_actor_dof_force_sensors(env_ptr, ant_handle_op)
            # set color
            for j in range(self.num_bodies_op):
                self.gym.set_rigid_body_color(
                    env_ptr, ant_handle_op, j, gymapi.MESH_VISUAL, gymapi.Vec3(0.15, 0.21, 0.42))

            self.envs.append(env_ptr)
            self.ant_handles.append(ant_handle)
            self.actor_handles_op.append(ant_handle_op)

        self.dof_limits_lower = to_torch(self.dof_limits_lower, device=self.device)
        self.dof_limits_lower_op = to_torch(self.dof_limits_lower_op, device=self.device)
        self.dof_limits_upper = to_torch(self.dof_limits_upper, device=self.device)
        self.dof_limits_upper_op = to_torch(self.dof_limits_upper_op, device=self.device)
        self.actor_indices = to_torch(self.actor_indices, dtype=torch.long, device=self.device)
        self.actor_indices_op = to_torch(self.actor_indices_op, dtype=torch.long, device=self.device)

    def pre_physics_step(self, actions):
        # actions.shape = [num_envs, num_dof + num_dof_op, num_actions]
        self.actions = actions.clone().to(self.device)
        targets = self.actions

        self.gym.set_dof_position_target_tensor(self.sim, gymtorch.unwrap_tensor(targets))

    def post_physics_step(self):
        """
            IsaacGym post step.
        """
        self.progress_buf += 1
        self.randomize_buf += 1

        self.compute_observations()
        self.compute_reward(self.actions)
        self.pos_before = self.obs_buf[:self.num_envs, :2].clone()

    def compute_observations(self, actions: None):
        """
            Calculate ant observations.
        """
        if self.stage == "skel_trans":
            assert actions is not None, "Skeleton transform needs actions to get obs, edge, node, and body_ind infos!"
            # agent
            self.obs_buf[:self.num_envs] = ...
            self.edge_buf[:self.num_envs] = ...
            self.stage_buf[:self.num_envs] = 0 # 0 for skel_trans
            self.num_nodes_buf[:self.num_envs] = ...
            self.body_ind[:self.num_envs] = ...
            # agent opponent
            self.obs_buf[self.num_envs:] = ...
            self.edge_buf[self.num_envs:] = ...
            self.stage_buf[self.num_envs:] = 0 # 0 for skel_trans
            self.num_nodes_buf[self.num_envs:] = ...
            self.body_ind[self.num_envs:] = ...
        elif self.stage == "attr_trans":
            assert actions is not None, "Attribute transform needs actions to get obs, edge, node, and body_ind infos!"
            # agent
            self.obs_buf[:self.num_envs] = ...
            self.edge_buf[:self.num_envs] = ...
            self.stage_buf[:self.num_envs] = 0 # 0 for skel_trans
            self.num_nodes_buf[:self.num_envs] = ...
            self.body_ind[:self.num_envs] = ...
            # agent opponent
            self.obs_buf[self.num_envs:] = ...
            self.edge_buf[self.num_envs:] = ...
            self.stage_buf[self.num_envs:] = 0 # 0 for skel_trans
            self.num_nodes_buf[self.num_envs:] = ...
            self.body_ind[self.num_envs:] = ...
        else: # execution stage
            assert self.sim_initialized is True
            self.gym.refresh_dof_state_tensor(self.sim)
            self.gym.refresh_actor_root_state_tensor(self.sim)
            self.gym.refresh_force_sensor_tensor(self.sim)
            self.gym.refresh_dof_force_tensor(self.sim)
            self.obs_buf[:self.num_envs] = \
                compute_ant_observations(
                    self.root_states[0::2],
                    self.root_states[1::2],
                    self.dof_pos,
                    self.dof_vel,
                    self.dof_limits_lower,
                    self.dof_limits_upper,
                    self.dof_vel_scale,
                    self.termination_height
                )

            self.obs_buf[self.num_envs:] = compute_ant_observations(
                self.root_states[1::2],
                self.root_states[0::2],
                self.dof_pos_op,
                self.dof_vel_op,
                self.dof_limits_lower,
                self.dof_limits_upper,
                self.dof_vel_scale,
                self.termination_height
            )





















#####################################################################
###=========================jit functions=========================###
#####################################################################


@torch.jit.script
def expand_env_ids(env_ids, n_agents):
    # type: (Tensor, int) -> Tensor
    device = env_ids.device
    agent_env_ids = torch.zeros((n_agents * len(env_ids)), device=device, dtype=torch.long)
    for idx in range(n_agents):
        agent_env_ids[idx::n_agents] = env_ids * n_agents + idx
    return agent_env_ids


@torch.jit.script
def compute_move_reward(
        pos,
        pos_before,
        target,
        dt,
        move_to_op_reward_scale
):
    # type: (Tensor,Tensor,Tensor,float,float) -> Tensor
    move_vec = (pos - pos_before) / dt
    direction = target - pos_before
    direction = torch.div(direction, torch.linalg.norm(direction, dim=-1).view(-1, 1))
    s = torch.sum(move_vec * direction, dim=-1)
    return torch.maximum(s, torch.zeros_like(s)) * move_to_op_reward_scale


@torch.jit.script
def compute_ant_reward(
        obs_buf,
        obs_buf_op,
        reset_buf,
        progress_buf,
        pos_before,
        torques,
        hp,
        hp_op,
        termination_height,
        max_episode_length,
        borderline_space,
        draw_penalty_scale,
        win_reward_scale,
        move_to_op_reward_scale,
        stay_in_center_reward_scale,
        action_cost_scale,
        push_scale,
        joints_at_limit_cost_scale,
        dense_reward_scale,
        hp_decay_scale,
        dt,
):
    # type: (Tensor, Tensor, Tensor, Tensor,Tensor,Tensor,Tensor,Tensor,float, float,float, float,float,float,float,float,float,float,float,float,float) -> Tuple[Tensor, Tensor,Tensor,Tensor,Tensor,Tensor,Tensor]

    hp -= (obs_buf[:, 2] < termination_height) * hp_decay_scale
    hp_op -= (obs_buf_op[:, 2] < termination_height) * hp_decay_scale
    is_out = torch.sum(torch.square(obs_buf[:, 0:2]), dim=-1) >= borderline_space ** 2
    is_out_op = torch.sum(torch.square(obs_buf_op[:, 0:2]), dim=-1) >= borderline_space ** 2
    is_out = is_out | (hp <= 0)
    is_out_op = is_out_op | (hp_op <= 0)
    # reset agents
    tmp_ones = torch.ones_like(reset_buf)
    reset = torch.where(is_out, tmp_ones, reset_buf)
    reset = torch.where(is_out_op, tmp_ones, reset)
    reset = torch.where(progress_buf >= max_episode_length - 1, tmp_ones, reset)

    hp = torch.where(reset > 0, tmp_ones * 100., hp)
    hp_op = torch.where(reset > 0, tmp_ones * 100., hp_op)

    win_reward = win_reward_scale * is_out_op
    lose_penalty = -win_reward_scale * is_out
    draw_penalty = torch.where(progress_buf >= max_episode_length - 1, tmp_ones * draw_penalty_scale,
                               torch.zeros_like(reset, dtype=torch.float))
    move_reward = compute_move_reward(obs_buf[:, 0:2], pos_before,
                                      obs_buf_op[:, 0:2], dt,
                                      move_to_op_reward_scale)
    # stay_in_center_reward = stay_in_center_reward_scale * torch.exp(-torch.linalg.norm(obs_buf[:, :2], dim=-1))
    dof_at_limit_cost = torch.sum(obs_buf[:, 13:21] > 0.99, dim=-1) * joints_at_limit_cost_scale
    push_reward = -push_scale * torch.exp(-torch.linalg.norm(obs_buf_op[:, :2], dim=-1))
    action_cost_penalty = torch.sum(torch.square(torques), dim=1) * action_cost_scale
    not_move_penalty = -10 * torch.exp(-torch.sum(torch.abs(torques), dim=1))
    dense_reward = move_reward + dof_at_limit_cost + push_reward + action_cost_penalty + not_move_penalty
    total_reward = win_reward + lose_penalty + draw_penalty + dense_reward * dense_reward_scale

    return total_reward, reset, hp, hp_op, is_out_op, is_out, progress_buf >= max_episode_length - 1


@torch.jit.script
def compute_ant_observations(
        root_states,
        root_states_op,
        dof_pos,
        dof_vel,
        dof_limits_lower,
        dof_limits_upper,
        dof_vel_scale,
        termination_height
):
    # type: (Tensor,Tensor,Tensor,Tensor,Tensor,Tensor,float,float)->Tensor
    dof_pos_scaled = unscale(dof_pos, dof_limits_lower, dof_limits_upper)
    obs = torch.cat(
        (root_states[:, :13], dof_pos_scaled, dof_vel * dof_vel_scale, root_states_op[:, :7],
         root_states[:, :2] - root_states_op[:, :2], torch.unsqueeze(root_states[:, 2] < termination_height, -1),
         torch.unsqueeze(root_states_op[:, 2] < termination_height, -1)), dim=-1)

    return obs


@torch.jit.script
def randomize_rotation(rand0, rand1, x_unit_tensor, y_unit_tensor):
    return quat_mul(quat_from_angle_axis(rand0 * np.pi, x_unit_tensor),
                    quat_from_angle_axis(rand1 * np.pi, y_unit_tensor))