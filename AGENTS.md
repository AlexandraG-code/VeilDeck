# AGENTS.md — правила для агентов в проекте VeilDeck

Единый источник правил для всех агентов (Claude, Codex, DeepSeek, GLM и др.). `CLAUDE.md` только ссылается сюда.

## 1. Что за проект

VeilDeck — учебный демонстрационный MVP «Confidential Teaser & Controlled Disclosure» (кейс B, партнёр Smart IMMO Invest). Публикует обезличенные карточки корпоративных возможностей (teaser); расширенные сведения и документы раскрываются конкретному внешнему пользователю только после ручного одобрения, на ограниченный срок, с мгновенным отзывом и аудитом. Описание возможностей: `README.md`.

**Источник истины по требованиям — `openspec/`.** Перед любой задачей читай:
- `openspec/config.yaml` — контекст и жёсткие ограничения;
- `openspec/changes/add-controlled-disclosure-mvp/{proposal,design,tasks}.md`;
- `openspec/changes/add-controlled-disclosure-mvp/specs/<домен>/spec.md` — требования GIVEN/WHEN/THEN нужного домена.

Работай по `tasks.md` (теги `[BE]` `[FE]` `[OPS]` `[SEC]` `[DOC]`). Расходится код со спекой — правится спека через OpenSpec-change, а не молча код. Проверка спек: `openspec validate --strict`.

Язык: документы, комментарии, коммиты — русский. Ключевые слова OpenSpec (Requirement, Scenario, SHALL/MUST, GIVEN/WHEN/THEN) — английские.

## 2. Жёсткие ограничения (не нарушать)

- Только демо в изолированной среде, только синтетические данные, никаких реальных документов и ПДн.
- Вне scope: платежи, ЮЗЭДО, постоянные кабинеты внешних пользователей, регистрация/соцлогин, реальная почта/SMS (только Mailpit), Kubernetes, DRM.
- Все контроли безопасности — на сервере. Скрытие элемента в UI не контроль доступа.
- Криптография и аутентификация — только проверенные библиотеки (argon2-cffi, cryptography, pyotp). Самописного нет.
- Секреты не попадают в репозиторий, образы и логи. Приложение не стартует без секретов или с дефолтными.
- Репозиторий по брифу (с. 9) должен быть приватным. **На время разработки он публичный** — осознанное отклонение команды (код нужно показывать), решение D-08 в `design.md`; письменного согласия SMI нет. Поэтому в репозитории только синтетика и никаких секретов, а перед сдачей репозиторий закрывается (или берётся согласие). Бриф, скриншоты, findings и результаты тестов за пределы репозитория не публиковать (соцсети, портфолио).
- Тестировать (ZAP, Burp, сканеры) только свой локальный стенд. Деплой на хостинг — только с закрытым доступом (basic auth или allowlist по IP) и синтетическими данными.
- Запуск через Docker Compose по README за ≤ 30 минут в чистой среде.

## 3. Ключевые решения (обязательны)

- **Сессии на сервере в Redis, не JWT** (мгновенный отзыв). Cookie `__Host-sid` (staff), `__Host-vsid` (viewer), `__Host-csrf`; HttpOnly, Secure, SameSite=Strict. SID ≥ 128 бит, ротация при входе. Роль берётся только из серверной сессии. Staff и viewer — разные сессии и префиксы API (`/api/v1/staff/*`).
- **Токен одноразовой ссылки** — `secrets.token_urlsafe(32)`, в БД только SHA-256, TTL 30 мин, передаётся во fragment (`#t=`), SPA сразу делает `history.replaceState`. Погашение — атомарный UPDATE, повтор → 410. Ссылку и токен не логировать.
- **Оригиналы PDF не отдаются никогда.** Viewer получает растр страниц (PNG ≤ 150 dpi) с серверным watermark `псевдоним · UTC · WM-код`. WM-код = base32(HMAC-SHA256(wm_key, grant_id ‖ view_id))[:10]. Параметры запроса на watermark не влияют. `Cache-Control: no-store`.
- **Чужой объект → 404 с тем же телом, что у несуществующего.** Отказ по роли → 403. Оба случая пишутся в аудит.
- **Разделение обязанностей:** admin не одобряет запросы и видит только счётчики очереди; reviewer не публикует карточки и не загружает материалы; никто не может изменить или удалить событие аудита.
- **Аудит append-only:** у роли БД `app_rw` только INSERT/SELECT на `audit_events` + триггер на UPDATE/DELETE + hash-цепочка `SHA-256(prev_hash ‖ canonical JSON)` под advisory lock. В `details` — только allowlist, без токенов, паролей, TOTP, e-mail, purpose, org_name.
- **E-mail requester** хранится только как Fernet + HMAC. IP — только HMAC.
- **Публичные ответы не раскрывают существование:** `POST access-requests` всегда 202 `{"status":"received"}`; draft/archived/несуществующая карточка → одинаковый 404.
- Pydantic v2 с `extra="forbid"`, параметризованные запросы, единый формат ошибок `{"error":{"code","message","request_id"}}` без стек-трейсов.
- Решение по запросу единственное (UNIQUE request_id, повтор → 409), автоодобрения нет.
- Каждое security-решение в коде связывается с угрозой T-xx и требованием SR-xx из `design.md`.

