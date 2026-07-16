"""
Генерация партнёрской ссылки на товар.

Приоритет источников:
1. Admitad — если заданы ADMITAD_TOKEN + ADMITAD_WEBSITE_ID + ADMITAD_CAMPAIGN_ID,
   вызываем реальный публичный Deeplink API:
   https://developers.admitad.com/en/doc/api_en/methods/deeplink/deeplink/
2. Getblogger — у площадки НЕТ публичного API для автогенерации ссылок (в отличие от Admitad):
   она выдаёт персональную ссылку/промокод вручную под конкретный согласованный оффер.
   Поэтому здесь просто ищем совпадение в справочнике GETBLOGGER_LINKS из config.py —
   туда нужно вручную вписать уже выданные вам ссылки.
3. Если ничего не настроено или обе попытки не сработали — возвращаем ИСХОДНУЮ обычную
   ссылку без изменений. Это штатный режим для самых первых постов, пока CPA-сети ещё
   не подключены: посты выходят с обычными ссылками, ничего не падает и не блокируется.
"""
import requests
from config import ADMITAD_TOKEN, ADMITAD_WEBSITE_ID, ADMITAD_CAMPAIGN_ID, GETBLOGGER_LINKS


def _try_admitad(target_url: str) -> str | None:
    if not (ADMITAD_TOKEN and ADMITAD_WEBSITE_ID and ADMITAD_CAMPAIGN_ID):
        return None
    try:
        resp = requests.get(
            f"https://api.admitad.com/deeplink/{ADMITAD_WEBSITE_ID}/advcampaign/{ADMITAD_CAMPAIGN_ID}/",
            params={"ulp": target_url},
            headers={"Authorization": f"Bearer {ADMITAD_TOKEN}"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()  # Admitad возвращает СПИСОК ссылок в том же порядке, что и ulp
        if isinstance(data, list) and data:
            return data[0]
        print(f"[affiliate_links] Admitad вернул неожиданный формат ответа: {data}")
        return None
    except Exception as e:
        print(f"[affiliate_links] Admitad недоступен/ошибка запроса: {e}")
        return None


def _try_getblogger(target_url: str) -> str | None:
    # Публичного API нет — просто смотрим, не выдавали ли вам уже ссылку под этот URL вручную.
    return GETBLOGGER_LINKS.get(target_url)


def generate_deeplink(target_url: str, prefer: str = "admitad") -> str:
    """
    prefer: "admitad" или "getblogger" — какой источник пробовать первым.
    Если ни один источник не настроен или не дал результата — возвращает исходную
    ссылку без изменений, ничего не ломая в пайплайне.
    """
    tryers = {"admitad": _try_admitad, "getblogger": _try_getblogger}
    order = [prefer] + [name for name in tryers if name != prefer]

    for name in order:
        link = tryers[name](target_url)
        if link:
            print(f"[affiliate_links] Использована ссылка от {name}")
            return link

    print("[affiliate_links] Ни одна CPA-сеть не настроена/не сработала — "
          "публикую обычную (не реферальную) ссылку")
    return target_url


def format_disclosure(text: str) -> str:
    """Добавляет обязательную маркировку рекламы к посту (требование законодательства РФ)."""
    return f"{text}\n\n#реклама\nПартнёрский материал."
