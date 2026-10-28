# -----------------
# Setup
# -----------------
install:
	pip install -r requirements.txt

update:
	pip freeze > requirements.txt


# -----------------
# DEV
# -----------------
run-dev:
	@echo "Starting DEV environment..."
	honcho -f Procfile.dev start


# -----------------
# PROD
# -----------------
run-prod:
	@echo "Starting PROD environment..."
	honcho -f Procfile.prod start


