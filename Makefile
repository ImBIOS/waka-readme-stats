.ONESHELL:
.DEFAULT_GOAL = help
.EXPORT_ALL_VARIABLES:

ENV = .env.example
include $(ENV)

help:
	@echo "Welcome to 'waka-readme-stats' GitHub Actions!"
	@echo "Test locally with: 'make run-locally'"
	@echo "Build container with: 'make run-container'"
	@echo "Clean build files with: 'make clean'"
.PHONY: help

install:
	@echo "Installing dependencies using pipenv"
	pipenv install --dev

run-locally: install
	@echo "Running action locally"
	mkdir -p ./assets/ || true
	pipenv run python3 ./sources/main.py
.PHONY: run-locally

run-container:
	@echo "Building and running container"
	docker build -t waka-readme-stats -f Dockerfile .
	docker run --env-file $(ENV) -v $(CURDIR)/assets/:/waka-readme-stats/assets/ waka-readme-stats
.PHONY: run-container

lint: install
	@echo "Running linters"
	pipenv run flake8 --max-line-length=160 --exclude venv,assets .
	pipenv run black --line-length=160 --exclude='/venv/|/assets/' .
.PHONY: lint

clean:
	@echo "Cleaning build files"
	@venv_path=$$(pipenv --venv 2>/dev/null); \
	[ -n "$$venv_path" ] && rm -rf "$$venv_path" || true
	rm -rf assets
	rm -f package*.json
	docker rm -f waka-readme-stats 2>/dev/null || true
	docker rmi $$(docker images | grep "waka-readme-stats" | awk '{print $$3}') 2>/dev/null || true
.PHONY: clean
