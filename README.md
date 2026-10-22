# Практическая работа № 2. Вариант 15

Дисциплина: **Прикладная разработка серверных частей веб-приложений на языке Питон**  
Группа: **ИКБО-70-24**, РТУ МИРЭА  
Тема курсовой работы: **Веб-приложение с HTTP API для асинхронной генерации штрих-кодов EAN-13 в формате PDF**

---

## 1. Общее описание

Проект реализует серверное веб-приложение для управления вычислительными задачами генерации векторных штрих-кодов международного формата EAN-13 в формате PDF.

### Архитектура системы:
- **Этап 1 (Преобразование данных):** Консольная утилита (`src.cli`) для вычисления контрольного разряда EAN-13, формирования битовой маски штрих-кода (95 модулей) и генерации векторного PDF-документа на диске.
- **Этап 2 (HTTP API):** RESTful веб-сервер на базе микрофреймворка `Bottle` с авторизацией по стандарту RFC 7617 (HTTP Basic Authentication), обменом данными в формате XML и интеграцией с CLI-утилитой через модуль `subprocess`. Реализован HTTP-клиент (`src.client.ApiClient`) с именами методов, соответствующими маршрутам API согласно ТЗ. Реализовано Model-Based Testing (MBT) на базе библиотеки `hypothesis` (`RuleBasedStateMachine`).
- **Этап 3 (Подключение реляционной СУБД SQLite):** Реализация слоя доступа к данным на базе ORM `PonyORM` с СУБД SQLite (`src.storage_pony.PonyStorage`), полная заменяемость файлового хранилища (`src.storage_file.FileStorage`) и верификация MBT тестами.

### Схема данных (ER-модель Варианта 15):
1. **User** (`identifier: int`, `time: int`, `ip: str`, `locale: str`)
2. **Message** (`identifier: int`, `time: int`, `input: str`, `user: int`, `description: str`, `triggered: int`)
3. **Completion** (`identifier: int`, `time: int`, `result: str`, `state: str`, `failure: str`, `message: int`, `cache_hit: int`, `duration: int`)

### Формула построения отчёта (Формула 15):
$$\pi_{C.state, M.description, U.ip} \Big( U \rtimes_{U.identifier = M.user} \Big( \sigma_{M.identifier = C.message} \big( (\sigma_{M.time \ge now - 9\text{ min}} M) \times C \big) \Big) \Big)$$
Отчет выполняет соединение недавних сообщений (за последние 9 минут) с результатами вычислений и правое внешнее соединение (Right Outer Join) с пользователями, проецируя поля `state`, `description` и `ip`.

---

## 2. Описание функций и настроек

### 2.1 Конфигурация (`src/config.py`)
- `TIME_WINDOW_SECONDS = 540` — временное окно выборки (9 минут).
- `DEFAULT_HOST = "127.0.0.1"`, `DEFAULT_PORT = 8080` — сетевые параметры.
- `DEFAULT_USERNAME = "admin"`, `DEFAULT_PASSWORD = "secretpassword"` — учетные данные RFC 7617.
- `EAN12_LENGTH = 12`, `EAN13_LENGTH = 13` — параметры формата EAN-13.
- `BAR_WIDTH = 2`, `BAR_HEIGHT = 60` — геометрические параметры штрихов.

### 2.2 Консольная утилита (`src/cli.py`)
- `compute_ean13_checksum(digits12)` — вычисление контрольного разряда EAN-13 по модулю 10 с весовыми коэффициентами 1 и 3.
- `normalize_ean13(raw_code)` — валидация 12/13-значного кода и дополнение до 13 цифр.
- `encode_ean13_bits(ean13)` — кодирование в последовательность 95 битовых модулей (защитные полосы `101`, левые знаки по таблице четности первого разряда, центральный разделитель `01010`, правые знаки).
- `generate_barcode_pdf(ean13, bits, pdf_path)` — построение и запись векторного PDF-документа со штрих-кодом и числовой подписью.
- `process_files(input_filepath, output_filepath)` — чтение параметров из JSON, расчет и сохранение результата.

