from src.core.entities import User, Keyword
from src.core.interfaces import IUserRepository

class ManageUsersUseCase:
    def __init__(self, user_repo: IUserRepository):
        self.user_repo = user_repo

    async def register_or_update_user(self, tg_id: int, email: str = None) -> User:
        user = await self.user_repo.get_by_telegram_id(tg_id)
        if not user:
            user = User(telegram_id=tg_id, email=email)
        else:
            if email:
                user.email = email
        
        await self.user_repo.save_user(user)
        return await self.user_repo.get_by_telegram_id(tg_id)

    async def add_trigger_word(self, tg_id: int, word: str):
        # TODO: Добавить проверку, существует ли уже слово
        await self.user_repo.add_keyword(tg_id, Keyword(word=word, is_stop_word=False))

    async def get_user_profile(self, tg_id: int) -> User:
        return await self.user_repo.get_by_telegram_id(tg_id)