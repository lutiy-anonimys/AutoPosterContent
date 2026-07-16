"""
Автоматический поиск реальных товаров на Wildberries под тему статьи — чтобы не вести
вручную список ссылок (PRODUCT_URLS_POOL). Используем поисковый запрос, который для
каждой статьи генерирует сам ИИ (см. content_generator.py, поле "product_query").

ВАЖНО про используемый эндпоинт (search.wb.ru):
- Это тот же внутренний поисковый запрос, который делает сам сайт wildberries.ru,
  когда посетитель ищет товар в браузере — то есть данные публичные, без авторизации
  и без обхода каких-либо ограничений доступа, доступны любому посетителю сайта.
- Тем не менее это НЕофициально документированный API: Wildberries может поменять
  формат ответа без предупреждения — тогда парсинг ниже сломается, и его нужно будет
  поправить под новый формат.
- Не стоит дёргать его слишком часто/агрессивно — при запуске раз в несколько часов
  (как в текущем cron) это не проблема, но не превращайте это в цикл из сотен запросов.
- Официальная и более устойчивая альтернатива, если захотите её отдельно внедрить, —
  партнёрские товарные фиды CPA-сетей (например, у части офферов в Admitad есть
  готовый product feed по конкретному рекламодателю) — тогда не нужен и сам парсинг WB.
"""
import requests

WB_SEARCH_URL = "https://search.wb.ru/exactmatch/ru/common/v4/search"


def find_products(query: str, limit: int = 5) -> list:
    """
    Возвращает список товаров: [{"name": str, "price_rub": float|None, "url": str}, ...],
    отсортированных так же, как их отдаёт WB (sort=popular).
    Пустой список, если ничего не найдено или запрос не удался — тогда main.py
    должен откатиться на PRODUCT_URLS_POOL или на ссылку поиска.
    """
    try:
        resp = requests.get(
            WB_SEARCH_URL,
            params={
                "appType": 1,
                "curr": "rub",
                "dest": -1257786,  # регион по умолчанию (Москва); можно уточнить под свою аудиторию
                "page": 1,
                "query": query,
                "resultset": "catalog",
                "sort": "popular",
                "spp": 30,
            },
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://www.wildberries.ru/",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        products = data.get("data", {}).get("products", [])[:limit]

        results = []
        for p in products:
            product_id = p.get("id")
            if not product_id:
                continue
            price_kopecks = p.get("salePriceU") or p.get("priceU")
            results.append({
                "name": p.get("name", ""),
                "price_rub": (price_kopecks / 100) if price_kopecks else None,
                "url": f"https://www.wildberries.ru/catalog/{product_id}/detail.aspx",
            })
        return results
    except Exception as e:
        print(f"[product_finder] Не удалось получить товары для запроса '{query}': {e}")
        return []
