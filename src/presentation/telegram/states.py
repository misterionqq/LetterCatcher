from aiogram.fsm.state import StatesGroup, State

class UserSettingsStates(StatesGroup):
    waiting_for_keyword = State()