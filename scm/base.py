from abc import ABC, abstractmethod


class SCMBase(ABC):
    @abstractmethod
    def checkout(self, revision=None):
        pass

    @abstractmethod
    def cleanup(self):
        pass

    @abstractmethod
    def upload(self):
        pass

    @abstractmethod
    def get_changelog(self):
        pass

    @abstractmethod
    def get_current_revision(self):
        pass
