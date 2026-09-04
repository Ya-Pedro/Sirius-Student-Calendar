"""
Тестовый скрипт для исследования Livewire API schedule.siriusuniversity.ru.

Помогает понять структуру данных, которые возвращает сервер
при выборе группы и навигации по неделям.
"""

import re
import json
import requests
from bs4 import BeautifulSoup


def test_livewire():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) "
                     "Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9",
    })

    print("=" * 60)
    print("Шаг 1: Загрузка главной страницы...")
    resp = session.get("https://schedule.siriusuniversity.ru", timeout=30)
    print(f"  Статус: {resp.status_code}")

    token_match = re.search(r"livewire_token\s*=\s*'([^']+)'", resp.text)
    csrf_token = token_match.group(1) if token_match else ""
    print(f"  CSRF-токен: {csrf_token[:20]}...")

    soup = BeautifulSoup(resp.text, "html.parser")
    wire_el = soup.find(attrs={"wire:initial-data": True})
    initial_data = json.loads(wire_el["wire:initial-data"])

    fingerprint = initial_data["fingerprint"]
    server_memo = initial_data["serverMemo"]

    print(f"  Компонент: {fingerprint['name']}")
    print(f"  ID: {fingerprint['id']}")
    print(f"  Данные: {list(server_memo.get('data', {}).keys())}")

    group_list = server_memo.get("data", {}).get("groupList", [])
    print(f"\n  Доступные группы ({len(group_list)}):")
    for g in group_list[:5]:
        if isinstance(g, dict):
            print(f"    - {g.get('name', g)}")
        else:
            print(f"    - {g}")
    if len(group_list) > 5:
        print(f"    ... и ещё {len(group_list) - 5}")

    print("\n" + "=" * 60)
    print("Шаг 2: Выбираем группу К0609-23...")

    payload = {
        "fingerprint": fingerprint,
        "serverMemo": server_memo,
        "updates": [{
            "type": "callMethod",
            "payload": {
                "id": fingerprint["id"],
                "method": "set",
                "params": ["К0609-23"]
            }
        }]
    }

    headers = {
        "Content-Type": "application/json",
        "X-Livewire": "true",
        "X-CSRF-TOKEN": csrf_token,
        "Referer": "https://schedule.siriusuniversity.ru",
    }

    resp = session.post(
        "https://schedule.siriusuniversity.ru/livewire/message/main-grid",
        json=payload,
        headers=headers,
        timeout=30,
    )
    print(f"  Статус: {resp.status_code}")

    result = resp.json()

    with open("/home/pedro/lks/debug_livewire_response.json", "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("  Полный ответ сохранён в debug_livewire_response.json")

    print(f"\n  Ключи ответа: {list(result.keys())}")

    if "serverMemo" in result:
        new_data = result["serverMemo"].get("data", {})
        print(f"  Ключи serverMemo.data: {list(new_data.keys())}")
        print(f"  Группа: {new_data.get('group', 'не указана')}")
        print(f"  Дата: {new_data.get('date', 'не указана')}")
        print(f"  Неделя: {new_data.get('numWeek', '?')}")

        events = new_data.get("events", [])
        print(f"  Количество событий: {len(events)}")

        if events:
            print("\n  Структура первого события:")
            first = events[0]
            if isinstance(first, dict):
                print(json.dumps(first, ensure_ascii=False, indent=4))
            else:
                print(f"    Тип: {type(first)}, Значение: {first}")

            print(f"\n  Все события ({len(events)}):")
            for i, ev in enumerate(events):
                if isinstance(ev, dict):
                    title = ev.get("title") or ev.get("name") or ev.get("subject") or str(ev)[:80]
                    print(f"    [{i}] {title}")
                else:
                    print(f"    [{i}] {ev}")

        event_elements = new_data.get("eventElement", [])
        print(f"\n  Количество eventElement: {len(event_elements)}")
        if event_elements:
            print("  Структура первого eventElement:")
            first_ee = event_elements[0]
            if isinstance(first_ee, dict):
                print(json.dumps(first_ee, ensure_ascii=False, indent=4))
            else:
                print(f"    Тип: {type(first_ee)}, Значение: {first_ee}")

    if "effects" in result:
        effects = result["effects"]
        print(f"\n  Ключи effects: {list(effects.keys())}")
        if "html" in effects:
            html = effects["html"]
            print(f"  Длина HTML: {len(html)} символов")
            with open("/home/pedro/lks/debug_livewire_html.html", "w") as f:
                f.write(html)
            print("  HTML сохранён в debug_livewire_html.html")

            soup2 = BeautifulSoup(html, "html.parser")

            cells = soup2.find_all("td")
            print(f"\n  Найдено <td> ячеек: {len(cells)}")

            for color in ["teal", "yellow", "sky", "purple", "pink", "orange"]:
                colored = soup2.find_all("div", class_=re.compile(f"bg-{color}-"))
                if colored:
                    print(f"  Цвет {color}: {len(colored)} блоков")
                    for c in colored[:2]:
                        text = c.get_text(separator=" | ", strip=True)
                        print(f"    → {text[:120]}")


if __name__ == "__main__":
    test_livewire()
