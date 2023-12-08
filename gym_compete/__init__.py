from gymnasium.envs.registration import register
import os

CUSTOM_ENVS = ["sumo-ants-v0"]

register(
    id='run-to-goal-bugs-v0',
    entry_point='gym_compete.new_envs:MultiAgentEnv',
    disable_env_checker=True,
    kwargs={'agent_names': ['bug', 'bug'],
            'scene_xml_path': os.path.join(
                os.path.dirname(__file__),
                "new_envs", "assets",
                "world_body.bug_body.bug_body.xml"
            ),
            'init_pos': [(-1, 0, 0.75), (1, 0, 0.75)],
            'ini_euler': [(0, 0, 0), (0, 0, 180)],
            'cfg_path': "config/run-to-goal-bugs-v0.yaml",
            },
)

register(
    id='run-to-goal-bug-v0',
    entry_point='gym_compete.new_envs:MultiAgentEnv',
    disable_env_checker=True,
    kwargs={'agent_names': ['bug'],
            'scene_xml_path': os.path.join(
                os.path.dirname(__file__),
                "new_envs", "assets",
                "world_body.bug_body.xml"
            ),
            # 'init_pos': [(-1, 0, 0.75)],
            # 'ini_euler': [(0, 0, 0)],
            'init_pos': [(1, 0, 0.75)],
            'ini_euler': [(0, 0, 180)],
            'cfg_path': "config/run-to-goal-bug-v0.yaml",
            },
)

register(
    id='run-to-goal-spider-v0',
    entry_point='gym_compete.new_envs:MultiAgentEnv',
    disable_env_checker=True,
    kwargs={'agent_names': ['spider'],
            'scene_xml_path': os.path.join(
                os.path.dirname(__file__),
                "new_envs", "assets",
                "world_body.spider_body.xml"
            ),
            # 'init_pos': [(-1, 0, 0.75)],
            # 'ini_euler': [(0, 0, 0)],
            'init_pos': [(1, 0, 0.75)],
            'ini_euler': [(0, 0, 180)],
            'cfg_path': "config/run-to-goal-spider-v0.yaml",
            },
)

register(
    id='run-to-goal-spiders-v0',
    entry_point='gym_compete.new_envs:MultiAgentEnv',
    disable_env_checker=True,
    kwargs={'agent_names': ['spider', 'spider'],
            'scene_xml_path': os.path.join(
                os.path.dirname(__file__),
                "new_envs", "assets",
                "world_body.spider_body.spider_body.xml"
            ),
            'init_pos': [(-1, 0, 0.75), (1, 0, 0.75)],
            'ini_euler': [(0, 0, 0), (0, 0, 180)],
            'cfg_path': "config/run-to-goal-spiders-v0.yaml",
            },
)

register(
    id='run-to-goal-ants-v0',
    entry_point='gym_compete.new_envs:MultiAgentEnv',
    disable_env_checker=True,
    kwargs={'agent_names': ['ant', 'ant'],
            'scene_xml_path': os.path.join(
                os.path.dirname(__file__),
                "new_envs", "assets",
                "world_body.ant_body.ant_body.xml"
            ),
            'init_pos': [(-1, 0, 0.75), (1, 0, 0.75)],
            'ini_euler': [(0, 0, 0), (0, 0, 180)],
            'cfg_path': "config/run-to-goal-ants-v0.yaml",
            },
)

register(
    id='run-to-goal-ant-v0',
    entry_point='gym_compete.new_envs:MultiAgentEnv',
    disable_env_checker=True,
    kwargs={'agent_names': ['ant'],
            'scene_xml_path': os.path.join(
                os.path.dirname(__file__),
                "new_envs", "assets",
                "world_body.ant_body.xml"
            ),
            'init_pos': [(-1, 0, 0.75)],
            'ini_euler': [(0, 0, 0)],
            # 'init_pos': [(1, 0, 0.75)],
            # 'ini_euler': [(0, 0, 180)],
            'max_episode_steps': 500,
            'cfg_path': "config/run-to-goal-ant-v0.yaml",
            },
)

register(
    id='run-to-goal-humans-v0',
    entry_point='gym_compete.new_envs:MultiAgentEnv',
    disable_env_checker=True,
    kwargs={'agent_names': ['humanoid', 'humanoid'],
            'scene_xml_path': os.path.join(
                os.path.dirname(__file__), "new_envs",
                "assets",
                "world_body.humanoid_body.humanoid_body.xml"
            ),
            'init_pos': [(-1, 0, 1.4), (1, 0, 1.4)],
            'ini_euler': [(0, 0, 0), (0, 0, 180)],
            'cfg_path': "config/run-to-goal-humans-v0.yaml",
            },
)

register(
    id='run-to-goal-human-v0',
    entry_point='gym_compete.new_envs:MultiAgentEnv',
    disable_env_checker=True,
    kwargs={'agent_names': ['humanoid'],
            'scene_xml_path': os.path.join(
                os.path.dirname(__file__), "new_envs",
                "assets",
                "world_body.humanoid_body.xml"
            ),
            'init_pos': [(-1, 0, 1.4)],
            'ini_euler': [(0, 0, 0)],
            'max_episode_steps': 500,
            'cfg_path': "config/run-to-goal-human-v0.yaml",
            },
)

