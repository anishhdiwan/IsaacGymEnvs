import gym
from gym import spaces

import collections
import numpy as np
import pygame
import pymunk
import pymunk.pygame_util
from pymunk.vec2d import Vec2d
import shapely.geometry as sg
import cv2
import skimage.transform as st

# Importing from the file path
import sys
import os
PYMUNK_OVERRIDE_PATH = os.path.abspath(os.path.dirname(__file__))
sys.path.append(PYMUNK_OVERRIDE_PATH)
from pymunk_override import DrawOptions


def pymunk_to_shapely(body, shapes):
    geoms = list()
    for shape in shapes:
        if isinstance(shape, pymunk.shapes.Poly):
            verts = [body.local_to_world(v) for v in shape.get_vertices()]
            verts += [verts[0]]
            geoms.append(sg.Polygon(verts))
        else:
            raise RuntimeError(f'Unsupported shape type {type(shape)}')
    geom = sg.MultiPolygon(geoms)
    return geom


def unnormalise_action(action, window_size):
    """Unnormalise an input action from being in the range of Box([-1,-1], [1,1]) to the range Box([0,0], [window_size, window_size])

    Given,
    [r_min, r_max] = [-1,1] = data range
    [t_min, t_max] = [0, window_size] = target range
    x in data range

    x_in_target_range = t_min + (x - r_min)*(t_max - t_min)/(r_max - r_min) 
    https://stats.stackexchange.com/questions/281162/scale-a-number-between-a-range

    Args:
        action (gym.Actions): Input action in normalised range
        window_size (float): Size of the pushT window to which the action is unnormalised
    """
    action = (action + 1)*(window_size)/2

    return action