### 2.3 Обработчики HTTP API (`src/app.py`, Таблица 15)
Все обработчики требуют заголовок `Authorization: Basic <base64(user:pass)>` и возвращают ответы в формате XML.
- `POST /private/api/stable/user/insert` — создание пользователя (тело XML: `<user><ip>...</ip><locale>...</locale></user>`).
- `GET /private/api/stable/user/del` — удаление пользователя по `?identifier=<id>`.
- `GET /private/api/stable/user/query` — поиск пользователей по параметрам `?identifier=<id>` или `?ip=<ip>`.
- `POST /private/api/stable/message/insert` — создание задачи сообщения, запуск CLI-утилиты генерации PDF через `subprocess`, создание записи `Completion` и возврат результата.
- `GET /private/api/stable/message/del` — удаление сообщения по `?identifier=<id>`.
- `GET /private/api/stable/message/query/:user` — получение всех сообщений пользователя `:user`.
- `GET /private/api/stable/completion/query/:message` — получение результатов выполнения задачи `:message`.
- `GET /private/api/stable/report/query` — получение отчета по Формуле (15).

### 2.4 Клиент HTTP API (`src/client.py`)
Класс `ApiClient` предоставляет методы, соответствующие именам маршрутов из Таблицы 15:
- `private_api_stable_user_insert(ip, locale)`
- `private_api_stable_user_del(identifier)`
- `private_api_stable_user_query(identifier=None, ip=None)`
- `private_api_stable_message_insert(user, input_data, description, triggered)`
- `private_api_stable_message_del(identifier)`
- `private_api_stable_message_query_user(user)` (алиас: `private_api_stable_message_query`)
- `private_api_stable_completion_query_message(message)` (алиас: `private_api_stable_completion_query`)
- `private_api_stable_report_query()`

---

## 3. Описание команд для сборки проекта и запуска тестов

### Установка зависимостей
```bash
pip install bottle pony hypothesis pytest coverage flake8
```

### Запуск проверок стиля кода (PEP8)
```bash
python -m flake8 src tests
```

### Запуск модульных и Model-Based тестов
```bash
python -m pytest tests
```

### Запуск тестов с отчётом о покрытии кода на основе ветвей (branch coverage)
```bash
python -m coverage run --branch -m pytest tests
python -m coverage report -m
```

### Быстрый запуск через скрипты
- **Windows:**
  ```cmd
  run.bat
  ```
- **Linux / macOS:**
  ```bash
  chmod +x run.sh
  ./run.sh
  ```
- **Make:**
  ```bash
  make all
  ```

---

## 4. Примеры использования

### 4.1 Запуск CLI-утилиты генерации PDF со штрих-кодом
```bash
python -m src.cli -i data/input_1.json -o data/output_1.json
```

Содержимое `data/input_1.json`:
```json
{
  "code": "460123456789",
  "title": "Молоко пастеризованное 3.2%",
  "output_pdf": "data/barcode_1.pdf"
}
```

Результат в `data/output_1.json`:
```json
{
  "raw_code": "460123456789",
  "ean13": "4601234567893",
  "check_digit": 3,
  "pdf_path": "data/barcode_1.pdf",
  "status": "SUCCESS"
}
```
Файл `data/barcode_1.pdf` содержит векторный штрих-код формата EAN-13.

### 4.2 Запуск веб-сервера HTTP API
```bash
python -m src.app --host 127.0.0.1 --port 8080 -u admin -p secretpassword
```

### 4.3 Примеры работы с API через Python-клиент
```python
from src.client import ApiClient

client = ApiClient("http://127.0.0.1:8080", username="admin", password="secretpassword")

# 1. Создание пользователя
user = client.private_api_stable_user_insert(ip="192.168.1.100", locale="ru-RU")
user_id = user["identifier"]

# 2. Создание задачи генерации штрих-кода в PDF
task_input = '{"code": "460123456789", "output_pdf": "result.pdf"}'
msg = client.private_api_stable_message_insert(
    user=user_id,
    input_data=task_input,
    description="Генерация EAN-13 в PDF",
    triggered=1
)

# 3. Получение отчета по Формуле (15)
report = client.private_api_stable_report_query()
print(report)
```
