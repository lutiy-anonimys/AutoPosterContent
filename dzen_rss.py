"""
Официальный способ автопубликации в Дзен — размеченная RSS-лента,
которую вы ОДИН РАЗ подключаете вручную в Дзен-Студии
(Настройки канала -> Способы публикации -> RSS).
Требования Дзена к формату ленты (обязательные поля, размер картинок и т.д.):
https://dzen.ru/help/ru/website/rss-modify.html

Важные нюансы, о которых пишет сам Дзен:
- лента должна содержать минимум 10 материалов при первом подключении;
- сайт должен быть реально доступен и не закрыт в robots.txt для юзер-агента Mail.ru;
- изменения в статье, отправленной через RSS, подхватываются только в течение 7 дней;
- у некоторых новых/маленьких сайтов Дзен в 2025-2026 гг. может требовать
  минимальный трафик перед подключением RSS — уточняйте актуальные условия в Студии,
  т.к. это могло измениться.

Этот скрипт только СОБИРАЕТ валидный XML-файл. Разместить его по стабильному
публичному URL (например через GitHub Pages) и подключить в Студии — отдельный,
разовый шаг руками.
"""
import os
import html
from datetime import datetime, timezone
from email.utils import format_datetime

from config import ARTICLES_DIR, RSS_FEED_PATH, SITE_BASE_URL


def save_article_html(slug: str, title: str, body_html: str) -> str:
    os.makedirs(ARTICLES_DIR, exist_ok=True)
    path = os.path.join(ARTICLES_DIR, f"{slug}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"<html><head><title>{html.escape(title)}</title></head>"
                f"<body><h1>{html.escape(title)}</h1>{body_html}</body></html>")
    return path


def rebuild_feed(articles: list[dict]) -> str:
    """
    articles: список dict с ключами: slug, title, body_html, guid, pub_date (datetime), image_url (опц.)
    Дзен требует минимум 10 материалов в ленте при первом подключении — накапливайте их,
    не перезаписывайте только последним постом.
    """
    items_xml = []
    for a in articles:
        pub_date = format_datetime(a.get("pub_date", datetime.now(timezone.utc)))
        link = f"{SITE_BASE_URL}/{ARTICLES_DIR}/{a['slug']}.html"
        image_block = (
            f'<enclosure url="{html.escape(a["image_url"])}" type="image/jpeg"/>'
            if a.get("image_url") else ""
        )
        items_xml.append(f"""
    <item>
      <title>{html.escape(a['title'])}</title>
      <link>{link}</link>
      <guid isPermaLink="false">{html.escape(a['guid'])}</guid>
      <pubDate>{pub_date}</pubDate>
      <description><![CDATA[{a['body_html']}]]></description>
      {image_block}
    </item>""")

    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>Мой блог о выгодных покупках</title>
    <link>{SITE_BASE_URL}</link>
    <description>Обзоры и подборки товаров</description>
    {''.join(items_xml)}
  </channel>
</rss>"""

    os.makedirs(os.path.dirname(RSS_FEED_PATH), exist_ok=True)
    with open(RSS_FEED_PATH, "w", encoding="utf-8") as f:
        f.write(feed)
    return RSS_FEED_PATH
