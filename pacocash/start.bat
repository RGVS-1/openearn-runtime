@echo off
chcp 65001 > nul
title PacoCash Farm Bot v1.0
cd /d "%~dp0"
"C:\Users\hoaki\AppData\Local\Programs\Python\Python310\python.exe" main.py
pause
