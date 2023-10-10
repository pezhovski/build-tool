import toml

from action.action import Action
from config.config import load_config


class Build:
    def __init__(self, pipeline_file):
        self.load_pipeline(pipeline_file)

    def load_pipeline(self, pipeline_file):
        with open(pipeline_file, 'r') as file:
            pipeline_config = toml.load(file)

            scms_configs = pipeline_config.get('pipeline', {}).get('scms', [])
            self.scms = {}
            for scm_name, scm_config in scms_configs.items():
                if scm_name in self.scms:
                    raise ValueError(f'SCM with name {scm_name} already exists')
                self.scms[scm_name] = scm_config

            actions_configs = pipeline_config.get('pipeline', {}).get('actions', [])
            self.actions = []

            for action_config in actions_configs:
                self.actions.append(Action(self, action_config))

    def run(self):
        for action in self.actions:
            action.execute()


if __name__ == '__main__':
    load_config(config_path='config.toml')

    pipeline_file = 'pipeline.toml'
    engine = Build(pipeline_file)
    engine.run()
