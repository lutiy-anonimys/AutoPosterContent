"""
Точка входа. Запускается GitHub Actions по расписанию (см. .github/workflows/autopost.yml).

Пайплайн:
1. Берём тему из ротации.
2. Генерируем статью через Polza.ai.
3. Генерируем партнёрскую ссылку на товар (подставьте свои реальные ссылки).
4. Публикуем короткую версию в Telegram.
5. Добавляем статью в историю публикаций (output/history.json) и пересобираем
   RSS-ленту из последних N статей — Дзену нужно минимум 10 материалов в ленте.
"""
import random
import re
import uuid
import json
import os
from datetime import datetime, timezone

from config import TOPICS, TOPICS_POOL_FILE, TOPICS_REFILL_BATCH, TOPICS_REFILL_THRESHOLD, PRODUCT_URLS_POOL
from content_generator import generate_article
from affiliate_links import generate_deeplink, format_disclosure
from telegram_poster import post_to_telegram
from dzen_rss import save_article_html, rebuild_feed
from topic_generator import get_next_topic, save_topics_pool
from product_finder import find_products

HISTORY_FILE = "output/history.json"
HISTORY_LIMIT = 20  # сколько последних статей держим в RSS-ленте


def slugify(title: str) -> str:
    s = re.sub(r"[^a-zA-Zа-яА-Я0-9]+", "-", title.lower()).strip("-")
    return s[:60] or uuid.uuid4().hex[:8]


def pick_product_link(product_query: str, topic: str) -> tuple:
    """
    Возвращает (url, product_name|None). Три уровня фолбэка:
    1. Автопоиск реального товара на Wildberries по product_query от ИИ (см. product_finder.py).
    2. Если поиск ничего не дал — берём случайную ссылку из PRODUCT_URLS_POOL, если он не пуст.
    3. Если и его нет — даём прямую ссылку на страницу поиска WB по теме (не идеально,
       но лучше, чем упасть или публиковать пост совсем без ссылки).
    """
    if product_query:
        products = find_products(product_query, limit=5)
        if products:
            top = products[0]
            print(f"[main] Найден товар автоматически: {top['name']}")
            return top["url"], top["name"]

    if PRODUCT_URLS_POOL:
        print("[main] Автопоиск не дал результата — беру ссылку из PRODUCT_URLS_POOL")
        return random.choice(PRODUCT_URLS_POOL), None

    from urllib.parse import quote
    search_url = f"https://www.wildberries.ru/catalog/0/search.aspx?search={quote(product_query or topic)}"
    print("[main] Автопоиск и PRODUCT_URLS_POOL пусты — публикую ссылку на страницу поиска WB")
    return search_url, None


def load_history() -> list:
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[main] Не удалось прочитать историю ({e}), начинаю с чистого листа")
            return []
    return []


def save_history(history: list) -> None:
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def run_once():
    history = load_history()

    topic, topics_pool = get_next_topic(
        TOPICS_POOL_FILE, TOPICS_REFILL_BATCH, TOPICS_REFILL_THRESHOLD
    )
    print(f"[main] Тема: {topic}")
    print(f"[main] Тем в очереди осталось: {len(topics_pool['pending'])}")

    article = generate_article(topic)
    slug = slugify(article["title"])

    raw_link, product_name = pick_product_link(article.get("product_query", ""), topic)
    aff_link = generate_deeplink(raw_link)

    preview = article["body_plain"][:700]
    product_line = f"🛍️ {product_name}\n\n" if product_name else ""
    telegram_text = (
        f"✍️ <b>{article['title']}</b>\n\n"
        f"{preview}...\n\n"
        f"{product_line}"
        f'👉 <a href="{aff_link}">Смотреть предложение</a>'
    )
    telegram_text = format_disclosure(telegram_text)

    ok = post_to_telegram(telegram_text)
    print(f"[main] Публикация в Telegram: {'успех' if ok else 'ошибка'}")

    save_article_html(slug, article["title"], article["body_html"])

    # Добавляем новую статью в начало истории, убираем дубли по slug, ограничиваем размер
    new_entry = {
        "slug": slug,
        "title": article["title"],
        "body_html": article["body_html"],
        "guid": slug,
        "pub_date": datetime.now(timezone.utc).isoformat(),
    }
    history = [item for item in history if item["slug"] != slug]
    history.insert(0, new_entry)
    history = history[:HISTORY_LIMIT]
    save_history(history)

    # Пересобираем RSS-ленту из накопленной истории (а не из одной последней статьи)
    formatted_articles = []
    for item in history:
        item_copy = item.copy()
        item_copy["pub_date"] = datetime.fromisoformat(item["pub_date"])
        formatted_articles.append(item_copy)

    rebuild_feed(formatted_articles)
    print(f"[main] RSS-лента обновлена, статей в ленте: {len(formatted_articles)}")

    # Пул тем сохраняем только после успешного прохода пайплайна: если что-то упадёт выше
    # (например, ошибка генерации статьи), тема останется в очереди и попробуется в следующий раз.
    save_topics_pool(TOPICS_POOL_FILE, topics_pool)


if __name__ == "__main__":
    run_once()
