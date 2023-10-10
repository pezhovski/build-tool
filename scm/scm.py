from scm.perforce import PerforceSCM
from scm.base import SCMBase


class SCM(SCMBase):
    def __init__(self, scm_config):
        scm_type = scm_config.pop('type', None)

        if scm_type == 'perforce':
            self.scm = PerforceSCM(scm_config)
        else:
            raise ValueError(f'Invalid scm_type: {scm_type}')

    def checkout(self, revision=None):
        self.scm.checkout(revision=revision)

    def cleanup(self):
        self.scm.cleanup()

    def upload(self):
        self.scm.upload()

    def get_changelog(self):
        self.scm.get_changelog()

    def get_current_revision(self):
        self.scm.get_current_revision()
