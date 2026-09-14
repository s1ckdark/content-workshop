import os

import config


def test_root_dir_is_project_root():
    assert os.path.isdir(os.path.join(config.ROOT_DIR, "src"))


def test_config_is_injected():
    assert config.get_nanobanana2_api_key() == "test-key"