register(
    id='you-shall-not-pass-humans-v0',
    entry_point='gym_compete.new_envs:HumansBlockingEnv',
    disable_env_checker=True,
    kwargs={'agent_names': ['humanoid_blocker', 'humanoid'],
            'scene_xml_path': os.path.join(
                os.path.dirname(__file__), "new_envs",
                "assets",
                "world_body.humanoid_body.humanoid_body.xml"
            ),
            'init_pos': [(-1, 0, 1.4), (1, 0, 1.4)],
            'ini_euler': [(0, 0, 0), (0, 0, 180)],
            'max_episode_steps': 500,
            },
)

register(
    id='sumo-humans-v0',
    entry_point='gym_compete.new_envs:SumoEnv',
    disable_env_checker=True,
    kwargs={'agent_names': ['humanoid_fighter', 'humanoid_fighter'],
            'scene_xml_path': os.path.join(
                os.path.dirname(__file__), "new_envs",
                "assets",
                "world_body_arena.humanoid_body.humanoid_body.xml"
            ),
            'world_xml_path': os.path.join(
                os.path.dirname(__file__), "new_envs",
                "assets", 'world_body_arena.xml'
            ),
            'init_pos': [(-1, 0, 2), (1, 0, 2)],
            'ini_euler': [(0, 0, 0), (0, 0, 180)],
            'max_episode_steps': 500,
            'min_radius': 1.5,
            'max_radius': 3.5,
            'cfg_path': "config/sumo-humans-v0.yaml",
            },
)

register(
    id='sumo-ants-v0',
    entry_point='gym_compete.new_envs:SumoEnv',
    disable_env_checker=True,
    kwargs={'agent_names': ['ant_fighter', 'ant_fighter'],
            'scene_xml_path': os.path.join(
                os.path.dirname(__file__), "new_envs",
                "assets",
                "world_body_arena.ant_body.ant_body.xml"
            ),
            'world_xml_path': os.path.join(
                os.path.dirname(__file__), "new_envs",
                "assets", 'world_body_arena.xml'
            ),
            'init_pos': [(-1, 0, 2.5), (1, 0, 2.5)],
            # 'ini_euler': [(0, 0, 0), (0, 0, 180)],
            'max_episode_steps': 500,
            'min_radius': 2.5,
            'max_radius': 4.5,
            'cfg_path': "config/sumo-ants-v0.yaml",
            },
)

register(
    id='robo-sumo-ants-v0',
    entry_point='gym_compete.new_envs:RoboSumoEnv',
    disable_env_checker=True,
    kwargs={'agent_names': ['robo_ant_fighter', 'robo_ant_fighter'],
            'scene_xml_path': os.path.join(
                os.path.dirname(__file__), "new_envs",
                "assets",
                "world_body_arena.ant_body.ant_body.xml"
            ),
            'world_xml_path': os.path.join(
                os.path.dirname(__file__), "new_envs",
                "assets", 'world_body_arena.xml'
            ),
            'init_pos': [(-1, 0, 2.5), (1, 0, 2.5)],
            'ini_euler': [(0, 0, 0), (0, 0, 180)],
            'max_episode_steps': 500,
            'min_radius': 2.5,
            'max_radius': 4.5,
            'cfg_path': "config/robo-sumo-ants-v0.yaml",
            },
)


# register(
#     id='HumanAntArena-v0',
#     entry_point='gym_compete.new_envs:HumansKnockoutEnv',
#     kwargs={'agent_names': ['ant_fighter', 'humanoid_fighter'],
#             'scene_xml_path': os.path.join(
#                 os.path.dirname(__file__), "new_envs",
#                 "assets",
#                 "world_body_arena.ant_body.human_body.xml"
#             ),
#             'world_xml_path': os.path.join(
#                 os.path.dirname(__file__), "new_envs",
#                 "assets", 'world_body_arena.xml'
#             ),
#             'init_pos': [(-1, 0, 2.5), (1, 0, 2.5)],
#             'max_episode_steps': 500,
#             'min_radius': 2,
#             'max_radius': 3.5
#             },
# )

register(
    id='kick-and-defend-v0',
    entry_point='gym_compete.new_envs:KickAndDefend',
    kwargs={'agent_names': ['humanoid_kicker', 'humanoid_goalkeeper'], # ['humanoid_goalkeeper', 'humanoid_kicker']
            'scene_xml_path': os.path.join(
                os.path.dirname(__file__), "new_envs",
                "assets",
                "world_body_football.humanoid_body.humanoid_body.xml"
            ),
            'world_xml_path': os.path.join(
                os.path.dirname(__file__), "new_envs",
                "assets", 'world_body_football.xml'
            ),
            'init_pos': [(-1, 0, 1.5), (1, 0, 1.5)],
            'max_episode_steps': 500,
            },
)