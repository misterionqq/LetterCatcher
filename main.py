import sys
from src.infrastructure.config import IMAP_SERVER, EMAIL_USER, EMAIL_PASSWORD
from src.infrastructure.imap_client import ImapEmailRepository
from src.use_cases.check_email import CheckEmailUseCase

def main():
    repo = ImapEmailRepository(
        imap_server=IMAP_SERVER,
        email_user=EMAIL_USER,
        email_password=EMAIL_PASSWORD
    )

    use_case = CheckEmailUseCase(repository=repo)

    print("Проверка почтового ящика...")
    try:
        emails = use_case.execute()
        
        if not emails:
            print("Новых непрочитанных писем нет.")
        else:
            print(f"Найдено писем: {len(emails)}\n")
            for mail in emails:
                print(f"[{mail.uid}] От: {mail.sender}")
                print(f"Тема: {mail.subject}")
                print(f"Текст (первые 100 символов): {mail.body[:100]}...")
                print("-" * 40)

    except Exception as e:
        print(f"Критическая ошибка: {e}")

if __name__ == "__main__":
    main()