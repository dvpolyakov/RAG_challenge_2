## План адаптации пайплайна для «виртуальной копии персоны» (только текстовые транскрипты одной персоны)

Этот план описывает, как превратить готовые текстовые материалы по ОДНОЙ персоне в QA‑систему на базе текущего репозитория. Источник — текстовые файлы формата как `data/persona_set/transcript_1.txt` (строки вида `MM:SS Спикер: текст…`). PDF не используются.

### 1) Определите цели и границы
- **цель**: отвечать на вопросы по содержанию интервью/речей/статей ОДНОЙ персоны
- **формат источника**: только `.txt`‑транскрипты формата как `transcript_1.txt`
- **языки**: один язык или мультиязычно (RU/EN)
- **типы вопросов**: факты, имена, булевы, сравнения
- **правообладание**: убедитесь, что у вас есть права на обработку материалов

### 2) Сбор данных
- **источники**: уже готовые транскрипты интервью/речей/постов одной персоны
- **структура хранения (без PDF)**:
  - `data/persona_set/transcripts/` — `.txt`‑файлы вида `transcript_*.txt`
  - `data/persona_set/subset.csv` — соответствие `sha1` и имени персоны
  - `data/persona_set/questions.json` — опционально список вопросов для регрессии

### 3) Нормализация текста (опционально)
- **очистка**: удалить явный шум, повторяющиеся междометия, исправить пунктуацию
- **язык**: оставить как есть или привести к одному языку
- **сегментация**: не требуется вручную — разбиение сделает сплиттер

### 4) Подготовка данных без PDF (основной путь)
- Мы минуем Docling и этапы PDF. Сразу формируем `databases/chunked_reports/*.json` нужного формата из `.txt`.

### 5) Схема целевого JSON (`chunked_reports`)
- Для каждой персоны хранится один JSON:
  - `metainfo.company_name` — имя персоны (ключ маршрутизации в поиске)
  - `metainfo.sha1_name` — стабильный идентификатор (и имя файла без расширения)
  - `content.pages` — список `{ page (1-based), text }`
  - `content.chunks` — список `{ page, text, length_tokens }`

Пример:
```
{
  "metainfo": {
    "company_name": "Имя Фамилия",
    "sha1_name": "persona_interviews"
  },
  "content": {
    "pages": [
      { "page": 1, "text": "Текст страницы 1..." },
      { "page": 2, "text": "Текст страницы 2..." }
    ],
    "chunks": [
      { "page": 1, "length_tokens": 512, "text": "Фрагмент 1 страницы 1..." }
    ]
  }
}
```

### 6) Создайте `subset.csv`
- Сопоставление имени персоны и `sha1`:
```
sha1,company_name
persona_interviews,Имя Фамилия
```
- Поместите в `data/persona_set/subset.csv`

### 7) Настройте окружение
- Переименуйте `env` → `.env` и заполните ключи:
  - `OPENAI_API_KEY` (обязательно); опционально `GEMINI_API_KEY`, `JINA_API_KEY`
- Установите зависимости:
```
python -m venv .venv
source .venv/bin/activate
pip install -e . -r requirements.txt
```

### 8) Конвертация `.txt` → `chunked_reports/*.json`
- Ожидаемый формат строк в `.txt`: `MM:SS Спикер: текст…` (пример см. `data/persona_set/transcript_1.txt`).
- Каждая строка с таймкодом начинает новый «page»; текст между таймкодами входит в соответствующую страницу вместе с именем спикера.
- Быстрый конвертер (запустите из корня репо):
```
python - <<'PY'
from pathlib import Path
import re, json
from src.text_processing.text_splitter import TextSplitter

root = Path("data/persona_set")
in_dir = root
texts = sorted([p for p in in_dir.glob("transcript*.txt")]) or [root/"transcript_1.txt"]

def parse_txt_to_pages(txt: str):
    segments, buf = [], []
    ts_re = re.compile(r'^\s*\d{2}:\d{2}\s', re.MULTILINE)
    for line in txt.splitlines():
        if ts_re.match(line):
            if buf:
                segments.append("\n".join(buf).strip())
                buf = []
            buf.append(line.strip())
        else:
            if buf or line.strip():
                buf.append(line.strip())
    if buf:
        segments.append("\n".join(buf).strip())
    return [{"page": i+1, "text": seg} for i, seg in enumerate(segments)]

pages = []
for tp in texts:
    txt = tp.read_text(encoding="utf-8")
    pages.extend(parse_txt_to_pages(txt))

ts = TextSplitter()
chunks = []
for pg in pages:
    for ch in ts._split_page(pg, chunk_size=600, chunk_overlap=120):
        chunks.append(ch)

doc = {
    "metainfo": {"company_name": "Имя Фамилия", "sha1_name": "persona_interviews"},
    "content": {"pages": pages, "chunks": chunks}
}

out_dir = root / "databases" / "chunked_reports"
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "persona_interviews.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
print("Saved:", out_dir / "persona_interviews.json")
PY
```

