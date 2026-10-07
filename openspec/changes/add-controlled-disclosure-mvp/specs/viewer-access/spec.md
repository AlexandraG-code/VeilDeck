# Delta for viewer-access

## ADDED Requirements

### Requirement: Одноразовая ссылка доступа
При одобрении система SHALL генерировать токен `secrets.token_urlsafe(32)` (≥ 256 бит), хранить в БД только SHA-256 хеш,
TTL 30 минут. Ссылка имеет вид `https://<host>/access#t=<token>` (токен во fragment). Токен MUST NOT попадать в логи,
аудит, ответы API и заголовки `Referer`.

#### Scenario: Токен не логируется (TC-LEAK-01)
- **WHEN** viewer открывает ссылку и выполняет redeem
- **THEN** в логах nginx, API и в аудите отсутствует значение токена

#### Scenario: SPA убирает токен из адресной строки
- **WHEN** SPA загружает `/access#t=...`
- **THEN** токен считывается, fragment удаляется через `history.replaceState` до любого другого сетевого запроса

### Requirement: Обмен ссылки на сессию (redeem)
Система SHALL обменивать токен на viewer-сессию через `POST /api/v1/access/redeem {token}`. Операция MUST быть атомарной
(`UPDATE ... WHERE used_at IS NULL AND expires_at > now() RETURNING`), одноразовой и успешной только при активном grant.
Сессия выдаётся в cookie `__Host-vsid` (HttpOnly, Secure, SameSite=Strict, Path=/) и привязана к одному `grant_id`.

#### Scenario: Успешный redeem
- **GIVEN** действующая неиспользованная ссылка, grant активен
- **WHEN** выполнен redeem
- **THEN** ответ 200, установлена cookie, `used_at` проставлен, событие `link.redeemed` с ip_hash и user-agent

#### Scenario: Повторное использование (TC-LINK-02)
- **WHEN** тот же токен используется второй раз (в т.ч. с другого браузера)
- **THEN** ответ 410 с общим текстом «Ссылка недействительна», событие `link.reuse_attempt`

#### Scenario: Истёкшая ссылка (TC-LINK-03)
- **WHEN** токен использован через 31 минуту после выдачи
- **THEN** ответ 410, событие `link.expired_attempt`

#### Scenario: Ссылка после отзыва grant (TC-LINK-04)
- **WHEN** grant отозван до redeem
- **THEN** ответ 410, сессия не создаётся

#### Scenario: Перебор токенов (TC-LINK-05)
- **WHEN** с одного IP отправлено более 10 неудачных redeem за 10 минут
- **THEN** последующие запросы получают 429, событие `link.bruteforce_suspected`

#### Scenario: Двойной redeem одновременно (TC-RACE-01)
- **WHEN** два параллельных redeem одного токена
- **THEN** ровно один получает 200, второй 410

### Requirement: Жизненный цикл viewer-сессии
Viewer-сессия MUST иметь idle-таймаут 15 мин и абсолютный срок min(8 ч, `grant.expires_at`).
Каждый запрос viewer MUST повторно проверять в БД: grant не отозван, не истёк, `views_used < max_views` (для просмотра страниц).
Viewer SHALL иметь возможность завершить сессию (`POST /api/v1/viewer/logout`), что удаляет её на сервере.

#### Scenario: Истечение grant во время сессии
- **GIVEN** активная сессия
- **WHEN** наступает `grant.expires_at`
- **THEN** следующий запрос получает 401, сессия удалена

#### Scenario: Подмена cookie
- **WHEN** запрос содержит произвольное значение `__Host-vsid`
- **THEN** ответ 401, событие `session.invalid`

### Requirement: Viewer ограничен одним объектом
Viewer-сессия SHALL давать доступ только к карточке `grant.card_id` и материалам из `grant.material_ids`.
Эндпоинты viewer MUST NOT принимать `card_id` из запроса — карточка определяется по сессии.

#### Scenario: IDOR на материал (TC-VIEW-05)
- **WHEN** viewer запрашивает `/api/v1/viewer/materials/{mid}` с `mid`, не входящим в его grant
- **THEN** ответ 404, событие `authz.denied` с `object_id`

#### Scenario: Попытка доступа к staff API (TC-RBAC-01)
- **WHEN** viewer с валидной сессией вызывает `/api/v1/staff/*`
- **THEN** ответ 401 (viewer-сессия не является staff-сессией)
