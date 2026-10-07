.PHONY: secrets up down seed retention-run

SECRETS_FILE := .env

# Генерирует .env со случайными ключами; существующий файл не перезаписывается (SR-32).
secrets:
	@test ! -f $(SECRETS_FILE) || { echo "$(SECRETS_FILE) уже есть, удалите его, чтобы пересоздать"; exit 1; }
	@python3 -c 'import base64,secrets;r=lambda:secrets.token_urlsafe(48);print("ENV=demo");print("POSTGRES_PASSWORD="+r());print("APP_RW_PASSWORD="+r());print("SESSION_SECRET="+r());print("HMAC_KEY="+r());print("WM_KEY="+r());print("FERNET_KEY="+base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())' > $(SECRETS_FILE)
	@chmod 600 $(SECRETS_FILE)
	@echo "Создан $(SECRETS_FILE)"

up:
	docker compose -f deploy/docker-compose.yml --env-file .env up -d --build

down:
	docker compose -f deploy/docker-compose.yml --env-file .env down

seed:
	@echo "TODO: задача 4.4"

retention-run:
	@echo "TODO: задача 8.2 (NOW_OFFSET=$(NOW_OFFSET))"