## 4. Стек и структура

| Часть | Технологии |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, structlog |
| БД / кэш | PostgreSQL 16 (роли `app_owner` для миграций, `app_rw` для приложения), Redis 7 |
| Frontend | React 19, TypeScript, Vite, antd 6, zustand, FSD (см. §6) |
| Прочее | nginx (единственная точка входа, same-origin), Mailpit, PyMuPDF + Pillow для watermark, Docker Compose |

```
backend/   FastAPI-приложение, Alembic, тесты (pytest)
  tests/security/   негативные security-тесты TC-* (внешние, через API; владелец — Александра)
frontend/  SPA (React + TS + Vite)
  src/shared/api/generated/   типы и клиент из docs/api/openapi.json — АВТОГЕНЕРАЦИЯ, руками не править
deploy/    docker-compose, nginx, Dockerfile
docs/      docs/security/, docs/api/openapi.json (экспорт в CI)
openspec/  требования
Makefile   make secrets | seed | retention-run NOW_OFFSET=31d
```

Публичные ID — только UUIDv4; bigint наружу не отдаются.

## 5. Backend (FastAPI)

- **Архитектура: слоёная по доменам** (не MVC и не полная Clean Architecture; решение архитектора, см. `design.md` D-09). Домен — папка `backend/app/<домен>/` с файлами `router.py` → `service.py` → `repository.py` → `models.py` плюс `schemas.py`. Роутер без бизнес-логики и SQL; сервис не знает про FastAPI/HTTP; репозиторий трогает только таблицы своего домена и не делает `commit`.
- **Граф доменов (сверху вниз, импорт вверх запрещён):** `review | access | content` → `grants | requests` → `cards | catalog` → `auth` → `audit` → `core`. Решение по запросу оркестрирует `review.service` (вызывает `requests.service` и `grants.service`); отзыв живёт в `grants`; `access` и `content` только читают `grants`. Чужие данные — через `<домен>.service`, не через чужие `repository`/`models`; связи ORM между доменами только `ForeignKey("таблица.id")` строкой.
- **Ошибки без HTTP:** сервисы бросают `NotFound`/`Forbidden`/`Conflict`/`Gone`/`RateLimited`/`Unauthorized` из `core/exceptions.py`; в HTTP-коды и единый формат их превращает только `core/errors.py`. «Чужой объект → 404 с тем же телом» — один и тот же `NotFound`.
- **Сквозное:** `api/deps.py` (`require_staff(role)`, `require_viewer`, deny by default), `core/principal.py` (Principal из серверной сессии передаётся в сервис аргументом; `card_id`/`grant_id` viewer-а только оттуда), `core/sessions.py`, `core/ratelimit.py`. Сервис повторно проверяет разделение обязанностей (admin не одобряет, reviewer не публикует) — второй рубеж после RBAC. `content/watermark.py` — чистая функция без FastAPI и БД.
- **Транзакции:** одна `AsyncSession` на запрос, границу держит сервис (`async with session.begin()`). Аудит успешного действия пишется в той же транзакции (`audit.service.record(session, ...)` под `pg_advisory_xact_lock`); аудит отказов (403/404/ошибки) — отдельной короткой транзакцией, чтобы откат его не стёр. Очистка Redis при отзыве — после commit.
- **Проверки правил в CI:** `lint-imports` (`backend/.importlinter`: граф доменов, слои внутри домена, нет `fastapi`/`starlette` в сервисах и ядре, нет чужих `repository`/`models`), архитектурные тесты `backend/tests/architecture/` (каждый роут с `require_*` или в allowlist; все схемы `extra="forbid"`).
- RBAC — deny-by-default через зависимость на каждом роуте; есть тест, обходящий `app.routes` и проверяющий, что нет роутов без проверки роли.
- Один эндпоинт — один контракт: схемы запроса/ответа Pydantic, документируются в OpenAPI. Docs/DEBUG выключены при `ENV=demo`.
- Конфиг через pydantic-settings, fail-fast при отсутствии секретов.
- Миграции только Alembic от `app_owner`; приложение работает под `app_rw`.
- Rate limiting: Redis sliding window, 429 + `Retry-After`; лимиты из `platform-security` и `design.md`.
- Загрузки: PDF/PNG/JPEG, ≤ 10 МБ, magic bytes = расширение = MIME, PDF с JS/вложениями/шифрованием отклоняется, имя файла случайное.
- Тесты: pytest. Линт: ruff. Безопасность: bandit, pip-audit.

