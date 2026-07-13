@echo off
echo Stopping AI-Lab...
taskkill /f /im python.exe /fi "WINDOWTITLE eq AI-Lab*" 2>nul
echo Done.