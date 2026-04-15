from aiogram.fsm.state import StatesGroup, State

class UserSettingsStates(StatesGroup):
    waiting_for_email = State()
    waiting_for_keyword = State()
    waiting_for_link_email = State()
    waiting_for_link_code = State()
