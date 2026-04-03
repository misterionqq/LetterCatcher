from src.use_cases.manage_users import ManageUsersUseCase

_user_use_case: ManageUsersUseCase | None = None


def set_user_use_case(uc: ManageUsersUseCase) -> None:
    global _user_use_case
    _user_use_case = uc


def get_user_use_case() -> ManageUsersUseCase:
    assert _user_use_case is not None, "user_use_case not initialized"
    return _user_use_case
