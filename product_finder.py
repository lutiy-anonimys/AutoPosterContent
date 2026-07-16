import os
import urllib.parse
import requests


WB_SEARCH_URL = "https://search.wb.ru/exactmatch/ru/common/v4/search"


def find_products(query: str, limit: int = 5) -> list:
    results = []

    proxy_url = os.environ.get("PROXY_URL", "").strip()

    proxies = None

    if proxy_url:
        proxies = {
            "http": proxy_url,
            "https": proxy_url,
        }

        print("[product_finder] Проверяем прокси...")

        try:
            ip_response = requests.get(
                "https://api.ipify.org?format=json",
                proxies=proxies,
                timeout=10,
            )

            print(
                "[product_finder] IP:",
                ip_response.json().get("ip")
            )

        except Exception as e:
            print("[product_finder] Ошибка проверки прокси:", repr(e))

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ru-RU,ru;q=0.9",
    }

    try:
        params = {
            "appType": 1,
            "curr": "rub",
            "dest": -1257786,
            "page": 1,
            "query": query,
            "resultset": "catalog",
            "sort": "popular",
            "spp": 0,
            "suppressSpellcheck": "false",
        }

        resp = requests.get(
            WB_SEARCH_URL,
            params=params,
            headers=headers,
            proxies=proxies,
            timeout=20,
        )

        print("[WB] URL:", resp.url)
        print("[WB] Status:", resp.status_code)
        print("[WB] Content-Type:", resp.headers.get("content-type"))

        if resp.status_code != 200:
            print("[WB] Ответ сервера:")
            print(resp.text[:2000])

        resp.raise_for_status()

        data = resp.json()

        products = (
            data
            .get("data", {})
            .get("products", [])
        )

        print("[WB] Найдено товаров:", len(products))

        for product in products[:limit]:

            product_id = product.get("id")

            if not product_id:
                continue

            price_kopecks = (
                product.get("salePriceU")
                or product.get("priceU")
            )

            results.append({
                "name": product.get("name", "Без названия"),
                "price_rub": (
                    price_kopecks / 100
                    if price_kopecks is not None
                    else None
                ),
                "url": (
                    f"https://www.wildberries.ru/catalog/"
                    f"{product_id}/detail.aspx"
                ),
            })

    except requests.exceptions.ProxyError as e:
        print("[WB] Ошибка прокси:", repr(e))

    except requests.exceptions.Timeout as e:
        print("[WB] Таймаут:", repr(e))

    except requests.exceptions.HTTPError as e:
        print("[WB] HTTP ошибка:", repr(e))

    except requests.exceptions.JSONDecodeError as e:
        print("[WB] WB вернул не JSON:", repr(e))
        print(resp.text[:2000])

    except Exception as e:
        print("[WB] Неизвестная ошибка:", repr(e))

    # Ozon
    encoded_query = urllib.parse.quote_plus(query)

    results.append({
        "name": f"Поиск товаров '{query}' на Ozon",
        "price_rub": None,
        "url": (
            f"https://www.ozon.ru/search/"
            f"?text={encoded_query}&from_global=true"
        ),
    })

    return results
