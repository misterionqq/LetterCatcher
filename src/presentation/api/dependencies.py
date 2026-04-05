from src.use_cases.manage_users import ManageUsersUseCase
from src.use_cases.mail_scanner import MailScanner

_user_use_case: ManageUsersUseCase | None = None
_scanner: MailScanner | None = None


def set_user_use_case(uc: ManageUsersUseCase) -> None:
    global _user_use_case
    _user_use_case = uc


def get_user_use_case() -> ManageUsersUseCase:
    assert _user_use_case is not None, "user_use_case not initialized"
    return _user_use_case


def set_scanner(s: MailScanner) -> None:
    global _scanner
    _scanner = s


def get_scanner() -> MailScanner | None:
    return _scanner
