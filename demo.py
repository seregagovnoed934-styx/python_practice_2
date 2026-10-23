"""Interactive live demonstration script for HTTP API defense."""

import json
from src.client import ApiClient
from src.config import (
    DEFAULT_HOST,
    DEFAULT_PASSWORD,
    DEFAULT_PORT,
    DEFAULT_USERNAME,
)


def demo_users_and_task(client: ApiClient) -> int:
    """Demonstrate user creation and barcode message generation."""
    print("\n--- 1. Создание пользователя (POST /user/insert) ---")
    user = client.private_api_stable_user_insert("192.168.1.50", "ru-RU")
    print("Создан пользователь:", user)
    uid = user["identifier"]

    print("\n--- 2. Поиск пользователей (GET /user/query) ---")
    users = client.private_api_stable_user_query()
    print(f"Всего пользователей в системе: {len(users)}")

    print("\n--- 3. Создание задачи генерации штрих-кода ---")
    barcode_payload = json.dumps(
        {
            "code": "460123456789",
            "title": "Молоко пастеризованное 3.2%",
            "output_pdf": "data/demo_barcode.pdf",
        }
    )
    msg = client.private_api_stable_message_insert(
        user=uid,
        input_data=barcode_payload,
        description="Генерация EAN-13 в PDF для молока",
        triggered=1,
    )
    print("Создано сообщение и результат выполнения задачи:")
    print(json.dumps(msg, indent=2, ensure_ascii=False))
    print("Файл PDF успешно создан: data/demo_barcode.pdf")
    return uid


def demo_report_and_auth(client: ApiClient, url: str) -> None:
    """Demonstrate relational report query and authentication check."""
    print("\n--- 4. Получение отчета по Формуле (15) (GET /report/query) ---")
    st_rep, raw_xml_rep = client._send(
        "GET", "/private/api/stable/report/query"
    )
    print("Сырой XML ответа сервера по формуле (15):")
    print(raw_xml_rep)
    report = client.private_api_stable_report_query()
    print("Распарсенные данные отчёта:")
    for item in report:
        st_val = item["state"]
        desc_val = item["description"]
        ip_val = item["ip"]
        print(f"  Статус: {st_val} | Задача: {desc_val} | IP: {ip_val}")

    print("\n--- 5. Проверка неавторизованного доступа (401) ---")
    bad_client = ApiClient(url, "hacker", "wrong_pass")
    st, resp = bad_client._send("GET", "/private/api/stable/report/query")
    print(f"Код ответа при неверном пароле: {st} (Ожидается 401)")
    print("Тело ответа сервера:", resp)


def run_demo() -> None:
    """Run full demonstration of API methods with live output."""
    url = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}"
    print(f"Connecting to API at {url}...")
    client = ApiClient(url, DEFAULT_USERNAME, DEFAULT_PASSWORD)
    demo_users_and_task(client)
    demo_report_and_auth(client, url)
    print("\n=== Демонстрация успешно завершена! ===")


if __name__ == "__main__":
    run_demo()
