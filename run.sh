#!/usr/bin/env bash
set -e

echo "========================================"
echo "Checking Code Style (flake8)"
echo "========================================"
python -m flake8 src tests

echo "========================================"
echo "Running Tests with Branch Coverage"
echo "========================================"
python -m coverage run --branch -m pytest tests

echo "========================================"
echo "Coverage Summary"
echo "========================================"
python -m coverage report -m

echo "========================================"
echo "All checks successfully passed!"
echo "========================================"
