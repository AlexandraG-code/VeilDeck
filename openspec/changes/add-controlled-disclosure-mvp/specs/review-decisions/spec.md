# Delta for review-decisions

## ADDED Requirements

### Requirement: Очередь запросов для reviewer
Пользователь с ролью `reviewer` SHALL видеть очередь запросов (`GET /api/v1/staff/requests?status=pending`) с полями:
псевдоним запроса, карточка (teaser + org_name), `display_name`, `purpose`, дата. E-mail отображается замаскированным
(`a***@d***.test`); полный e-mail MUST NOT отдаваться в API очереди.

#### Scenario: Reviewer видит очередь
- **GIVEN** reviewer аутентифицирован (пароль + TOTP)
- **WHEN** открывает очередь
- **THEN** видит pending-запросы, отсортированные по дате, с замаскированным e-mail

#### Scenario: Admin не видит содержимое очереди (TC-RBAC-03)
- **WHEN** admin вызывает `GET /api/v1/staff/requests`
- **THEN** ответ 403; admin доступен только агрегат `GET /api/v1/staff/requests/stats`

### Requirement: Ручное решение по запросу
Reviewer SHALL одобрить или отклонить запрос через `POST /api/v1/staff/requests/{rid}/decision`.
При одобрении reviewer MUST задать: `material_ids` (подмножество материалов карточки, ≥ 1), `ttl_hours` (1–168),
`max_views` (1–100), `allow_download` (по умолчанию false). При отказе — `reason_code` (enum) и необязательный внутренний комментарий.
Решение по запросу MUST быть единственным (повторное решение → 409). Автоматическое одобрение MUST NOT существовать.

#### Scenario: Одобрение создаёт grant и ссылку
- **WHEN** reviewer одобряет запрос с 2 материалами, TTL 48 ч, 10 просмотров
- **THEN** создаются `decision`, `grant` (expires_at = now + 48 ч) и `magic_link`; отправлено письмо; события `decision.approved`, `grant.created`, `link.issued`

#### Scenario: Материал другой карточки (TC-VIEW-07)
- **WHEN** в `material_ids` передан ID материала другой карточки
- **THEN** ответ 422, grant не создаётся

#### Scenario: Двойное решение / гонка
- **WHEN** два reviewer одновременно отправляют решения по одному запросу
- **THEN** ровно одно решение сохраняется (UNIQUE `request_id`), второе получает 409

### Requirement: Управление выданным доступом
Reviewer и admin SHALL видеть список активных grants и MUST иметь возможность немедленно отозвать grant
(`POST /api/v1/staff/grants/{gid}/revoke` с `reason`). Reviewer SHALL иметь возможность сократить срок grant (но не продлить сверх 168 ч от решения).

#### Scenario: Немедленный отзыв (TC-VIEW-08)
- **GIVEN** viewer просматривает материалы
- **WHEN** reviewer отзывает grant
- **THEN** все сессии grant удаляются, следующий запрос viewer получает 401, событие `grant.revoked`

#### Scenario: Повторная выдача ссылки
- **WHEN** reviewer нажимает «Перевыпустить ссылку» для активного grant
- **THEN** все неиспользованные ссылки grant инвалидируются, создаётся новая, событие `link.reissued`

### Requirement: Разделение обязанностей
Пользователь с ролью `admin` MUST NOT иметь возможности одобрять запросы; `reviewer` MUST NOT публиковать карточки
и загружать материалы. Проверка выполняется на сервере.

#### Scenario: Admin пытается одобрить (TC-RBAC-04)
- **WHEN** admin вызывает `POST /api/v1/staff/requests/{rid}/decision`
- **THEN** ответ 403, событие `authz.denied`
