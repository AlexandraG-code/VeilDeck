# Delta for platform-security

## ADDED Requirements

### Requirement: HTTP-заголовки безопасности
nginx SHALL добавлять ко всем ответам: `Strict-Transport-Security: max-age=31536000`, `Content-Security-Policy:
default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; object-src 'none'; base-uri 'none';
frame-ancestors 'none'; form-action 'self'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`,
`Permissions-Policy: camera=(), microphone=(), geolocation=()`, `Cross-Origin-Opener-Policy: same-origin`.
Заголовок `Server` MUST NOT раскрывать версию.

#### Scenario: Проверка заголовков (TC-HDR-01)
- **WHEN** выполняется запрос к `/` и `/api/v1/cards`
- **THEN** все перечисленные заголовки присутствуют, `server_tokens off`

### Requirement: CSRF-защита
Все state-changing запросы (POST/PUT/PATCH/DELETE) MUST требовать заголовок `X-CSRF-Token`, совпадающий с cookie `__Host-csrf`
(double-submit), плюс проверку `Origin`. Cookie сессий — `SameSite=Strict`.

#### Scenario: Запрос без CSRF-токена (TC-API-04)
- **WHEN** POST на `/api/v1/staff/grants/{gid}/revoke` без `X-CSRF-Token`
- **THEN** ответ 403, действие не выполнено

### Requirement: Rate limiting
Система MUST применять лимиты из design.md §12 (Redis, sliding window) и отвечать 429 с заголовком `Retry-After`.
nginx дополнительно ограничивает общий поток (`limit_req`) и размер тела запроса.

#### Scenario: Лимит на рендер (TC-RL-02)
- **WHEN** viewer запрашивает 200 страниц за минуту
- **THEN** запросы сверх 120 получают 429

### Requirement: Обработка ошибок
API MUST возвращать ошибки в едином формате `{"error": {"code": "...", "message": "...", "request_id": "..."}}`
без стек-трейсов, SQL, путей файлов и версий библиотек. `DEBUG`/`docs` FastAPI отключаются в режиме `ENV=demo`,
OpenAPI-схема экспортируется в репозиторий файлом.

#### Scenario: Внутренняя ошибка
- **WHEN** в обработчике происходит исключение
- **THEN** клиент получает 500 с общим сообщением и `request_id`; детали — только в серверном логе (без чувствительных данных)

### Requirement: Секреты и конфигурация
Секреты (`SESSION_SECRET`, `FERNET_KEY`, `HMAC_KEY`, `WM_KEY`, пароли БД) MUST передаваться через env/docker secrets,
генерироваться скриптом `make secrets` и не попадать в git и образы. Приложение MUST не стартовать при отсутствии
секрета или при значении по умолчанию.

#### Scenario: Пустой секрет
- **WHEN** контейнер API запускается без `FERNET_KEY`
- **THEN** процесс завершается с ошибкой конфигурации

### Requirement: Защищённое развёртывание
Docker Compose SHALL поднимать: nginx, api, worker, postgres, redis, mailpit. Контейнеры api/worker/nginx MUST работать от non-root,
с `read_only: true` (+ tmpfs для временных файлов), `cap_drop: [ALL]`, `no-new-privileges`, базовые образы pinned по digest.
Наружу публикуется только 443 (и 8025 Mailpit на 127.0.0.1). Postgres и Redis недоступны с хоста.
Redis MUST требовать пароль. TLS — самоподписанный сертификат через mkcert для `localhost`.

#### Scenario: Проверка поверхности
- **WHEN** выполняется `docker compose ps` и сканирование портов хоста
- **THEN** открыты только 443 и 127.0.0.1:8025

### Requirement: CI security baseline
CI (GitHub Actions/GitLab CI в приватном репо) SHALL на каждый PR выполнять: lint + тесты backend/frontend,
SAST (Semgrep, Bandit), SCA (pip-audit, npm audit), secret scan (gitleaks), сканирование образов (Trivy), генерацию SBOM (Syft, CycloneDX).
Merge в `main` MUST блокироваться при findings уровня High/Critical без оформленного исключения
(файл `security/exceptions.yaml`: owner, обоснование, срок пересмотра).

#### Scenario: Найден секрет
- **WHEN** в PR добавлен тестовый hard-coded ключ
- **THEN** job gitleaks падает, merge заблокирован
