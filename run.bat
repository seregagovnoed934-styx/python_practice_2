@echo off
setlocal

echo ========================================
echo Checking Code Style (flake8)
echo ========================================
python -m flake8 src tests
if %ERRORLEVEL% neq 0 (
    echo Flake8 checks failed!
    exit /b %ERRORLEVEL%
)

echo ========================================
echo Running Tests with Branch Coverage
echo ========================================
python -m coverage run --branch -m pytest tests
if %ERRORLEVEL% neq 0 (
    echo Tests failed!
    exit /b %ERRORLEVEL%
)

echo ========================================
echo Coverage Summary
echo ========================================
python -m coverage report -m

echo ========================================
echo All checks successfully passed!
echo ========================================
