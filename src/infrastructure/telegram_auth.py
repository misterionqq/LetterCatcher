import hashlib
import hmac
import time


def verify_telegram_login(data: dict, bot_token: str, max_age_seconds: int = 86400) -> bool:
    """
    Validate Telegram Login Widget data using HMAC-SHA256.

    Per https://core.telegram.org/widgets/login#checking-authorization
    """
    check_hash = data.get("hash")
    if not check_hash:
        return False

    auth_date = data.get("auth_date")
    if not auth_date:
        return False
    try:
        if (time.time() - int(auth_date)) > max_age_seconds:
            return False
    except (ValueError, TypeError):
        return False

    filtered = {k: v for k, v in data.items() if k != "hash" and v}
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(filtered.items()))

    secret_key = hashlib.sha256(bot_token.encode()).digest()
    computed = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    return hmac.compare_digest(computed, check_hash)
