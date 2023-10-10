import os
import logging
import glob
import socket
import contextlib
from P4 import P4, P4Exception

from scm.base import SCMBase
from config.config import get_config


class PerforceConnection(P4):
    """
    This class provides a convenient way to create and manage Perforce connection based
    on a given connection name and optional configuration.

    Parameters:
    connection_name : str
        The name of the connection used to fetch configuration from config file.

    connection_config : dict, optional
        A dictionary containing Perforce connection configuration settings.
        If not provided, the configuration will be fetched from config file.
    """
    def __init__(self, connection_name, connection_config=None):
        super().__init__()

        if not connection_config:
            connection_config = get_config().get_connection_config(connection_name)

        self.user = connection_config['username']
        self.password = connection_config['password']

        p4port = f'{connection_config["server_host"]}:{connection_config.get("server_port", 1666)}'
        if connection_config.get('server_tls', False):
            p4port = f'ssl:{p4port}'
        self.port = p4port


class PerforceSCM(SCMBase):
    def __init__(self, scm_config=None):
        self.revision = None
        self.changelog = None

        try:
            self.depot_name = scm_config['depot_name']
            self.stream_name = scm_config['stream_name']
            self.client_root = os.path.abspath(scm_config['client_root'])
        except KeyError as ex:
            raise KeyError(f'Option {ex} is missing from scm configuration')

        self.client_name = scm_config.get('client_name', self._generate_client_name())
        self.sync_force = scm_config.get('sync_force', False)
        self.sync_clean = scm_config.get('sync_clean', True)
        self.server_trust = scm_config.get('server_trust', True)

        self._connection = PerforceConnection(scm_config['connection_config_name'])
        # TODO: Check if depot exists
        # TODO: Check if stream exists

    def _create_client(self):
        """
        Creates perforce workspace (client)
        """
        client = self._connection.fetch_client(self.client_name)
        client['Stream'] = f'//{self.depot_name}/{self.stream_name}'
        client['Root'] = self.client_root
        client['Options'] = 'rmdir allwrite'
        self._connection.save_client(client)
        # pylint: disable-next=attribute-defined-outside-init
        self._connection.client = self.client_name
        os.makedirs(self.client_root, exist_ok=True)

    def _generate_client_name(self):
        return f'BUILD-TOOL-{socket.gethostname()}'

    @contextlib.contextmanager
    def _in_client(self):
        """
        A context manager that temporarily changes the current working directory to the
        workspace root.
        """
        previous_dir = os.getcwd()

        try:
            if not self._connection.connected():
                self._connect()
            os.chdir(self.client_root)
            yield
        finally:
            os.chdir(previous_dir)

    def _connect(self):
        """
        Prepares workspace to work.
        """
        # TODO: Check if already connected
        self._connection.connect()
        if self.server_trust:
            self._connection.run_trust('-d')
            self._connection.run_trust('-y', '-f')
        self._connection.run_login()
        self._create_client()

    def checkout(self, revision=None):
        """
        Syncs the workspace
        """
        with self._in_client():
            args = []
            kwargs = {}

            if self.sync_force:
                args.append('-f')

            if revision:
                args.append(f'@{revision}')

            in_sync = False

            try:
                self._connection.run_sync('-n', *args, **kwargs)
            except P4Exception as ex:
                if 'File(s) up-to-date.' in str(ex):
                    logging.info('Workspace is in sync with depot')
                    in_sync = True
                else:
                    raise ex

            if not in_sync or self.sync_force:
                self._connection.run_sync(*args, **kwargs)

            if self.sync_clean:
                pass
                # Causes error on clean sync
                # self._connection.run_clean()

    def cleanup(self):
        self._connection.run_logout()
        self._connection.disconnect()

    def get_changelog(self):
        return

    def get_current_revision(self):
        return

    def upload(self, paths=None, message=None):
        """
        Submits the files specified by `paths` to Perforce only if they have been modified.

        Parameters:
        paths : list
            A list of file paths or glob patterns to be considered for submission.

        message : str, optional
            A custom message to be associated with the submission.
        """
        paths = paths or []

        with self._in_client():
            has_changes = False
            for file_path in paths:
                matching_files = glob.glob(file_path)
                if not matching_files:
                    logging.warning('Invalid path to submit: %s', file_path)
                    continue

                for file in matching_files:
                    try:
                        self._connection.run_reconcile('-n', os.path.abspath(file))
                    except P4Exception as ex:
                        if 'no file(s) to reconcile' in str(ex):
                            logging.debug('File %s not changed, not submitting', file)
                            continue

                        raise ex
                    else:
                        has_changes = True
                        self._connection.run_reconcile(os.path.abspath(file))
                        logging.debug('Reconciled %s', file)

            if has_changes:
                self._connection.run_submit('-d', message)
                return

            logging.info('Nothing to submit')
