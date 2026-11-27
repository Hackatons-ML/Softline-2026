# Умный поиск и рекомендации для Store.softline.ru

Прототип для трека «Аналитик данных» (ИИкузница, кейс Softline).

## Запуск

Все данные уже в репозитории (`Mindbox.yml.gz` — сжатый каталог из фида Mindbox, `frontend/dist` — собранная статика), поэтому Node.js и внешние API-ключи не нужны:

```bash
pip install -r requirements.txt
python run.py
```

При первом старте `run.py` сам распакует на лету `Mindbox.yml.gz`, соберёт индекс в `storage/` (SQLite + BM25 + ONNX-эмбеддинги `Xenova/multilingual-e5-small`) и поднимет сервер на `http://127.0.0.1:8000`. Повторные запуски стартуют сразу с готового индекса.

Пересобрать индекс с нуля:

```bash
python run.py --rebuild-index
```

Запуск в Docker:

```bash
docker build -t softline-search .
docker run -p 8000:8000 softline-search
```

## Тесты

```bash
python -m pytest tests/ -v
```

Проверяют 10 эталонных запросов из `Выборка поисковых запросов.xlsx`, разделение интента «сервер» (оборудование vs ПО), сленг/раскладку/опечатки, минимум 4 товара в выдаче, блок допродаж и эндпоинты API.

## Как устроено

- `backend/data/build_index.py` — потоковый парсер `Mindbox.yml.gz` (136 040 SKU, 9 311 категорий -> 10 916 продуктовых групп), чистка смешанной кириллицы/латиницы, расчёт скидок и ценовых преимуществ по категориям.
- `backend/data/domain_knowledge.py` — словарь ИТ-сленга и ребрендингов (`мтс` -> МТС Линк, `акронис` -> Кибер Бэкап и др.) + совместимые связки вендоров.
- `backend/engine/query_processor.py` — раскладка (ЙЦУКЕН <-> QWERTY), опечатки (`RapidFuzz`), нормализация, определение интента (железо / ПО).
- `backend/engine/hybrid_search.py` — гибрид `multilingual-e5-small` (ONNX) + `BM25F` + RRF-слияние и доменный реранкер, живые подсказки `/api/suggest` и baseline-поиск для сравнения.
- `backend/engine/recommender.py` — блок «Часто покупают вместе» и подбор аналогов из Реестра ПО РФ.
- `backend/engine/analytics_service.py` — логирование запросов/кликов в SQLite, аудит фида и экспорт отчёта в `.xlsx`.
- `frontend/` — интерфейс на React + TypeScript (витрина поиска, сравнение «Было / Стало», кабинет аналитика).
