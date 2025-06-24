import pytest

from config import get_named_config

TEST_ENVIRONMENT_DATA = [
    ("valid", "development", "Development"),
    ("valid", "testing", "Testing"),
    ("valid", "default", "Production"),
    ("valid", "staging", "Production"),
    ("valid", "production", "Production"),
    ("error", None, KeyError),
]


@pytest.mark.parametrize("test_type, environment, expected", TEST_ENVIRONMENT_DATA)
def test_get_named_config(test_type, environment, expected):
    """Assert that the named configurations can be loaded or raise KeyError."""
    if test_type == "valid":
        config_obj = get_named_config(environment)
        assert config_obj.__class__.__name__ == expected
    else:
        with pytest.raises(expected):
            get_named_config(environment)