### 9) Создание векторных БД
- Достаточно построить вектора из уже готовых `chunked_reports`:
```
python - <<'PY'
from pyprojroot import here
from src.pipeline import Pipeline
pl = Pipeline(here() / "data" / "persona_set")
pl.create_vector_dbs()
PY
```

### 10) Конфигурация ответов
- Рекомендуемый конфиг: `max_nst_o3m` (PDR + LLM‑rerank + o3‑mini)
- Запуск в `data/persona_set`:
```
cd data/persona_set
python ../../main.py process-questions --config max_nst_o3m
```
- Для произвольных вопросов без файла см. «Интерактивный режим» (шаг 12)

Тонкая настройка в `src/pipeline.py` (`RunConfig`/`configs`):
- `top_n_retrieval`, `llm_reranking_sample_size`, `parallel_requests`, `answering_model`

### 11) Адаптация промптов под интервью
Откройте `src/llm_api_utils/prompts.py` и замените формулировки «годовой отчёт компании» на «интервью/транскрипты персоны» в:
- `AnswerWithRAGContextSharedPrompt`
- Схемах `name/number/boolean/names` (при необходимости ослабьте строгость числовых правил)
- `ComparativeAnswerPrompt` (нужно, только если будут сравнения персон)

Достаточно перефразовать инструкцию; схемы сохраняют структуру ответа и ссылки на «страницы»

### 12) Интерактивный режим (без `questions.json`)
Пример использования `QuestionsProcessor`:
```
from src.production.questions_processing import QuestionsProcessor

qp = QuestionsProcessor(
    vector_db_dir="./databases/vector_dbs",
    documents_dir="./databases/chunked_reports",
    parent_document_retrieval=True,
    llm_reranking=True,
    top_n_retrieval=10,
    api_provider="openai",
    answering_model="o3-mini-2025-01-31",
    full_context=False,
    subset_path="./subset.csv",
)

question = "Что говорил Имя Фамилия о роли ИИ в образовании?"
company_name = "Имя Фамилия"  # имя персоны из subset.csv
answer = qp.get_answer_for_company(company_name, question, schema="names")
print(answer)
```
Схемы: `name`, `number`, `boolean`, `names`, `comparative`

### 13) Проверка качества и ссылок
- Ответы включают `relevant_pages`/`references` (работают как «сегменты/страницы» интервью)
- `_validate_page_references` в `QuestionsProcessor` очищает неверные номера
- Сделайте небольшой `questions.json` для регрессии

### 14) Стоимость и производительность
- На дефолтном `max_nst_o3m`: ~0.02–0.03$ за вопрос (зависит от длины контекста)
- Экономия:
  - уменьшите `llm_reranking_sample_size` и `top_n_retrieval`
  - отключите LLM‑rerank (значимая экономия, небольшой минус к качеству)
  - сокращайте длину «страниц»/чанков

### 15) Рекомендации по чанкингу
- Для длинных интервью:
  - чанки 600–1200 токенов, оверлап 15–20%
  - объединяйте близкие по теме ответы (сплиттер уже группирует по страницам‑сегментам)
- При необходимости адаптируйте `TextSplitter` в `src/text_processing/text_splitter.py`

### 16) Приватность и безопасность
- Не коммитьте `.env`
- Соблюдайте правовой статус материалов и ПДн

### 17) Диагностика
- Промежуточные артефакты: `debug_data/01_*`, `02_*`, `03_*`
- Итог: `databases/chunked_reports/*.json`, `databases/vector_dbs/*.faiss`
- Трассировки ошибок — из `QuestionsProcessor`

### 18) Идеи улучшений
- Стиль ответа в духе персоны (тон/лексика) — добавить в system‑prompt
- «Память цитат»: хранить ID сегментов, расширять контекст
- Рерайт «устной речи» перед индексированием
- Мультимодальность (слайды/изображения)

### 19) Быстрый чеклист (без PDF)
- Подготовьте `.txt` в `data/persona_set/` (например, `transcript_1.txt`)
- Создайте `subset.csv`
- Сгенерируйте `databases/chunked_reports/persona_interviews.json` (шаг 8)
- Постройте вектора (`Pipeline.create_vector_dbs()`)
- Задавайте вопросы (`process-questions` или `QuestionsProcessor.get_answer_for_company()`)

— Конец плана —
