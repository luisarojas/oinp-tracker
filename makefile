all: build run
run:
	docker run -e PYTHONUNBUFFERED=1 --rm --name oinp-tracker luisacodes/oinp-tracker
build:
	docker build -t luisacodes/oinp-tracker .