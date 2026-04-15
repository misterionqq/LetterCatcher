import hashlib
import hmac
import time

from src.infrastructure.telegram_auth import verify_telegram_login

BOT_TOKEN = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"


def _make_login_data(**overrides):
    """Build valid Telegram Login Widget data and compute a correct hash."""
    data = {
        "id": "12345678",
        "first_name": "John",
        "username": "johndoe",
        "auth_date": str(int(time.time())),
    }
    data.update(overrides)

    # Compute correct hash
    filtered = {k: v for k, v in data.items() if k != "hash" and v}
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(filtered.items()))
    secret = hashlib.sha256(BOT_TOKEN.encode()).digest()
    correct_hash = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    data["hash"] = correct_hash
    return data


def test_valid_login():
    data = _make_login_data()
    assert verify_telegram_login(data, BOT_TOKEN) is True


def test_missing_hash():
    data = _make_login_data()
    del data["hash"]
    assert verify_telegram_login(data, BOT_TOKEN) is False


def test_wrong_hash():
    data = _make_login_data()
    data["hash"] = "0" * 64
    assert verify_telegram_login(data, BOT_TOKEN) is False


def test_tampered_data():
    data = _make_login_data()
    data["first_name"] = "Hacker"  # tamper after hash computed
    assert verify_telegram_login(data, BOT_TOKEN) is False


def test_expired_auth_date():
    old_time = str(int(time.time()) - 100000)  # > 86400 seconds ago
    data = _make_login_data(auth_date=old_time)
    assert verify_telegram_login(data, BOT_TOKEN) is False


def test_custom_max_age():
    one_hour_ago = str(int(time.time()) - 3600)
    data = _make_login_data(auth_date=one_hour_ago)
    # Within default 86400 max_age
    assert verify_telegram_login(data, BOT_TOKEN) is True
    # But exceeds a 1800-second max_age
    assert verify_telegram_login(data, BOT_TOKEN, max_age_seconds=1800) is False


def test_missing_auth_date():
    data = _make_login_data()
    del data["auth_date"]
    # hash was computed WITH auth_date, so it will be invalid anyway
    assert verify_telegram_login(data, BOT_TOKEN) is False


def test_invalid_auth_date():
    data = _make_login_data(auth_date="not-a-number")
    assert verify_telegram_login(data, BOT_TOKEN) is False


def test_wrong_bot_token():
    data = _make_login_data()
    assert verify_telegram_login(data, "wrong-token") is False


def test_optional_fields_empty():
    """Telegram omits empty optional fields from the hash calculation."""
    data = _make_login_data(first_name="", username="", photo_url="")
    assert verify_telegram_login(data, BOT_TOKEN) is True
