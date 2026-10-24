@echo off
title Jacinto AI
cd /d "%~dp0"

rem Deixa o Ollama leve: um modelo por vez, sem pedidos em paralelo
set OLLAMA_MAX_LOADED_MODELS=1
set OLLAMA_NUM_PARALLEL=1

echo Ligando o Ollama...
start "" /min ollama serve
timeout /t 4 /nobreak >nul

rem Baixa a prioridade do Ollama para o Windows e o navegador nao travarem
powershell -NoProfile -Command "Get-Process | Where-Object { $_.Name -like 'ollama*' } | ForEach-Object { try { $_.PriorityClass = 'BelowNormal' } catch {} }"

echo.
echo ================================================
echo  No celular (mesmo Wi-Fi), abra um destes enderecos:
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do echo     http://%%a:8501
echo ================================================
echo.

streamlit run app.py --server.address 0.0.0.0 --server.fileWatcherType none --server.runOnSave false --browser.gatherUsageStats false
pause
