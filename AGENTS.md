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
  src/api/generated/   типы и клиент из docs/api/openapi.json — АВТОГЕНЕРАЦИЯ, руками не править
deploy/    docker-compose, nginx, Dockerfile
docs/      docs/security/, docs/api/openapi.json (экспорт в CI)
openspec/  требования
Makefile   make secrets | seed | retention-run NOW_OFFSET=31d
```

Публичные ID — только UUIDv4; bigint наружу не отдаются.

## 5. Backend (FastAPI)

- Слои: `api` (роутеры, зависимости) → `services` (бизнес-логика) → `repositories`/модели → БД. Роутер не содержит бизнес-логики и SQL.
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

**Сгенерированный API:** `src/api/generated/` лежит вне слоёв FSD, алиас `@api`. Генерируется orval из `docs/api/openapi.json`: типы, axios-клиент и хуки TanStack Query, первой строкой каждого файла — «АВТОГЕНЕРАЦИЯ, НЕ ПРАВИТЬ»; в игноре eslint и prettier. Сгенерированные хуки используются в `model/` и `ui/` слайсов; запросы руками не пишутся. Пока бэка нет — моки MSW по той же схеме.

**Алиасы:** `@app @pages @widgets @features @entities @shared @api` — объявляются в `vite.config.ts` (`resolve.alias`) и `tsconfig.app.json` (`paths`); vitest наследует через `mergeConfig`.

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
- **Защищённое — только оркестратор своей зоны** (у каждого участника свой оркестратор, см. §11): `context/*.md`, `team.json`, `registry.json`, конфиги сборки и CI, миграции, авторизация, секреты. Исполнители защищённое не трогают; в чужой зоне правка идёт только через PR с ревью владельца (CODEOWNERS).
- Большие файлы (спеки, PDF, дампы) читаются субагентами с возвратом выжимки.

## 9. Git

Один коммит на задачу. Сообщение — по-русски, с указанием номера задачи из `tasks.md`. `main` защищён, изменения идут через PR. Не коммитить `.env`, секреты, `env-config.ts`.

## 10. Чего не делать

- Не добавлять функциональность вне `openspec/` без нового change.
- Не логировать токены, session ID, пароли, TOTP, e-mail, purpose, org_name.
- Не отдавать оригиналы материалов и не принимать `card_id` viewer-а из запроса (он берётся из сессии).
- Не писать самодельную криптографию, не выключать проверки «на время демо».
- Не публиковать бриф, findings и результаты вовне (соцсети, портфолио); не класть в репозиторий секреты и реальные данные.

## 11. Работа вдвоём: вертикальные срезы

Александра (`AlexandraG-code`) и Диана (`LediDi060`) берут задачи целиком, фронт + бэк + тесты обоих слоёв. Контракт — `docs/api/openapi.json`, который FastAPI генерирует из кода; клиент и хуки фронта генерируются из него (`src/api/generated/`).

Исполнитель каждой задачи указан в `tasks.md`: (А) Александра ≈ 65% (инфра и CI, права админа репозитория, фронт, security-тесты, публичный каталог и просмотр, документы), (Д) Диана ≈ 35% (ядро бэкенда: БД и миграции, сессии, RBAC, staff-аутентификация, решения reviewer, grants, retention). Три общие задачи — (А+Д). Фронт к бэку Дианы пишет Александра по контракту OpenAPI (моки MSW, пока эндпоинта нет).

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
- `docs/api/openapi.json` и `src/api/generated/` при конфликте не мержатся руками, а перегенерируются. CI перегенерирует их и падает при расхождении с закоммиченным.
- Lock-файлы (`yarn.lock`, `backend/requirements*.txt` (pip-compile)) при конфликте пересоздаются командой менеджера.
- Ветки на одну задачу, PR ≤ ~300 строк, живут 1–2 дня; `git pull --rebase` от `main` каждое утро; merge через squash.
