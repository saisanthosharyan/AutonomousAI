import pytest

from app.services.fixer.patch_validator import PatchValidator


@pytest.fixture
def validator():
    return PatchValidator()


def test_application_file_is_allowed(validator):
    response = """
FILE: app.py
def multiply(a, b):
    return a * b
END FILE
"""

    patches = validator.validate(response)

    assert len(patches) == 1
    assert patches[0]["path"] == "app.py"


def test_tests_directory_is_protected(validator):
    response = """
FILE: tests/test_app.py
def test_multiply():
    assert True
END FILE
"""

    with pytest.raises(ValueError, match="Protected test file"):
        validator.validate(response)


def test_nested_tests_directory_is_protected(validator):
    response = """
FILE: tests/api/test_user.py
def test_user():
    assert True
END FILE
"""

    with pytest.raises(ValueError, match="Protected test file"):
        validator.validate(response)


def test_test_directory_is_protected(validator):
    response = """
FILE: test/test_app.py
def test_app():
    assert True
END FILE
"""

    with pytest.raises(ValueError, match="Protected test file"):
        validator.validate(response)


def test_test_prefix_file_is_protected(validator):
    response = """
FILE: test_app.py
def test_app():
    assert True
END FILE
"""

    with pytest.raises(ValueError, match="Protected test file"):
        validator.validate(response)


def test_test_suffix_file_is_protected(validator):
    response = """
FILE: app_test.py
def test_app():
    assert True
END FILE
"""

    with pytest.raises(ValueError, match="Protected test file"):
        validator.validate(response)


def test_multiple_application_files_are_allowed(validator):
    response = """
FILE: app.py
def multiply(a, b):
    return a * b
END FILE

FILE: services/calculator.py
def add(a, b):
    return a + b
END FILE
"""

    patches = validator.validate(response)

    assert len(patches) == 2
    assert patches[0]["path"] == "app.py"
    assert patches[1]["path"] == "services/calculator.py"


def test_mixed_application_and_test_files_are_rejected(validator):
    response = """
FILE: app.py
def multiply(a, b):
    return a * b
END FILE

FILE: tests/test_app.py
def test_multiply():
    assert True
END FILE
"""

    with pytest.raises(ValueError, match="Protected test file"):
        validator.validate(response)