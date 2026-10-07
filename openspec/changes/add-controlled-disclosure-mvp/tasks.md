# Tasks: Controlled Disclosure MVP

Теги: [BE] backend, [FE] frontend, [OPS] DevSecOps/инфраструктура, [SEC] security-тесты и анализ, [DOC] документация.
Ориентир по неделям: Н1 7–13 окт · Н2 14–20 окт · Н3 21–27 окт · Н4 28 окт–3 ноя (сдача) · далее — доводка к защите в декабре.

## 0. Организация (Н1)
- [ ] 0.1 [DOC] Распределить роли из брифа §8 между двумя участниками и записать в README (кто за что лично отвечает)
- [ ] 0.2 [OPS] Приватный репозиторий, защищённая ветка `main`, PR-only, обязательные status checks
- [ ] 0.3 [DOC] Уточнить у координатора/SMI контрольные даты и формат сдачи; зафиксировать в decision log

## 1. Каркас проекта (Н1)
- [ ] 1.1 [OPS] Структура репо: `backend/`, `frontend/`, `deploy/`, `docs/security/`, `openspec/`, `Makefile`
- [ ] 1.2 [OPS] `docker-compose.yml`: nginx, api, worker, postgres, redis, mailpit; сети `edge` и `data (internal)`
- [ ] 1.3 [OPS] `make secrets` — генерация `.env` со случайными ключами; `.env` в `.gitignore`; pre-commit с gitleaks
- [ ] 1.4 [OPS] mkcert-сертификат для `localhost`, nginx с TLS и заголовками безопасности
- [ ] 1.5 [BE] FastAPI-скелет: конфиг (pydantic-settings, fail-fast на пустых секретах), `/healthz`, единый формат ошибок, `request_id`
- [ ] 1.6 [BE] SQLAlchemy 2 + Alembic; роли БД `app_owner`/`app_rw`; первая миграция со всеми таблицами из design §2
- [ ] 1.7 [BE] Триггер и REVOKE для `audit_events`
- [ ] 1.8 [FE] Vite + React + TS, роутинг (публичная зона / viewer / staff), TanStack Query, API-клиент с CSRF-заголовком
- [ ] 1.9 [OPS] Dockerfile backend и frontend: multi-stage, non-root, pinned base image, read-only rootfs

## 2. Безопасная основа (Н1–Н2)
- [ ] 2.1 [BE] Сервис аудита: allowlist `details`, hash-цепочка под advisory lock, IP → HMAC
- [ ] 2.2 [BE] Сессии в Redis (staff и viewer раздельно), `__Host-` cookies, idle/absolute TTL, индекс `grant_sessions`
- [ ] 2.3 [BE] CSRF double-submit + проверка Origin (middleware)
- [ ] 2.4 [BE] Rate limiter (Redis sliding window) как dependency с параметрами из platform-security
- [ ] 2.5 [BE] RBAC-dependency `require_role(...)`, `require_viewer_grant()`; тест обхода `app.routes` (deny by default)
- [ ] 2.6 [BE] Логирование: structlog/json, фильтр-редактор чувствительных ключей

## 3. Staff-аутентификация (Н2)
- [ ] 3.1 [BE] CLI `create-staff` (argon2id, генерация TOTP-секрета, вывод otpauth URI)
- [ ] 3.2 [BE] `POST /staff/auth/login` (пароль+TOTP, dummy-hash, lockout, защита от повтора TOTP), `logout`, `me`
- [ ] 3.3 [BE] Деактивация/активация reviewer admin'ом с удалением сессий
- [ ] 3.4 [FE] Страница входа staff, обработка 401/423/429, автологаут по idle
- [ ] 3.5 [SEC] Тесты TC-AUTH-01..05

## 4. Карточки и материалы (Н2)
- [ ] 4.1 [BE] CRUD карточек (draft/publish/archive), Pydantic `extra="forbid"`, enum-поля
- [ ] 4.2 [BE] Линтер утечек teaser (нормализация, транслит, regex домен/e-mail/телефон/ИНН) + k-предупреждение
- [ ] 4.3 [BE] Загрузка материалов: magic bytes (python-magic/filetype), лимиты, проверка PDF на JS/вложения/шифрование (PyMuPDF), случайный `storage_key`, SHA-256
- [ ] 4.4 [BE] `make seed`: синтетические карточки и PDF (Faker + reportlab, плашка SYNTHETIC)
- [ ] 4.5 [FE] Админка: список карточек, форма карточки (react-hook-form + zod), загрузка материалов, вывод нарушений линтера, подтверждение k-предупреждения
- [ ] 4.6 [SEC] Тесты TC-CARD-04, загрузка с двойным расширением/подменой MIME/размером

## 5. Публичный каталог и запросы (Н2–Н3)
- [ ] 5.1 [BE] `GET /cards`, `GET /cards/{id}` — только teaser-поля (отдельная response-схема), пагинация ≤ 20, фильтры enum
- [ ] 5.2 [BE] `POST /cards/{id}/access-requests`: валидация, Fernet + HMAC для e-mail, единообразный 202, honeypot, лимиты
- [ ] 5.3 [FE] Каталог, карточка, форма запроса, экран «Запрос получен»
- [ ] 5.4 [SEC] Тесты TC-CAT-01..03, TC-API-02..03, TC-RL-01, TC-LEAK-05

