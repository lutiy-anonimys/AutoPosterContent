"""
Генерация новых тем для статей на основе ниши и списка уже использованных тем
(чтобы ИИ не повторялся). Использует тот же Polza.ai API, что и content_generator.py.
"""
import json
import re
import requests
from config import POLZA_API_KEY, POLZA_BASE_URL, POLZA_MODEL, NICHE_NAME, NICHE_DESCRIPTION, TOPICS


def _extract_json_array(text: str) -> list:
    """Достаёт JSON-массив из ответа модели, даже если он обёрнут в ```json ... ```."""
    cleaned = text.replace("```json", "").replace("```", "").strip()
    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if not match:
        raise ValueError(f"В ответе модели не найден JSON-массив: {text[:200]}")
    return json.loads(match.group(0))


def generate_new_topics(used_topics: list, batch_size: int = 8) -> list:
    """
    Возвращает список новых уникальных тем-заголовков (строк) для ниши,
    которых нет среди used_topics.
    """
    if not POLZA_API_KEY:
        raise ValueError("[topic_generator] Не задан POLZA_API_KEY")

    # Показываем модели последние ~40 использованных тем, чтобы не раздувать промпт
    recent_used = used_topics[-40:]

    system_prompt = (
        f"Ты — контент-стратег блога «{NICHE_NAME}». Ниша: {NICHE_DESCRIPTION}\n\n"
        "Придумывай заголовки статей в стиле, который хорошо заходит в Яндекс.Дзен и "
        "содержит ключевые слова, которые люди реально вбивают в поиск "
        "(например: 'органайзер для кухни', 'находки для дома', 'постельное белье купить', "
        "'хранение вещей маленькая квартира').\n\n"
        "Требования к заголовкам:\n"
        "1. Обещают конкретную пользу или решение проблемы читателя.\n"
        "2. Не повторяют по смыслу уже использованные темы (список ниже).\n"
        "3. Разные подтемы: не зацикливайся только на кухне — бери спальню, ванную, "
        "прихожую, детскую, балкон, рабочее место дома и т.д.\n"
        "4. Без выдуманных точных цифр вроде 'до 500 рублей', если это не общая оценка сегмента.\n\n"
        "Ответ верни СТРОГО в виде JSON-массива строк, без markdown, без пояснений. "
        'Пример: ["Заголовок 1", "Заголовок 2"]'
    )

    user_prompt = (
        f"Уже использованные темы (не повторять):\n- " + "\n- ".join(recent_used)
        + f"\n\nПридумай {batch_size} новых уникальных тем."
    )

    resp = requests.post(
        f"{POLZA_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {POLZA_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": POLZA_MODEL,
            "temperature": 0.9,  # больше разнообразия для тем
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()

    try:
        raw_text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"[topic_generator] Неожиданный формат ответа Polza.ai: {data}") from e

    topics = _extract_json_array(raw_text)
    topics = [t.strip() for t in topics if isinstance(t, str) and t.strip()]

    # На всякий случай ещё раз фильтруем точные дубли с уже использованными
    used_lower = {t.lower() for t in used_topics}
    topics = [t for t in topics if t.lower() not in used_lower]

    if not topics:
        raise RuntimeError("[topic_generator] Модель не вернула ни одной новой темы")

    return topics


def load_topics_pool(path: str) -> dict:
    """Структура: {"used": [...], "pending": [...]}"""
    import os
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                pool = json.load(f)
                pool.setdefault("used", [])
                pool.setdefault("pending", [])
                return pool
        except Exception as e:
            print(f"[topic_generator] Не удалось прочитать пул тем ({e}), начинаю заново")
    # При первом запуске pending = seed-темы из config.py
    return {"used": [], "pending": list(TOPICS)}


def save_topics_pool(path: str, pool: dict) -> None:
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(pool, f, ensure_ascii=False, indent=2)


def get_next_topic(path: str, refill_batch: int, refill_threshold: int) -> tuple[str, dict]:
    """
    Возвращает (тема, обновлённый_пул). Если pending почти закончился —
    сначала пытается пополнить его через generate_new_topics; при ошибке ИИ
    (например, нет ключа или сеть недоступна) откатывается на seed-темы из config.py,
    чтобы пайплайн не падал целиком из-за временной проблемы с генерацией тем.
    """
    pool = load_topics_pool(path)

    if len(pool["pending"]) <= refill_threshold:
        try:
            new_topics = generate_new_topics(pool["used"] + pool["pending"], batch_size=refill_batch)
            pool["pending"].extend(new_topics)
            print(f"[topic_generator] Добавлено {len(new_topics)} новых тем в пул")
        except Exception as e:
            print(f"[topic_generator] Не удалось сгенерировать новые темы ({e}), "
                  f"использую seed-темы из config.py как запасной вариант")
            fallback = [t for t in TOPICS if t not in pool["used"] and t not in pool["pending"]]
            pool["pending"].extend(fallback)

    if not pool["pending"]:
        # совсем крайний случай — пул и seed-темы исчерпаны
        pool["pending"] = list(TOPICS)

    topic = pool["pending"].pop(0)
    pool["used"].append(topic)
    pool["used"] = pool["used"][-200:]  # не даём файлу расти бесконечно

    return topic, pool
