"""
Configuration Module

This module provides a class for loading, validating and managing configuration settings.
"""

import copy
import os

import hvac
import toml

ALLOWED_CHANGES_COLLECTION_MODES = ['timestamp', 'changelist']

# pylint: disable-next=invalid-name
_config = None


def load_config(config_path='config.toml'):
    """
    Loads config from provided path, assignes it into global variable
    """
    # pylint: disable-next=global-statement
    global _config
    _config = Config(config_path)


def get_config():
    """
    Returns config instance
    """
    return _config


class Config:
    """
    A class for loading, managing and accessing configuration settings configuration file.

    Parameters:
    config_path : str, optional
        The path to the configuration file.
    """
    def __init__(self, config_path):
        self.config_path = os.path.abspath(config_path)
        self._load_config()

    def _load_config(self):
        """
        Loads configuration from file and validates it
        """
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f'Config file not found: {self.config_path}')

        with open(self.config_path, 'r', encoding='utf-8') as file:
            self._config = toml.load(file)

        self._config['main']['ci_home'] = os.path.abspath(self._config['main'].get('ci_home', './ci_home'))

        changes_collection_mode = self._config['main'].get('changes_collection_mode', 'timestamp')
        if changes_collection_mode not in ALLOWED_CHANGES_COLLECTION_MODES:
            raise ValueError(
                f'Invalid value for "changes_collection_mode": "{changes_collection_mode}",' +
                f'valid options are: {ALLOWED_CHANGES_COLLECTION_MODES}')

    def _get_config_section(self, section, section_name):
        """
        Actually retrieves the configuration of certain type
        """
        config_section = copy.deepcopy(self._config.get(section, {}).get(section_name, {}))
        if not config_section:
            raise ValueError(f'Missing {section} config with name "{section_name}"')

        return self.retrieve_secrets_from_vault(config_section)

    def get_connection_config(self, name):
        """
        Retrieves the configuration settings for a Perforce connection with the given name.
        """
        return self._get_config_section('perforce_connection', name)

    def get_workspace_config(self, name):
        """
        Retrieves the configuration settings for a Perforce workspace with the given name.
        """
        return self._get_config_section('perforce_workspace', name)

    def get_job_config(self, name):
        """
        Retrieves the configuration settings for a Job with the given name.
        """
        return self._get_config_section('job', name)

    def get_main_config(self):
        """
        Retrieves the global (main) configuration settings.
        """
        return copy.deepcopy(self._config['main'])

    def retrieve_secrets_from_vault(self, config_section):
        """
        Reads config section, finds and resolves references to vault secret
        """
        for key, value in config_section.items():
            if isinstance(value, str) and value.startswith('vault://'):
                secret_path = value[len('vault://'):].strip()
                secret_data = self._read_secret_from_vault(secret_path)
                config_section[key] = secret_data

        return config_section

    def _read_secret_from_vault(self, secret_address):
        """
        Actually resolves references to vault
        """
        vault_addr = self.get_main_config().get('vault_address')
        vault_token = self.get_main_config().get('vault_token')

        if not vault_addr:
            raise ValueError('"main.vault_address" should be specified when using secrets')
        if not vault_token:
            raise ValueError('"main.vault_token" should be specified when using secrets')

        client = hvac.Client(url=vault_addr, token=vault_token)

        secret_address_parts = secret_address.split('#')
        full_secret_path = secret_address_parts[0]
        secret_key = secret_address_parts[1] if len(secret_address_parts) > 1 else None

        if not secret_key:
            raise ValueError(
                'Invalid secret format, secret should be in format: vault://<secret_engine>/<secret_path>#<secret_key>')

        secret_path_parts = full_secret_path.split('/')
        secret_mount = secret_path_parts[0]
        secret_path = '/'.join(secret_path_parts[1:]) if len(secret_path_parts) > 1 else None

        if not secret_mount:
            raise ValueError(
                'Invalid secret format, secret should be in format: vault://<secret_engine>/<secret_path>#<secret_key>')

        try:
            secret_data = client.secrets.kv.v2.read_secret_version(
                path=secret_path, mount_point=secret_mount)['data']['data']
            if not secret_data:
                raise ValueError(f'Secret not found at {secret_path}')

            secret = secret_data.get(secret_key)
            if not secret:
                raise ValueError(f'Secret don\'t have key {secret_key}')
            return secret
        except Exception as ex:
            raise ValueError(f'Error retrieving secret: {str(ex)}') from ex
