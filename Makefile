.PHONY: all run

ifneq (,$(wildcard ./.env))
    include .env
    export
endif

all: run

install:
	@echo "Installing dependencies..."
	@python3 -m venv venv
	@source venv/bin/activate && pip install -r requirements.txt

run:
	@echo "Running the application..."
	@fastapi dev src/image_generator/main.py

write-deps:
	@echo "Updating dependencies..."
	@source venv/bin/activate && pip freeze > requirements.txt

build:
	@echo "Building the application..."
	@docker build -t image-generator .
