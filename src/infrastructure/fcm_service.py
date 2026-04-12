import asyncio
import logging
from typing import List

from src.infrastructure.config import FIREBASE_CREDENTIALS_PATH

_app = None


def _init_firebase():
    global _app
    if _app is not None:
        return True
    if not FIREBASE_CREDENTIALS_PATH:
        return False
    try:
        import firebase_admin
        from firebase_admin import credentials
        cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
        _app = firebase_admin.initialize_app(cred)
        logging.info("Firebase Admin SDK initialized")
        return True
    except Exception as e:
        logging.warning(f"Firebase init failed: {e}")
        return False


async def send_push(tokens: List[str], title: str, body: str, data: dict = None):
    """Send FCM push to a list of device tokens. Skips silently if Firebase is not configured."""
    if not tokens or not _init_firebase():
        return

    from firebase_admin import messaging

    def _send_all():
        removed = []
        for token in tokens:
            message = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                data={k: str(v) for k, v in (data or {}).items()},
                token=token,
            )
            try:
                messaging.send(message)
            except messaging.UnregisteredError:
                removed.append(token)
                logging.info(f"FCM token unregistered, will remove: {token[:20]}...")
            except Exception as e:
                logging.error(f"FCM send error: {e}")
        return removed

    return await asyncio.to_thread(_send_all)
