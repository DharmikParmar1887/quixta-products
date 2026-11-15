#!/bin/bash
# Run the unit tests with coverage (same flow as data-lake-service).
# Load .env first if you want them to run against PostgreSQL: set -a; source .env; set +a
set -e

echo "Unit Testing the services"
coverage run -m pytest
coverage report -m
