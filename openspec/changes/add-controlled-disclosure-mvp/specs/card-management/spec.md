# Delta for card-management

## ADDED Requirements

### Requirement: CRUD карточек admin'ом
Admin SHALL создавать и редактировать карточки в статусе `draft` (`/api/v1/staff/cards`), публиковать (`publish`)
и архивировать (`archive`). Опубликованную карточку нельзя редактировать без перевода в `draft` (снимается с публикации).
Все данные карточек MUST быть синтетическими.

#### Scenario: Создание черновика
- **WHEN** admin создаёт карточку с teaser- и confidential-полями
- **THEN** карточка в статусе `draft`, не видна публично, событие `card.created`

#### Scenario: Архивирование с активными grants
- **GIVEN** у карточки есть активные grants
- **WHEN** admin архивирует карточку
- **THEN** система требует подтверждения и при подтверждении отзывает все grants карточки (`grant.revoked`, reason=`card_archived`)

### Requirement: Teaser только из обобщённых значений
Поля `industry`, `region_macro`, `size_band`, `revenue_band`, `deal_type` MUST быть значениями enum.
`title_generic` ≤ 80 символов, `teaser_text` ≤ 600 символов.

#### Scenario: Точная выручка не принимается
- **WHEN** admin передаёт `revenue_band: "12 345 678 EUR"`
- **THEN** ответ 422

### Requirement: Линтер утечек при публикации
Перед публикацией система SHALL проверять `title_generic` и `teaser_text` и MUST блокировать публикацию, если найдено:
вхождение `org_name` или любого `org_aliases` (без учёта регистра, с транслитерацией RU↔EN), URL/домен, e-mail, телефон,
ИНН/ОГРН/VAT-подобная последовательность цифр. Ответ содержит список найденных нарушений.

#### Scenario: Название компании в teaser (TC-CARD-04)
- **GIVEN** `org_name = "Nordlicht Logistik GmbH"`, в `teaser_text` есть «nordlicht»
- **WHEN** admin нажимает «Опубликовать»
- **THEN** ответ 422 с нарушением `org_name_in_teaser`, карточка остаётся `draft`

### Requirement: Предупреждение об уникальной комбинации признаков
При публикации система SHALL вычислять число опубликованных карточек с той же комбинацией
(`industry`, `region_macro`, `size_band`, `revenue_band`). Если их 0 (карточка будет уникальной), система SHALL показать
предупреждение и потребовать явного подтверждения admin, которое фиксируется в аудите (`card.publish_k_warning_ack`).

#### Scenario: Уникальная комбинация
- **WHEN** admin публикует карточку с уникальной комбинацией
- **THEN** публикация требует подтверждения, подтверждение пишется в аудит

### Requirement: Загрузка синтетических материалов
Admin SHALL загружать материалы к карточке: только PDF, PNG, JPEG; ≤ 10 МБ на файл, ≤ 10 файлов на карточку, ≤ 30 страниц PDF.
Тип MUST проверяться по сигнатуре (magic bytes) и совпадать с расширением и заявленным MIME. Файл сохраняется под случайным
`storage_key` вне веб-корня; PDF с JavaScript/встроенными файлами/шифрованием MUST отклоняться. Вычисляется SHA-256.

#### Scenario: Двойное расширение / подмена MIME
- **WHEN** загружается `report.pdf.exe` или PNG с заголовком `Content-Type: application/pdf`
- **THEN** ответ 422, событие `material.upload_rejected`

#### Scenario: Превышение размера
- **WHEN** загружается файл 11 МБ
- **THEN** запрос отклоняется (413 на nginx или 422 на API), файл не сохраняется

### Requirement: Генератор синтетических данных
Репозиторий SHALL содержать команду `make seed`, создающую ≥ 10 синтетических карточек, PDF-материалы (reportlab/Faker,
с пометкой «SYNTHETIC — FOR TESTING ONLY» на каждой странице), staff-аккаунты reviewer и admin с выводом TOTP-секретов в консоль.

#### Scenario: Сид на чистой БД
- **WHEN** выполнен `make seed` после `docker compose up`
- **THEN** каталог содержит опубликованные карточки, логины тестовых сотрудников выведены в консоль
