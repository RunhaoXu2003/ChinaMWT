@echo off
python -X utf8 "%~dp0launch.py" %*
if errorlevel 1 pause
