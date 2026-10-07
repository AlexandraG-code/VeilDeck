.PHONY: secrets certs up down seed retention-run

SECRETS_FILE := .env

# Генерирует .env со случайными ключами; существующий файл не перезаписывается (SR-32).
secrets:
	@test ! -f $(SECRETS_FILE) || { echo "$(SECRETS_FILE) уже есть, удалите его, чтобы пересоздать"; exit 1; }
	@python3 -c 'import base64,secrets;r=lambda:secrets.token_urlsafe(48);print("ENV=demo");print("POSTGRES_PASSWORD="+r());print("APP_RW_PASSWORD="+r());print("SESSION_SECRET="+r());print("HMAC_KEY="+r());print("WM_KEY="+r());print("FERNET_KEY="+base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())' > $(SECRETS_FILE)
	@chmod 600 $(SECRETS_FILE)
	@echo "Создан $(SECRETS_FILE)"

# Сертификат для localhost: mkcert, если установлен (доверенный), иначе самоподписанный openssl (браузер предупредит).
certs:
	@mkdir -p deploy/certs
	@if command -v mkcert >/dev/null 2>&1; then \
		mkcert -cert-file deploy/certs/localhost.pem -key-file deploy/certs/localhost-key.pem localhost 127.0.0.1 ::1; \
	else \
		echo "mkcert не найден: самоподписанный сертификат (brew install mkcert && mkcert -install для доверенного)"; \
		openssl req -x509 -newkey rsa:2048 -nodes -days 30 -subj "/CN=localhost" -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" \
			-keyout deploy/certs/localhost-key.pem -out deploy/certs/localhost.pem 2>/dev/null; \
	fi
	@chmod 600 deploy/certs/localhost-key.pem

up: certs
	docker compose -f deploy/docker-compose.yml --env-file .env up -d --build

down:
	docker compose -f deploy/docker-compose.yml --env-file .env down

seed:
	@echo "TODO: задача 4.4"

retention-run:
	@echo "TODO: задача 8.2 (NOW_OFFSET=$(NOW_OFFSET))"