## 6. Frontend: архитектура как у notifier-frontend

Эталон: `/Users/alex/WebstormProjects/notifierFrontend` (его `AGENTS.md` — подробные правила). Переносится универсальное ядро; GREEN-API-специфика не переносится.

**Стек:** React 19, TypeScript, Vite, antd 6 + `@ant-design/icons`, TanStack Query 5 (серверный стейт) + zustand 5 (клиентский стейт), react-router-dom 7 (`createHashRouter` не нужен — VeilDeck за nginx, используем `createBrowserRouter`), axios, i18next + react-i18next, SCSS Modules (sass), vitest + Testing Library, Playwright, eslint (flat) + typescript-eslint, prettier + `@trivago/prettier-plugin-sort-imports`. Пакетный менеджер — yarn. Redux и RTK Query не используем: роль RTK Query играет TanStack Query.

**Слои FSD** (импорт только вниз): `app → pages → widgets → features → entities → shared`.
```
src/
  app/       main.tsx, App.tsx, providers/ (ErrorNotifier, ThemeProvider), routes/ (AppRouter, guards), styles/
  pages/     тонкие оболочки страниц
  widgets/   составные блоки (виджет не импортирует другой виджет — их сочетает страница)
  features/  пользовательские сценарии (Auth, RequestAccess, DecideRequest, RevokeGrant, ...)
  entities/  Card, AccessRequest, Grant, Material, AuditEvent
  shared/    api/, config/, i18n/, lib/, styles/, theme/, ui/
  test/      setup.ts
```
Слайс: `api/` · `model/` (сторы, типы, enums, constants, хуки) · `ui/` · `lib/` · `index.ts` (публичный API). Чужой слайс импортируется только через его `index.ts`.

**Сгенерированный API:** `src/shared/api/generated/` (слой `shared`, отдельного слоя `api` в FSD нет). Генерируется orval из `docs/api/openapi.json`: типы, axios-клиент и хуки TanStack Query, первой строкой каждого файла — «АВТОГЕНЕРАЦИЯ, НЕ ПРАВИТЬ»; в игноре eslint и prettier. Сгенерированные хуки используются в `model/` и `ui/` слайсов; запросы руками не пишутся. Пока бэка нет — моки MSW по той же схеме.

**Алиасы:** `@app @pages @widgets @features @entities @shared` — объявляются в `vite.config.ts` (`resolve.alias`) и `tsconfig.app.json` (`paths`); vitest наследует через `mergeConfig`.

**Проверка слоёв:** направление импортов FSD (только вниз) и импорт чужого слайса только через `index.ts` проверяет eslint (`no-restricted-imports` в `frontend/eslint.config.js`), падение блокирует CI.

**Конвенции кода:**
- Типы — в `types.ts`, enum — в `enums.ts`, константы — в `constants.ts`; inline-типы в сигнатурах запрещены. Числовые литералы — именованные константы. JSDoc на каждой функции модуля. Строка ≤ 120 символов.
- Один компонент — одна папка (`.tsx`, `.module.scss`, `.variables.scss`, `types.ts`, `constants.ts`). Файл компонента содержит только разметку; универсальные компоненты управляемые (`value`/`onChange`).
- Порядок в теле компонента/хука: сторы, `useState`, библиотечные хуки, свои хуки, вычисляемое, `useMemo`, `useCallback`, `useEffect`, обработчики, `return`. В `useEffect` только вызовы функций.
- Стили: `@use '@shared/styles' as *;`, размеры через `rem()`, цвета только из токенов темы (`var(--color-*)`, `getAntdTheme`), хекс-цветов в компонентах нет.
- i18n: текстов в коде нет; `shared/i18n/locales/<страница>/<ru|en>/<страница>.json`; новое пространство — в enum `Namespace` и оба json; загрузка через `loadNamespaces` в `lazy` маршрута.
- Ошибки: запросы идут через TanStack Query, ошибки ловит глобальный `onError` у `QueryCache`/`MutationCache`; показывает их только `ErrorNotifier`. Действия zustand-сторов с запросами оборачиваются в `runAsyncAction`. Прямые `notification.error` / `message.error` запрещены.
- API: в `shared/api` только общий axios-инстанс (таймаут из env, CSRF-заголовок) — orval использует его как mutator. Ручных `*.service.ts` нет; обёртки над сгенерированными хуками (ключи инвалидации, тексты ошибок) — в `model/` слайса.
- Серверные данные (очередь, grants, карточки) живут только в кэше TanStack Query и не дублируются в zustand; после approve/revoke/смены срока — инвалидация ключей.
- Клиентское состояние (UI, текущий пользователь) — zustand; `persist` не использовать для чувствительных данных.
- Runtime-конфиг без `VITE_*`: `env-config.ts` (из `env-config.ts.sample`) → `window._env_`; CSP формируется Vite-плагином.
- Фигурные скобки у `if/else/for/while` обязательны (`curly: all`). `import type`, `verbatimModuleSyntax`.