class PushTEnv(gym.Env):
    metadata = {"render.modes": ["human", "rgb_array"], "video.frames_per_second": 10}
    reward_range = (0., 1.)

    def __init__(self,
            legacy=False, 
            block_cog=None, damping=None,
            render_action=True,
            render_size=96,
            reset_to_state=None,
            cfg=None,
            normalise_action=True,
        ):
        self._seed = None
        self.normalise_action = normalise_action
        self.seed()
        self.window_size = ws = 512  # The size of the PyGame window
        self.render_size = render_size
        self.sim_hz = 100
        # Local controller params.
        self.k_p, self.k_v = 100, 20    # PD control.z
        self.control_hz = self.metadata['video.frames_per_second']
        # legcay set_state for data compatibility
        self.legacy = legacy

        # agent_pos, block_pos, block_angle
        self.observation_space = spaces.Box(
            low=np.array([0,0,0,0,0], dtype=np.float64),
            high=np.array([ws,ws,ws,ws,np.pi*2], dtype=np.float64),
            shape=(5,),
            dtype=np.float64
        )

        # Setting up the env observation space params used to train AMP and similar algos
        if cfg != None:
            # General config params
            self._headless = cfg["headless"]
            self._num_envs = cfg["env"]["numEnvs"]
            self._training_algo = cfg["training_algo"]

            try:
                # Training params for AMP and similar algos
                # self.reset_called = False
                
                # Number of features in an observation vector 
                NUM_OBS_PER_STEP = 5 # [robotY, robotY, tX, tY, tTheta]
                self._num_obs_per_step = NUM_OBS_PER_STEP

                # Number of observations to group together. For example, AMP groups to observations s-s' together to compute rewards as discriminator(s,s')
                # numAMPObsSteps defines the number of obs to group in AMP. numObsSteps also defines the same but is a bit more general in its wording.
                # Support for numAMPObsSteps is kept to maintain compatibility with AMP configs
                try:
                    self._num_obs_steps = cfg["env"]["numAMPObsSteps"]
                except KeyError:
                    self._num_obs_steps = cfg["env"].get("numObsSteps", 2)
                
                self._motion_file = cfg["env"].get('motion_file', "random_motions.npy")
                                
                assert(self._num_obs_steps >= 2)
                # Number of features in the grouped observation vector
                self.num_obs = self._num_obs_steps * NUM_OBS_PER_STEP

                # Observation space as a gym Box object
                self._obs_space = spaces.Box(np.ones(self.num_obs) * -np.Inf, np.ones(self.num_obs) * np.Inf)
            except Exception as e:
                pass


        if self.normalise_action:
            # Normalised actions: in the range [-1,1]. Action space changed to normalised values
            # In the step() function, actions are unnormalised again
            self.action_space = spaces.Box(
                low=np.array([-1,-1], dtype=np.float64),
                high=np.array([1,1], dtype=np.float64),
                shape=(2,),
                dtype=np.float64
            )

        else:
            # positional goal for agent
            self.action_space = spaces.Box(
                low=np.array([0,0], dtype=np.float64),
                high=np.array([ws,ws], dtype=np.float64),
                shape=(2,),
                dtype=np.float64
            )


        self.block_cog = block_cog
        self.damping = damping
        self.render_action = render_action

        """
        If human-rendering is used, `self.window` will be a reference
        to the window that we draw to. `self.clock` will be a clock that is used
        to ensure that the environment is rendered at the correct framerate in
        human-mode. They will remain `None` until human-mode is used for the
        first time.
        """
        self.window = None
        self.clock = None
        self.screen = None

        self.space = None
        self.teleop = None
        self.render_buffer = None
        self.latest_action = None
        self.reset_to_state = reset_to_state

    # Added to provide env obs shape info to amp_continuous
    @property
    def paired_observation_space(self):
        return self._obs_space
    
    def reset(self):
        self._setup()
        if self.block_cog is not None:
            self.block.center_of_gravity = self.block_cog
        if self.damping is not None:
            self.space.damping = self.damping
        
        # use legacy RandomState for compatibility
        state = self.reset_to_state
        if state is None:
            # rs = np.random.RandomState(seed=seed)
            state = np.array([
                self.np_random.integers(low=50, high=450), self.np_random.integers(low=50, high=450),
                self.np_random.integers(low=100, high=400), self.np_random.integers(low=100, high=400),
                self.np_random.normal() * 2 * np.pi - np.pi
                ])
        self._set_state(state)

        observation = self._get_obs()
        return observation

    def reset_done(self):
        """
        Wrapper around reset to enable compatibility with the amp_continous play method
        """
        return self.reset(), []

    def step(self, action):
        if self.normalise_action:
            # Unnormalise action before applying to the env
            action = unnormalise_action(action, self.window_size)

        dt = 1.0 / self.sim_hz
        self.n_contact_points = 0
        n_steps = self.sim_hz // self.control_hz
        if action is not None:
            self.latest_action = action
            for i in range(n_steps):
                # Step PD control.
                # self.agent.velocity = self.k_p * (act - self.agent.position)    # P control works too.
                acceleration = self.k_p * (action - self.agent.position) + self.k_v * (Vec2d(0, 0) - self.agent.velocity)
                self.agent.velocity += acceleration * dt

                # Step physics.
                self.space.step(dt)

        # compute reward
        # TODO: fix shapely divide by zero errors!
        goal_body = self._get_goal_pose_body(self.goal_pose)
        goal_geom = pymunk_to_shapely(goal_body, self.block.shapes)
        block_geom = pymunk_to_shapely(self.block, self.block.shapes)

        intersection_area = goal_geom.intersection(block_geom).area
        goal_area = goal_geom.area
        coverage = intersection_area / goal_area
        reward = np.clip(coverage / self.reward_threshold, 0, 1)

        # If the current reward threshold is mostly met (0.9) then increase it until it reaches the success_threshold
        if reward > 0.9 and self.reward_threshold < self.success_threshold:
            self.reward_threshold += 0.1

        dist_to_goal = -(np.linalg.norm(np.absolute(self.goal_pose[:2]) - np.absolute(np.array(self.block.position))))/725
        # print(f"Dist to goal {dist_to_goal}")
        # orientation_error = -(self.goal_pose[2] - self.block.angle)

        dist_to_block = -(np.linalg.norm(np.absolute(self.agent.position) - np.absolute(np.array(self.block.position))))/363
        # print(f"Dist to block {dist_to_block}")

        dist_reward = dist_to_goal + dist_to_block   
        reward = reward + dist_reward
        # print(f"reward {reward}")


        # ## PPO SANITY CHECK
        # # Dist from agent to centre of env
        # temp = -(np.linalg.norm(np.absolute(self.agent.position) - np.absolute(self.goal_pose[:2])))/363
        # reward = temp
        # ## PPO SANITY CHECK
        
        done = coverage > self.success_threshold
        observation = self._get_obs()
        info = self._get_info()

        # Rewards need to be in the info to get logged by the observer
        info['scores'] = reward

        #Env stops after a certain number of steps
        self.env_steps += 1
        if self.env_steps >= self.max_env_steps:
            done = True

        return observation, reward, done, info

    def render(self, mode):
        return self._render_frame(mode)

    def teleop_agent(self):
        TeleopAgent = collections.namedtuple('TeleopAgent', ['act'])
        def act(obs):
            act = None
            mouse_position = pymunk.pygame_util.from_pygame(Vec2d(*pygame.mouse.get_pos()), self.screen)
            if self.teleop or (mouse_position - self.agent.position).length < 30:
                self.teleop = True
                act = mouse_position
            return act
        return TeleopAgent(act)

    def _get_obs(self):
        obs = np.array(
            tuple(self.agent.position) \
            + tuple(self.block.position) \
            + (self.block.angle % (2 * np.pi),))
        return obs

    def _get_goal_pose_body(self, pose):
        mass = 1
        inertia = pymunk.moment_for_box(mass, (50, 100))
        body = pymunk.Body(mass, inertia)
        # preserving the legacy assignment order for compatibility
        # the order here doesn't matter somehow, maybe because CoM is aligned with body origin
        body.position = pose[:2].tolist()
        body.angle = pose[2]
        return body
    
    def _get_info(self):
        n_steps = self.sim_hz // self.control_hz
        n_contact_points_per_step = int(np.ceil(self.n_contact_points / n_steps))
        info = {
            'pos_agent': np.array(self.agent.position),
            'vel_agent': np.array(self.agent.velocity),
            'block_pose': np.array(list(self.block.position) + [self.block.angle]),
            'goal_pose': self.goal_pose,
            'n_contacts': n_contact_points_per_step}
        return info

    def _render_frame(self, mode):

        if self.window is None and mode == "human":
            pygame.init()
            pygame.display.init()
            self.window = pygame.display.set_mode((self.window_size, self.window_size))
        if self.clock is None and mode == "human":
            self.clock = pygame.time.Clock()

        canvas = pygame.Surface((self.window_size, self.window_size))
        canvas.fill((255, 255, 255))
        self.screen = canvas

        draw_options = DrawOptions(canvas)

        # Draw goal pose.
        goal_body = self._get_goal_pose_body(self.goal_pose)
        for shape in self.block.shapes:
            goal_points = [pymunk.pygame_util.to_pygame(goal_body.local_to_world(v), draw_options.surface) for v in shape.get_vertices()]
            goal_points += [goal_points[0]]
            pygame.draw.polygon(canvas, self.goal_color, goal_points)

        # Draw agent and block.
        self.space.debug_draw(draw_options)

        if mode == "human":
            # The following line copies our drawings from `canvas` to the visible window
            self.window.blit(canvas, canvas.get_rect())
            pygame.event.pump()
            pygame.display.update()

            # the clock is already ticked during in step for "human"


        img = np.transpose(
                np.array(pygame.surfarray.pixels3d(canvas)), axes=(1, 0, 2)
            )
        img = cv2.resize(img, (self.render_size, self.render_size))
        if self.render_action:
            if self.render_action and (self.latest_action is not None):
                action = np.array(self.latest_action)
                coord = (action / 512 * 96).astype(np.int32)
                marker_size = int(8/96*self.render_size)
                thickness = int(1/96*self.render_size)
                cv2.drawMarker(img, coord,
                    color=(255,0,0), markerType=cv2.MARKER_CROSS,
                    markerSize=marker_size, thickness=thickness)
        return img


    def close(self):
        if self.window is not None:
            pygame.display.quit()
            pygame.quit()
    
    def seed(self, seed=None):
        if seed is None:
            seed = np.random.randint(0,25536)
        self._seed = seed
        self.np_random = np.random.default_rng(seed)

    def _handle_collision(self, arbiter, space, data):
        self.n_contact_points += len(arbiter.contact_point_set.points)

    def _set_state(self, state):
        if isinstance(state, np.ndarray):
            state = state.tolist()
        pos_agent = state[:2]
        pos_block = state[2:4]
        rot_block = state[4]
        self.agent.position = pos_agent
        # setting angle rotates with respect to center of mass
        # therefore will modify the geometric position
        # if not the same as CoM
        # therefore should be modified first.
        if self.legacy:
            # for compatibility with legacy data
            self.block.position = pos_block
            self.block.angle = rot_block
        else:
            self.block.angle = rot_block
            self.block.position = pos_block

        # Run physics to take effect
        self.space.step(1.0 / self.sim_hz)
    
    def _set_state_local(self, state_local):
        agent_pos_local = state_local[:2]
        block_pose_local = state_local[2:]
        tf_img_obj = st.AffineTransform(
            translation=self.goal_pose[:2], 
            rotation=self.goal_pose[2])
        tf_obj_new = st.AffineTransform(
            translation=block_pose_local[:2],
            rotation=block_pose_local[2]
        )
        tf_img_new = st.AffineTransform(
            matrix=tf_img_obj.params @ tf_obj_new.params
        )
        agent_pos_new = tf_img_new(agent_pos_local)
        new_state = np.array(
            list(agent_pos_new[0]) + list(tf_img_new.translation) \
                + [tf_img_new.rotation])
        self._set_state(new_state)
        return new_state

    def _setup(self):
        self.space = pymunk.Space()
        self.space.gravity = 0, 0
        self.space.damping = 0
        self.teleop = False
        self.render_buffer = list()
        
        # Add walls.
        walls = [
            self._add_segment((5, 506), (5, 5), 2),
            self._add_segment((5, 5), (506, 5), 2),
            self._add_segment((506, 5), (506, 506), 2),
            self._add_segment((5, 506), (506, 506), 2)
        ]
        self.space.add(*walls)

        # Add agent, block, and goal zone.
        self.agent = self.add_circle((256, 400), 15)
        self.block = self.add_tee((256, 300), 0)
        self.goal_color = pygame.Color('LightGreen')
        self.goal_pose = np.array([256,256,np.pi/4])  # x, y, theta (in radians)

        # Add collision handling
        self.collision_handeler = self.space.add_collision_handler(0, 0)
        self.collision_handeler.post_solve = self._handle_collision
        self.n_contact_points = 0

        self.max_score = 50 * 100

        # success_threshold is the threshold after which env is done. reward_threshold gradually goes up to incrementally provide a reward signal
        self.reward_threshold = 0.1
        self.success_threshold = 0.95    # 95% coverage.

        # Counting the number of steps
        self.env_steps = 0
        # step() returns done after this
        self.max_env_steps = 150

    def _add_segment(self, a, b, radius):
        shape = pymunk.Segment(self.space.static_body, a, b, radius)
        shape.color = pygame.Color('LightGray')    # https://htmlcolorcodes.com/color-names
        return shape

    def add_circle(self, position, radius):
        body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        body.position = position
        body.friction = 1
        shape = pymunk.Circle(body, radius)
        shape.color = pygame.Color('RoyalBlue')
        self.space.add(body, shape)
        return body

    def add_box(self, position, height, width):
        mass = 1
        inertia = pymunk.moment_for_box(mass, (height, width))
        body = pymunk.Body(mass, inertia)
        body.position = position
        shape = pymunk.Poly.create_box(body, (height, width))
        shape.color = pygame.Color('LightSlateGray')
        self.space.add(body, shape)
        return body

    def add_tee(self, position, angle, scale=30, color='LightSlateGray', mask=pymunk.ShapeFilter.ALL_MASKS()):
        mass = 1
        length = 4
        vertices1 = [(-length*scale/2, scale),
                                 ( length*scale/2, scale),
                                 ( length*scale/2, 0),
                                 (-length*scale/2, 0)]
        inertia1 = pymunk.moment_for_poly(mass, vertices=vertices1)
        vertices2 = [(-scale/2, scale),
                                 (-scale/2, length*scale),
                                 ( scale/2, length*scale),
                                 ( scale/2, scale)]
        inertia2 = pymunk.moment_for_poly(mass, vertices=vertices1)
        body = pymunk.Body(mass, inertia1 + inertia2)
        shape1 = pymunk.Poly(body, vertices1)
        shape2 = pymunk.Poly(body, vertices2)
        shape1.color = pygame.Color(color)
        shape2.color = pygame.Color(color)
        shape1.filter = pymunk.ShapeFilter(mask=mask)
        shape2.filter = pymunk.ShapeFilter(mask=mask)
        body.center_of_gravity = (shape1.center_of_gravity + shape2.center_of_gravity) / 2
        body.position = position
        body.angle = angle
        body.friction = 1
        self.space.add(body, shape1, shape2)
        return body
