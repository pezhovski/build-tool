import subprocess
from abc import ABC, abstractmethod
from copy import deepcopy

from scm.scm import SCM


class ActionInterface(ABC):
    @abstractmethod
    def execute(self):
        pass


class BaseAction():
    def __init__(self, build, action_config):
        self.build = build


class BaseSCMAction():
    def __init__(self, build, action_config):
        scm_name = action_config.get('scm_name')
        if not scm_name:
            raise ValueError('scm_name is required for SCM Action')

        try:
            scm_config = deepcopy(build.scms[scm_name])
            self.scm = SCM(scm_config)
        except KeyError as ex:
            raise KeyError(f'Unknown SCM config "{ex}".')

    def execute(self):
        self.scm.cleanup()


class SCMCheckoutAction(BaseSCMAction, BaseAction, ActionInterface):
    def __init__(self, build, action_config, revision=None):
        super().__init__(build, action_config)
        self.revision = revision

    def execute(self):
        self.scm.checkout(revision=self.revision)
        super().execute()


class SCMUploadAction(BaseSCMAction, BaseAction, ActionInterface):
    _DEFAULT_SUBMIT_MESSAGE = "Auto-generated commit"

    def __init__(self, build, action_config):
        super().__init__(build, action_config)
        self.message = action_config.get('message') or self._DEFAULT_SUBMIT_MESSAGE

    def execute(self):
        self.scm.upload()
        super().execute()


class CommandAction(BaseAction, ActionInterface):
    def __init__(self, build, action_config):
        super().__init__(build, action_config)
        self.commands = action_config.get('commands')

    def execute(self):
        for command in self.commands:
            try:
                subprocess.run(command, shell=True, check=True)
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f'Command execution failed: {e}')


class Action(BaseAction, ActionInterface):
    def __init__(self, build, action_config):
        action_name = action_config.pop('name')

        for key, value in action_config.items():
            if key == 'checkout':
                self.action = SCMCheckoutAction(build, value)
                break
            if key == 'command':
                self.action = CommandAction(build, value)
                break
            if key == 'upload':
                self.action = SCMUploadAction(build, value)
                break

        if not self.action:
            raise ValueError(f'Invalid or unknown action type for {action_name}')

        self.action.name = action_name

    def execute(self):
        print(f"Started action '{self.action.name}'.")
        self.action.execute()
        print(f"Action '{self.action.name}' completed successfully.")
