@echo off
title EKO Recon - Backend
rem %~dp0 = this script's directory, so the repo can live anywhere
cd /d "%~dp0backend"
echo Starting EKO Reconciliation Backend on port 8000...
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
pause
