import pytest
from src.use_cases.manage_users import _EMAIL_RE


@pytest.mark.parametrize("email", [
    "user@mail.ru",
    "a.b+c@sub.domain.com",
    "user123@test.io",
    "first.last@company.org",
    "name+tag@gmail.com",
])
def test_valid_emails(email):
    assert _EMAIL_RE.match(email) is not None


@pytest.mark.parametrize("email", [
    "",
    "user",
    "@domain",
    "user@",
    "user @mail.ru",
    "user@.com",
    "@",
])
def test_invalid_emails(email):
    assert _EMAIL_RE.match(email) is None