## 6. Решения reviewer (Н3)
- [ ] 6.1 [BE] Очередь запросов с маскированием e-mail; stats для admin
- [ ] 6.2 [BE] Решение approve/reject в одной транзакции: decision + grant + magic_link; UNIQUE на request_id
- [ ] 6.3 [BE] Отправка писем через Mailpit (шаблоны без confidential-данных)
- [ ] 6.4 [BE] Список grants, revoke (удаление сессий), сокращение срока, перевыпуск ссылки
- [ ] 6.5 [FE] Интерфейс reviewer: очередь, карточка запроса, форма решения (выбор материалов, TTL, лимит, скачивание), активные grants, отзыв
- [ ] 6.6 [SEC] Тесты TC-RBAC-02..04, TC-VIEW-07, гонка решений

## 7. Доступ viewer и защищённый контент (Н3)
- [ ] 7.1 [BE] `POST /access/redeem` — атомарный одноразовый обмен, cookie, аудит
- [ ] 7.2 [BE] Проверка grant на каждый запрос viewer (dependency), атомарный счётчик просмотров
- [ ] 7.3 [BE] Рендер страниц PyMuPDF → PNG, watermark Pillow (псевдоним, время, WM-код HMAC), no-store
- [ ] 7.4 [BE] Скачивание watermarked PDF при `allow_download`
- [ ] 7.5 [BE] Инструмент «Trace watermark» для admin
- [ ] 7.6 [FE] `/access` — чтение fragment, `replaceState`, redeem, ошибки 410/429
- [ ] 7.7 [FE] Просмотрщик: расширенная карточка, постраничный просмотр, баннер о watermark, таймер срока, logout
- [ ] 7.8 [SEC] Тесты TC-LINK-02..05, TC-VIEW-05..08, TC-WM-01..03, TC-RACE-01..02, TC-LEAK-01..04, TC-RL-02

## 8. Аудит и retention (Н3–Н4)
- [ ] 8.1 [BE] Просмотр аудита (фильтры, пагинация), CSV-экспорт, `audit/verify`
- [ ] 8.2 [BE] Retention-джобы в worker + `make retention-run NOW_OFFSET=...`
- [ ] 8.3 [BE] Ручное обезличивание запроса и удаление материала
- [ ] 8.4 [FE] Страница аудита и trace watermark в админке
- [ ] 8.5 [SEC] Тесты TC-AUD-02..03, TC-LEAK-03, retention-сценарии

## 9. CI/CD (Н2–Н4, параллельно)
- [ ] 9.1 [OPS] Pipeline: lint (ruff, eslint), тесты (pytest, vitest), Semgrep, Bandit, pip-audit, npm audit, gitleaks, Trivy, Syft SBOM
- [ ] 9.2 [OPS] Release gate: High/Critical блокируют merge; `security/exceptions.yaml` с owner/обоснованием/сроком
- [ ] 9.3 [OPS] Минимальные permissions CI, нет секретов в PR из форков, срок хранения артефактов 14 дней
- [ ] 9.4 [SEC] Демонстрация: hard-coded secret блокирует PR; уязвимая зависимость → finding → fix → зелёный прогон
- [ ] 9.5 [OPS] Экспорт OpenAPI в `docs/api/openapi.json` в CI

## 10. Ручное тестирование безопасности (Н4)
- [ ] 10.1 [SEC] Test plan по WSTG 4.2 (authn, authz, session, input validation, business logic, client-side)
- [ ] 10.2 [SEC] Прогон OWASP ZAP baseline + ручные проверки в Burp/ZAP по abuse cases из threat model
- [ ] 10.3 [SEC] Отчёт: findings, severity, remediation, повторная проверка

## 11. Документация и сдача (Н4)
- [ ] 11.1 [DOC] README: запуск ≤ 30 мин с нуля (проверить на чистой машине/VM), assumptions, границы scope
- [ ] 11.2 [DOC] Архитектурная схема, DFD (уровни 0 и 1), trust boundaries, модель данных, матрица доступа (из design.md)
- [ ] 11.3 [DOC] Threat model ≥ 12 угроз с приоритетом и планом обработки (design §5 → отдельный документ)
- [ ] 11.4 [DOC] Data classification, minimisation, retention/deletion matrix
- [ ] 11.5 [DOC] ASVS traceability matrix: заполнить точные ID v5.0.0-x.y.z, связать риск → требование → контроль → тест → результат
- [ ] 11.6 [DOC] Risk register, residual risk statement (design §10), decision log, известные ограничения
- [ ] 11.7 [DOC] Сценарий демо 15–20 мин: каталог → запрос → одобрение → письмо в Mailpit → просмотр с watermark → попытка повторной ссылки → IDOR → отзыв → аудит и trace watermark → CI блокирует секрет
- [ ] 11.8 [DOC] Презентация и handover-пакет
