.PHONY: compose-up compose-down logs ps test-compose lint-contract clean
compose-up:
	@test -f .env || cp .env.example .env
	docker compose up -d --build
compose-down:
	docker compose down
logs:
	docker compose logs -f
ps:
	docker compose ps
test-compose:
	npm run test:compose
lint-contract:
	npm run lint:contract
clean:
	docker compose down -v --remove-orphans
