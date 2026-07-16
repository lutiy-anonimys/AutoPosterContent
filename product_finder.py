"""
Автоматический поиск реальных товаров на Wildberries и Ozon под тему статьи — чтобы не вести
вручную список ссылок (PRODUCT_URLS_POOL). Используем поисковый запрос, который для
каждой статьи генерирует сам ИИ (см. content_generator.py, поле "product_query").

ВАЖНО про используемый эндпоинт Wildberries (search.wb.ru):
- Это тот же внутренний поисковый запрос, который делает сам сайт wildberries.ru.
- Запросы идут через прокси-сервер (если задана переменная PROXY_URL в Secrets), чтобы избежать ошибки 429.
- Для Ozon генерируется прямая поисковая ссылка, так как у Ozon агрессивная защита от парсинга API.
"""
import os
import urllib.parse
import requests

WB_SEARCH_URL = "https://search.wb.ru/exactmatch/ru/common/v4/search"


def find_products(query: str, limit: int = 5) -> list:
    """
    Возвращает список товаров с Wildberries и Ozon:
    [{"name": str, "price_rub": float|None, "url": str}, ...]

    Сначала пытается найти конкретные товары на Wildberries через API с использованием прокси.
    Затем добавляет в выдачу общую поисковую ссылку на Ozon по этому же запросу.
    """
    results = []

    # --- Настройка прокси (берем из GitHub Secrets) ---
    proxy_url = os.environ.get("PROXY_URL", "").strip()
    
    # Формируем словарь прокси для requests
    proxies = {
        "http": proxy_url,
        "https": proxy_url
    } if proxy_url else None

    if proxy_url:
        print("[product_finder] Запросы отправляются через прокси")
        try:
            ip_check = requests.get("https://api.ipify.org?format=json", proxies=proxies, timeout=5).json()
            print(f"[product_finder] Внешний IP через прокси: {ip_check.get('ip')}")
        except Exception as check_err:
            print(f"[product_finder] Предупреждение: не удалось проверить IP через прокси: {check_err}")
    else:
        print("[product_finder] Предупреждение: PROXY_URL не задан, запросы идут напрямую")

    # --- ЧАСТЬ 1. Поиск конкретных товаров на Wildberries ---
    try:
        # Эмулируем абсолютно чистый и полный набор заголовков современного браузера Chrome
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "*/*",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Origin": "https://www.wildberries.ru",
            "Referer": "https://www.wildberries.ru/",
            "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
        }

        resp = requests.get(
            WB_SEARCH_URL,
            params={
                "appType": 1,
                "curr": "rub",
                "dest": -1257786,  # регион по умолчанию (Москва)
                "page": 1,
                "query": query,
                "resultset": "catalog",
                "sort": "popular",
                "spp": 30,
            },
            headers=headers,
            proxies=proxies,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        products = data.get("data", {}).get("products", [])[:limit]

        for p in products:
            product_id = p.get("id")
            if not product_id:
                continue
            price_kopecks = p.get("salePriceU") or p.get("priceU")
            results.append({
                "name": f"{p.get('name', '')} (Wildberries)",
                "price_rub": (price_kopecks / 100) if price_kopecks else None,
                "url": f"https://www.wildberries.ru/catalog/{product_id}/detail.aspx",
            })
    except Exception as e:
        print(f"[product_finder] Не удалось получить конкретные товары с Wildberries для запроса '{query}': {e}")

    # --- ЧАСТЬ 2. Добавление поиска на Ozon ---
    try:
        encoded_query = urllib.parse.quote(query)
        ozon_search_url = f"https://www.ozon.ru/search/?text={encoded_query}&from_global=true"
        
        results.append({
            "name": f"Поиск товаров '{query}' на Ozon",
            "price_rub": None,
            "url": ozon_search_url
        })
    except Exception as e:
        print(f"[product_finder] Ошибка при генерации ссылки Ozon: {e}")

    return results
