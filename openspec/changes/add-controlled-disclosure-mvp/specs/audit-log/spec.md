# Delta for audit-log

## ADDED Requirements

### Requirement: Журналируемые события
Система SHALL записывать в `audit_events` все события из каталога design.md §11 (запросы, решения, grants, ссылки,
просмотры/скачивания, карточки, аутентификация, отказы авторизации, retention). Каждое событие MUST содержать: время UTC,
тип и псевдоним актора, действие, тип и ID объекта, исход (allow/deny/error), HMAC-хеш IP, correlation `request_id`.

#### Scenario: Отказ в доступе журналируется
- **WHEN** viewer получает 404 на чужой материал
- **THEN** в аудите есть `authz.denied` с `actor_ref` viewer-псевдонимом и `object_id` запрошенного материала

### Requirement: Без чувствительного содержимого
Аудит и логи MUST NOT содержать: токены ссылок, session ID, пароли, TOTP, e-mail, `purpose`, `org_name`, `full_description`,
содержимое материалов. Поле `details` формируется по allowlist ключей для каждого типа события.

#### Scenario: Проверка аудита на утечки (TC-LEAK-03)
- **WHEN** после прогона e2e-сценария выполняется поиск по `audit_events` и логам контейнеров известных тестовых значений токена, e-mail, org_name
- **THEN** совпадений нет

### Requirement: Неизменяемость журнала
Роль приложения в БД MUST иметь только `INSERT, SELECT` на `audit_events`; UPDATE/DELETE/TRUNCATE запрещены правами и триггером.
Каждое событие SHALL содержать `hash = SHA-256(prev_hash ‖ канонический JSON события)`; запись выполняется последовательно
(advisory lock). API MUST NOT иметь эндпоинтов изменения/удаления событий.

#### Scenario: Попытка удалить событие (TC-AUD-02)
- **WHEN** от роли `app_rw` выполняется `DELETE FROM audit_events WHERE id = 1`
- **THEN** ошибка прав доступа; событие на месте

#### Scenario: Обнаружение подмены (TC-AUD-03)
- **GIVEN** суперпользователь БД вручную изменил одно событие
- **WHEN** admin запускает проверку целостности (`GET /api/v1/staff/audit/verify`)
- **THEN** отчёт указывает первое событие с нарушенной цепочкой

### Requirement: Просмотр аудита admin'ом
Admin SHALL просматривать аудит с фильтрами (период, действие, объект, исход), постранично, и экспортировать выборку в CSV.
Экспорт сам фиксируется событием `audit.exported`.

#### Scenario: Trace watermark
- **WHEN** admin вводит WM-код со скриншота в инструмент «Trace watermark»
- **THEN** система показывает grant, псевдоним viewer и событие просмотра, к которому относится код