**Безопасность фронта (из спек):**
- Никакого `dangerouslySetInnerHTML`; текст рендерится как текст.
- Токен из `#t=` читается один раз и сразу удаляется из URL (`history.replaceState`); в `localStorage`/`sessionStorage` не кладётся.
- UI не утверждает, что копирование защищено: показывает баннер о watermark и аудите.
- Виджет просмотра не даёт скачать оригинал; скачивание — только если `allow_download`.
- Проверка до коммита: `yarn tsc -b`, `yarn lint`, `yarn format`, `yarn test`.

## 7. Тестирование

- На каждый security-контроль — свой негативный тест. Именование: `TC-<ДОМЕН>-NN` (TC-CAT, TC-CARD, TC-VIEW, TC-LINK, TC-RBAC, TC-API, TC-LEAK, TC-WM, TC-AUD, TC-AUTH, TC-RL, TC-RACE, TC-HDR, TC-FE). Список — в `tasks.md`.
- Сначала бесплатные проверки (lint, tsc, ruff, pytest), потом ревью.
- Задачи не крупнее ~1 рабочего дня.

## 8. Комитет агентов

- **Оркестратор** (основная сессия) — декомпозиция, ТЗ, сбор результата, коммит.
- **`validator`** — проверяет каждый diff исполнителей (ТЗ в `<task>`, diff в `<candidate_diff>`). `OK` → принять; `ERROR` → откатить и вернуть исполнителю (до 2 кругов); `NEEDS_ARCHITECT` → `opus-architect`.
- **`opus-architect`** — заранее, если задача меняет архитектуру, публичные контракты, миграции или авторизацию. На рутину не тратить.
- **Исполнители** (DeepSeek, GLM) получают узкое ТЗ: какие файлы и функции менять, какой контракт соблюсти, чего не трогать.
- **Что общее, что личное.** Общее (в git): роли и порядок работы (этот раздел) и промпты `validator` и `opus-architect` в `.claude/agents/` (они главнее личных из `~/.claude/agents/`), поэтому у Александры и Дианы проверяющие работают одинаково. Личное (не в git): какие модели и ключи используют исполнители (fleet, DeepSeek/GLM), настройки в `CLAUDE.local.md` и `.claude/settings.local.json`. Исполнители необязательны: у кого их нет, оркестратор пишет код сам, `validator` и проверки (lint, tsc, pytest, `lint-imports`) обязательны для всех.
- **Защищённое — только оркестратор своей зоны** (у каждого участника свой оркестратор, см. §11): `context/*.md`, `team.json`, `registry.json`, конфиги сборки и CI, миграции, авторизация, секреты. Исполнители защищённое не трогают; в чужой зоне правка идёт только через PR с ревью владельца (CODEOWNERS).
- Большие файлы (спеки, PDF, дампы) читаются субагентами с возвратом выжимки.

## 9. Git

Один коммит на задачу. Сообщение — по-русски, с указанием номера задачи из `tasks.md`. `main` защищён, изменения идут через PR. Не коммитить `.env`, секреты, `env-config.ts`.

## 10. Чего не делать

- Не добавлять функциональность вне `openspec/` без нового change.
- **Не ставить галочки (`- [x]`) и не менять строки задач в `openspec/changes/*/tasks.md`**: статус ведётся в GitHub Issues/Projects, чекбоксы отмечает человек один раз при архивации change (иначе конфликты слияния). Агентам `tasks.md` только читать.
- Не логировать токены, session ID, пароли, TOTP, e-mail, purpose, org_name.
- Не отдавать оригиналы материалов и не принимать `card_id` viewer-а из запроса (он берётся из сессии).
- Не писать самодельную криптографию, не выключать проверки «на время демо».
- Не публиковать бриф, findings и результаты вовне (соцсети, портфолио); не класть в репозиторий секреты и реальные данные.

