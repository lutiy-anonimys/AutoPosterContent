import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID


def post_to_telegram(text: str, photo_url: str | None = None) -> bool:
    """
    Публикует пост в канал. Если передан photo_url — фото с подписью (caption),
    иначе — обычное текстовое сообщение.
    Возвращает True/False по успеху, чтобы вызывающий код мог логировать ошибки.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        print("[telegram_poster] Не заданы TELEGRAM_BOT_TOKEN / TELEGRAM_CHANNEL_ID")
        return False

    base = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

    try:
        if photo_url:
            # caption у Telegram ограничен 1024 символами
            caption = text[:1000]
            resp = requests.post(
                f"{base}/sendPhoto",
                json={
                    "chat_id": TELEGRAM_CHANNEL_ID,
                    "photo": photo_url,
                    "caption": caption,
                    "parse_mode": "HTML",
                },
                timeout=20,
            )
        else:
            resp = requests.post(
                f"{base}/sendMessage",
                json={
                    "chat_id": TELEGRAM_CHANNEL_ID,
                    "text": text[:4000],
                    "parse_mode": "HTML",
                    "disable_web_page_preview": False,
                },
                timeout=20,
            )
        resp.raise_for_status()
        ok = resp.json().get("ok", False)
        if not ok:
            print(f"[telegram_poster] Telegram API вернул ошибку: {resp.text}")
        return ok
    except Exception as e:
        print(f"[telegram_poster] Ошибка отправки: {e}")
        return False
