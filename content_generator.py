"""
Генерация текста статьи через Polza.ai (OpenAI-совместимый API: https://polza.ai/docs).
Заодно просим модель предложить короткий поисковый запрос (product_query) для
автоматического поиска подходящего реального товара на маркетплейсе (см. product_finder.py) —
это убирает необходимость вручную вести список ссылок на товары.

Не забывайте: сгенерированный текст обязательно проверяйте перед публикацией —
модель может ошибиться в характеристиках товара или деталях.
"""
import re
import requests
from config import POLZA_API_KEY, POLZA_BASE_URL, POLZA_MODEL

SYSTEM_PROMPT = (
    "Ты — автор блога о выгодных покупках и обзорах товаров для Яндекс.Дзен. "
    "Пиши живым, разговорным языком («делюсь личной находкой», «проверено на себе»), "
    "без выдуманных фактов и точных цен — используй общие формулировки "
    "('в среднем ценовом сегменте', 'стоит бюджетно' и т.п.), т.к. цены быстро устаревают "
    "и указывать неточные цифры вводит читателя в заблуждение.\n\n"
    "Структурируй текст: подзаголовки <h2>, списки <ul><li>, важные мысли — <b>жирным</b>. "
    "Статья должна быть не короче заданного объёма.\n\n"
    "В конце статьи ВСЕГДА добавляй абзац: 'Материал носит информационный характер. "
    "Ссылки на товары являются партнёрскими (реклама).'\n\n"
    "Ответ верни СТРОГО в следующем формате, каждая часть на отдельной строке "
    "с указанным префиксом (без markdown, без кавычек, без пояснений от себя):\n"
    "TITLE: <заголовок статьи с интригой или пользой>\n"
    "KEYWORD: <короткий поисковый запрос из 2-4 слов для поиска ОДНОГО конкретного вида "
    "товара на маркетплейсе, который лучше всего подходит к теме статьи — "
    "например 'органайзер для холодильника' или 'постельное белье сатин'>\n"
    "BODY:\n<текст статьи простым HTML — только <p>, <h2>, <ul>, <li>, <b>>"
)


def _parse_response(full_text: str) -> dict:
    full_text = full_text.replace("```html", "").replace("```", "").strip()

    title_m = re.search(r"TITLE:\s*(.+)", full_text)
    keyword_m = re.search(r"KEYWORD:\s*(.+)", full_text)
    body_m = re.search(r"BODY:\s*(.*)", full_text, re.DOTALL)

    title = title_m.group(1).strip() if title_m else full_text.split("\n", 1)[0].strip()
    product_query = keyword_m.group(1).strip() if keyword_m else ""
    body_html = body_m.group(1).strip() if body_m else full_text

    return {"title": title, "product_query": product_query, "body_html": body_html}


def generate_article(topic: str, min_words: int = 400) -> dict:
    """
    Возвращает dict: {"title": str, "product_query": str, "body_html": str, "body_plain": str}
    product_query может быть пустой строкой, если модель не вернула её в ожидаемом формате —
    это нужно обработать при вызове (main.py откатывается на PRODUCT_URLS_POOL/тему).
    """
    if not POLZA_API_KEY:
        raise ValueError("[content_generator] Не задан POLZA_API_KEY (см. GitHub Secrets)")

    resp = requests.post(
        f"{POLZA_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {POLZA_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": POLZA_MODEL,
            "temperature": 0.7,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Напиши статью на тему: «{topic}». Минимум {min_words} слов.",
                },
            ],
        },
        timeout=60,
    )
    if resp.status_code >= 400:
        # Показываем тело ответа в логах — иначе raise_for_status() скрывает причину
        # (например, неверный формат model, нехватка баланса, невалидный ключ и т.п.)
        print(f"[content_generator] Polza.ai вернул {resp.status_code}: {resp.text[:500]}")
    resp.raise_for_status()
    data = resp.json()

    try:
        full_text = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"[content_generator] Неожиданный формат ответа Polza.ai: {data}") from e

    if not full_text:
        raise RuntimeError("[content_generator] Пустой ответ от модели")

    article = _parse_response(full_text)

    # Plain-версия для Telegram (там ограниченный набор HTML-тегов)
    body_plain = article["body_html"]
    body_plain = re.sub(r"<h2>(.*?)</h2>", r"\n<b>\1</b>\n", body_plain)
    body_plain = body_plain.replace("<p>", "").replace("</p>", "\n")
    body_plain = body_plain.replace("<ul>", "").replace("</ul>", "")
    body_plain = body_plain.replace("<li>", "• ").replace("</li>", "\n")
    body_plain = re.sub("<[^<]+?>", "", body_plain).strip()
    article["body_plain"] = body_plain

    return article