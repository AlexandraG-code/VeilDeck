# Delta for protected-content

## ADDED Requirements

### Requirement: Расширенная карточка для viewer
Система SHALL отдавать viewer расширенное представление карточки его grant (`GET /api/v1/viewer/card`):
teaser-поля, `org_name`, `full_description`, список разрешённых материалов (id, название, число страниц),
срок действия grant и остаток просмотров. Материалы вне grant MUST NOT перечисляться.

#### Scenario: Viewer видит только разрешённое
- **GIVEN** у карточки 4 материала, grant разрешает 2
- **WHEN** viewer открывает расширенную карточку
- **THEN** в ответе ровно 2 материала

### Requirement: Просмотр страниц с персональным watermark
Система SHALL отдавать страницы материалов как растровые изображения (PNG, ≤ 150 dpi) через
`GET /api/v1/viewer/materials/{mid}/pages/{n}`, с нанесённым на сервере watermark: псевдоним viewer, время UTC,
WM-код (HMAC от grant_id и view_id). Оригинальный файл MUST NOT отдаваться ни по какому URL.
Каждый просмотр страницы увеличивает счётчик просмотров (одна «сессия просмотра» материала = 1 view) и пишется в аудит.

#### Scenario: Watermark присутствует (TC-WM-01)
- **WHEN** viewer получает страницу
- **THEN** на изображении читается псевдоним viewer и WM-код, совпадающий с событием `material.page_viewed` в аудите

#### Scenario: Параметры не влияют на watermark (TC-WM-02)
- **WHEN** к запросу добавлены `?wm=0`, `?viewer=other` или заголовок `X-Watermark: off`
- **THEN** watermark идентичен обычному, параметры игнорируются

#### Scenario: Нет прямого доступа к оригиналу (TC-WM-03)
- **WHEN** выполняется перебор путей `/files/`, `/storage/`, `/static/<storage_key>`, `/api/v1/materials/{mid}/raw`
- **THEN** все ответы 404, содержимое оригинала не возвращается

#### Scenario: Лимит просмотров исчерпан
- **GIVEN** `views_used == max_views`
- **WHEN** viewer открывает новый материал
- **THEN** ответ 403 «Лимит просмотров исчерпан», событие `grant.views_exhausted`

#### Scenario: Гонка лимита просмотров (TC-RACE-02)
- **WHEN** параллельно отправлено 20 запросов при остатке 1 просмотр
- **THEN** засчитан и выдан не более чем 1 новый просмотр (атомарный `UPDATE ... SET views_used = views_used + 1 WHERE views_used < max_views`)

### Requirement: Скачивание watermarked PDF
Если `grant.allow_download = true`, viewer SHALL иметь возможность скачать PDF, собранный из watermarked-растров (без текстового слоя).
Иначе эндпоинт скачивания MUST возвращать 403.

#### Scenario: Скачивание запрещено
- **GIVEN** `allow_download = false`
- **WHEN** viewer вызывает `GET /api/v1/viewer/materials/{mid}/download`
- **THEN** ответ 403, событие `material.download_denied`

### Requirement: Защита от утечек через кеш и Referer
Все ответы `/api/v1/viewer/*` и `/api/v1/staff/*` MUST содержать `Cache-Control: no-store`, `Pragma: no-cache`;
весь сайт — `Referrer-Policy: no-referrer`. Изображения страниц MUST NOT иметь стабильных URL, кешируемых между сессиями.

#### Scenario: No-store на контенте (TC-LEAK-04)
- **WHEN** проверяются заголовки ответа страницы материала
- **THEN** присутствует `Cache-Control: no-store`

#### Scenario: Нет утечки через Referer (TC-LEAK-02)
- **WHEN** на расширенной странице есть внешняя ссылка и viewer переходит по ней
- **THEN** заголовок `Referer` не отправляется

### Requirement: Честная коммуникация ограничений
UI viewer SHALL показывать уведомление: доступ персональный, просмотры фиксируются, материалы содержат персональную метку;
UI MUST NOT утверждать, что копирование невозможно.

#### Scenario: Уведомление на странице материалов
- **WHEN** viewer открывает расширенную карточку
- **THEN** видит баннер о персональном watermark и аудите