## 11. Работа вдвоём: вертикальные срезы

Александра (`AlexandraG-code`) и Диана (`LediDi060`) берут задачи целиком, фронт + бэк + тесты обоих слоёв. Контракт — `docs/api/openapi.json`, который FastAPI генерирует из кода; клиент и хуки фронта генерируются из него (`src/api/generated/`).

Работаем **вертикальными срезами**: срез (бэк + фронт + тесты обоих слоёв) целиком у одного человека, поэтому на ходу никто никого не ждёт. Исполнитель каждой задачи — в скобках в `tasks.md`: (А) Александра, (Д) Диана, (А+Д) вместе (счёт в `tasks.md`). Диана отвечает за документы и план/отчёт тестирования, Александра — за код срезов, инфру и CI.

| Срез | Задачи | Кто |
|---|---|---|
| Основа: БД, аудит, сессии, CSRF, rate limit, RBAC, логи | 1.6, 1.7, 2.1–2.6 | Д (первые 2–3 дня) |
| Вход staff | 3.1–3.5 | Д |
| Решения reviewer: очередь, решение, письма, grants, отзыв | 6.1–6.6 | Д |
| Карточки и материалы | 4.1–4.6 | А |
| Каталог и запросы доступа | 5.1–5.4 | А |
| Viewer и watermark | 7.1–7.8 | А |
| Аудит и retention | 8.1–8.5 | А |
| Инфра, CI, права админа репозитория, деплой | 0.2, 1.1–1.5, 1.8, 1.9, раздел 9 | А |
| Ручное тестирование безопасности | 10.1 (план WSTG), 10.3 (отчёт), 10.5 (OWASP Top 10 / CISA) — Д; 10.2 (прогон ZAP и ручные проверки, перекрёстно: каждая тестирует срезы другой), 10.4 (triage) — вместе | |
| Документы | 11.2–11.6, 11.9, 11.10 — Д (threat model, ASVS-матрица, DFD, data classification, risk register, вклад, вопросы к SMI); 11.1 (README, запуск за 30 минут), 11.7 (сценарий демо) — А; 11.8, 0.1, 0.3 — вместе | |

Чтобы срезы не зависели друг от друга: каждый владелец сам описывает эндпоинты своего среза (OpenAPI из кода) и берёт данные из `make seed` (4.4: карточки, запросы, grants и ссылки создаются сразу), а не ждёт чужой срез. Исключение — первые 2–3 дня: срезы стоят на основе (миграция, сессии, RBAC). Пока Диана её делает, Александра занята инфрой, CI и MSW-заготовками, а `make seed` и модели берёт из первой миграции сразу после её пуша. Срезы в защищённых зонах (авторизация, миграции) ревьюит Диана через CODEOWNERS, но это ревью, а не ожидание.

Где что ведём:
- `tasks.md` — полный список, исполнитель и неделя. Галочки ставятся один раз при архивации change (иначе конфликты).
- GitHub Projects — статус: Backlog / Сейчас / Готово. В «Сейчас» у каждой только задачи текущей недели (Н1…Н4), остальное в Backlog. Одна задача — один issue и одна ветка.

Защищённые зоны (владелец — обязательный ревьюер, см. `.github/CODEOWNERS`):
- Александра: CI, `deploy/`, `Makefile`, `docker-compose.yml`, `.env.example`, секреты, конфиги сборки.
- Диана: миграции, авторизация/RBAC, сессии.

Перекрёстное ревью: PR автора всегда смотрит вторая; негативные `TC-*` по спеке она дописывает на ревью (независимая проверка).

Против конфликтов:
- Все роутеры регистрируются в `main.py` один раз в скелете (пустые); модели — по доменам (`app/cards/models.py`…).
- Одна миграция на задачу, цепочка линейная; при двух `alembic heads` ребейзит тот, кто мержится вторым.
- `docs/api/openapi.json` и `src/shared/api/generated/` при конфликте не мержатся руками, а перегенерируются. CI перегенерирует их и падает при расхождении с закоммиченным.
- Lock-файлы (`yarn.lock`, `backend/requirements*.txt` (pip-compile)) при конфликте пересоздаются командой менеджера.
- Ветки на одну задачу, PR ≤ ~300 строк, живут 1–2 дня; `git pull --rebase` от `main` каждое утро; merge через squash.
