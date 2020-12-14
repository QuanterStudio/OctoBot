#  Drakkar-Software OctoBot
#  Copyright (c) Drakkar-Software, All rights reserved.
#
#  This library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3.0 of the License, or (at your option) any later version.
#
#  This library is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public
#  License along with this library.
import copy
import os
import shutil

import octobot.constants as constants
import octobot_commons.configuration as configuration
import octobot_commons.constants as common_constants
import octobot_commons.logging as logging

import octobot_trading.api as trading_api

LOGGER_NAME = "Configuration"


class ConfigurationManager:
    def __init__(self):
        self.configuration_elements = {}

    def add_element(self, key, element, has_dict=False):
        self.configuration_elements[key] = ConfigurationElement(element, has_dict)

    def get_edited_config(self, key, dict_only):
        config_element = self.configuration_elements[key]
        if dict_only and config_element.has_dict:
            return config_element.edited_config.config
        return self.configuration_elements[key].edited_config

    def get_startup_config(self, key, dict_only):
        config_element = self.configuration_elements[key]
        if dict_only and config_element.has_dict:
            return config_element.startup_config.config
        return self.configuration_elements[key].startup_config


class ConfigurationElement:
    def __init__(self, element, has_dict):
        self.config = element
        self.has_dict = has_dict
        self.startup_config = copy.deepcopy(element)
        self.edited_config = copy.deepcopy(element)


def config_health_check(config: configuration.Configuration, in_backtesting: bool) -> configuration.Configuration:
    logger = logging.get_logger(LOGGER_NAME)
    # 1 ensure api key encryption
    should_replace_config = False
    if common_constants.CONFIG_EXCHANGES in config.config:
        for exchange, exchange_config in config.config[common_constants.CONFIG_EXCHANGES].items():
            for key in common_constants.CONFIG_EXCHANGE_ENCRYPTED_VALUES:
                try:
                    if not configuration.handle_encrypted_value(key, exchange_config, verbose=True):
                        should_replace_config = True
                except Exception as e:
                    logger.exception(e, True,
                                     f"Exception when checking exchange config encryption: {e}")

    # 2 ensure single trader activated
    try:
        trader_enabled = trading_api.is_trader_enabled_in_config(config.config)
        if trader_enabled:
            simulator_enabled = trading_api.is_trader_simulator_enabled_in_config(config.config)
            if simulator_enabled:
                logger.error(f"Impossible to activate a trader simulator additionally to a "
                             f"real trader, simulator deactivated.")
                config.config[common_constants.CONFIG_SIMULATOR][common_constants.CONFIG_ENABLED_OPTION] = False
                should_replace_config = True
    except KeyError as e:
        logger.exception(e, True,
                         f"KeyError when checking traders activation: {e}. "
                         f"Activating trader simulator.")
        config.config[common_constants.CONFIG_SIMULATOR][common_constants.CONFIG_ENABLED_OPTION] = True
        config.config[common_constants.CONFIG_TRADER][common_constants.CONFIG_ENABLED_OPTION] = False
        should_replace_config = True

    # 3 inform about configuration issues
    if not (in_backtesting or
            trading_api.is_trader_enabled_in_config(config.config) or
            trading_api.is_trader_simulator_enabled_in_config(config.config)):
        logger.error(f"Real trader and trader simulator are deactivated in configuration. This will prevent OctoBot "
                     f"from creating any new order.")

    # 4 save fixed config if necessary
    if should_replace_config:
        try:
            config.save()
            return config
        except Exception as e:
            logger.error(f"Save of the health checked config failed : {e}, "
                         f"will use the initial config")
            config.read(should_raise=False, fill_missing_fields=True)
            return config


def init_config(
        config_file=configuration.get_user_config(),
        from_config_file=constants.DEFAULT_CONFIG_FILE
):
    """
    Initialize default config
    :param config_file: the config file path
    :param from_config_file: the default config file path
    """
    try:
        if not os.path.exists(common_constants.USER_FOLDER):
            os.makedirs(common_constants.USER_FOLDER)

        shutil.copyfile(from_config_file, config_file)
        profile_folder = os.path.join(common_constants.USER_PROFILES_FOLDER,
                                      common_constants.DEFAULT_PROFILE)
        if not os.path.exists(profile_folder):
            os.makedirs(profile_folder)
        shutil.copyfile(constants.DEFAULT_PROFILE_FILE,
                        os.path.join(profile_folder, common_constants.DEFAULT_PROFILE_FILE))
        shutil.copyfile(constants.DEFAULT_PROFILE_AVATAR,
                        os.path.join(profile_folder, constants.DEFAULT_PROFILE_AVATAR_FILE_NAME))
    except Exception as global_exception:
        raise Exception(f"Can't init config file {global_exception}")
