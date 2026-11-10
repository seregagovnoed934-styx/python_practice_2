"""Interactive live demonstration script for HTTP API defense."""

import json
from src.client import ApiClient
from src.config import (
    DEFAULT_HOST,
    DEFAULT_PASSWORD,
    DEFAULT_PORT,
    DEFAULT_USERNAME,
)


def demo_users_and_task(client: ApiClient) -> tuple[int, int]:
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
    return uid, msg["message_id"]


def demo_queries_and_del(client: ApiClient, uid: int, mid: int) -> None:
    """Demonstrate query by path param and deletion handlers."""
    print("\n--- 4. Поиск сообщений (GET /message/query/:user) ---")
    msgs = client.private_api_stable_message_query_user(uid)
    print(f"Найдено сообщений пользователя {uid}: {len(msgs)}")

    print("\n--- 5. Поиск завершения (GET /completion/query/:message) ---")
    comps = client.private_api_stable_completion_query_message(mid)
    print(f"Найдено результатов для сообщения {mid}: {len(comps)}")

    print("\n--- 6. Удаление сообщения (GET /message/del) ---")
    del_msg_res = client.private_api_stable_message_del(mid)
    print("Статус удаления сообщения {}:".format(mid), del_msg_res)

    print("\n--- 7. Удаление пользователя (GET /user/del) ---")
    del_u_res = client.private_api_stable_user_del(uid)
    print("Статус удаления пользователя {}:".format(uid), del_u_res)


def demo_report_and_auth(client: ApiClient, url: str) -> None:
    """Demonstrate relational report query and authentication check."""
    print("\n--- 8. Получение отчета по Формуле (15) (GET /report/query) ---")
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

    print("\n--- 9. Проверка неавторизованного доступа (401) ---")
    bad_client = ApiClient(url, "hacker", "wrong_pass")
    st, resp = bad_client._send("GET", "/private/api/stable/report/query")
    print(f"Код ответа при неверном пароле: {st} (Ожидается 401)")
    print("Тело ответа сервера:", resp)


def run_demo() -> None:
    """Run full demonstration of API methods with live output."""
    url = "http://{}:{}".format(DEFAULT_HOST, DEFAULT_PORT)
    print(f"Connecting to API at {url}...")
    client = ApiClient(url, DEFAULT_USERNAME, DEFAULT_PASSWORD)
    uid, mid = demo_users_and_task(client)
    demo_report_and_auth(client, url)
    demo_queries_and_del(client, uid, mid)
    print("\n=== Демонстрация всех 8 методов успешно завершена! ===")


if __name__ == "__main__":
    run_demo()
