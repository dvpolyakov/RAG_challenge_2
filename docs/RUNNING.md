## Инструкция по запуску (Linux и Docker)

Этот проект отвечает на вопросы по стенограммам одной персоны из `.txt` файлов формата `MM:SS Спикер: текст`. PDF/Docling не используются в основном сценарии.

### 1) Подготовка данных

- Положите транскрипты в каталог `data/persona_set/` (например, `transcript_1.txt`, `transcript_2.txt` и т.д.).
- Создайте `data/persona_set/subset.csv`:
```
sha1,company_name
persona_interviews,Имя Фамилия
```
- Убедитесь, что `.env` содержит ключи (минимум):
```
OPENAI_API_KEY=sk-... 
```

### 2) Запуск локально (без Docker)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e . -r requirements.txt
```

Далее выполните команды из каталога `data/persona_set`:

- Конвертация `.txt` → `databases/chunked_reports/persona_interviews.json`:
```bash
python ../../main.py transcripts-to-chunked \
  --company-name "Имя Фамилия" \
  --sha1-name persona_interviews \
  --input-glob "transcript*.txt"
```

- Создание векторов (FAISS):
```bash
python ../../main.py create-vector-dbs
```

- Ответы по вопросам из файла `questions.json` (опционально):
```bash
python ../../main.py process-questions --config max_nst_o3m
```

Где лежат артефакты:
- Чанки: `data/persona_set/databases/chunked_reports/*.json`
- Вектора: `data/persona_set/databases/vector_dbs/*.faiss`

### 3) Запуск в Docker

Сборка образа (в корне репозитория):
```bash
docker compose build
```

Команды выполняются внутри (`working_dir: /app/data/persona_set`):

- Конвертация `.txt` → chunked JSON:
```bash
docker compose run --rm rag-persona \
  python ../../main.py transcripts-to-chunked \
  --company-name "Имя Фамилия" \
  --sha1-name persona_interviews \
  --input-glob "transcript*.txt"
```

- Создание векторов:
```bash
docker compose run --rm rag-persona \
  python ../../main.py create-vector-dbs
```

- Ответы по вопросам:
```bash
docker compose run --rm rag-persona \
  python ../../main.py process-questions --config max_nst_o3m
```

Монтирование данных и секретов:
- `./data` на хосте ↔ `/app/data` в контейнере (артефакты сохраняются персистентно)
- `./.env` на хосте ↔ `/app/.env` (переменные среды, в т.ч. `OPENAI_API_KEY`)

### 4) Интерактив без `questions.json` (опционально)

Пример использования напрямую из Python:
```python
from src.production.questions_processing import QuestionsProcessor

qp = QuestionsProcessor(
    vector_db_dir="data/persona_set/databases/vector_dbs",
    documents_dir="data/persona_set/databases/chunked_reports",
    parent_document_retrieval=True,
    llm_reranking=True,
    top_n_retrieval=10,
    api_provider="openai",
    answering_model="o3-mini-2025-01-31",
    subset_path="data/persona_set/subset.csv",
)

print(qp.get_answer_for_company(
    "Имя Фамилия", 
    "Что говорил Имя Фамилия про роль ИИ в образовании?", 
    schema="names"
))
```

### 5) Частые вопросы

- Где лежит векторное хранилище? В `data/persona_set/databases/vector_dbs/*.faiss` (имя файла = `sha1_name`).
- Нужно ли PDF? Нет, основной путь — `.txt` → `chunked_reports` → вектора → ответы.
- Что если транскриптов несколько? Укажите `--input-glob "transcript*.txt"` — все файлы будут склеены по сегментам в один документ с постраничной нумерацией.


