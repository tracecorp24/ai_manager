@echo off
title NautiGraph TR - B2B Denizcilik Kimlik Grafigi, Toplayici Kuyruk ve CRM
cls
echo =====================================================================
echo   NAUTIGRAPH TR -- B2B DENIZCILIK, TEKNE ^& YAT TASARIMI PLATFORMU
echo   Toplayici Kuyrugu (Crawler Engine) + Kimlik Grafigi + CRM
echo =====================================================================
echo.
echo Sunucu baslatiliyor... Lutfen bu pencereyi ACIK tutun.
echo Bu CMD penceresi kapatildiginda sunucu sureci tamamen duracaktir.
echo.

cd /d "%~dp0"

where py >nul 2>&1
if %errorlevel% equ 0 (
  py -3 app.py
  pause
  exit /b
)

where python >nul 2>&1
if %errorlevel% equ 0 (
  python app.py
  pause
  exit /b
)

echo HATA: Python 3 bulunamadi. Lutfen Python'un kurulu ve PATH'e ekli oldugundan emin olun.
pause
