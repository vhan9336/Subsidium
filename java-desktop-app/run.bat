@echo off
setlocal
cd /d "%~dp0"

where javac >nul 2>nul
if errorlevel 1 (
    echo A Java JDK is required to run this app. Install a JDK and reopen this window.
    pause
    exit /b 1
)

if not exist out mkdir out
javac -d out src\main\java\com\example\desktopapp\DesktopApp.java
if errorlevel 1 (
    echo Compilation failed.
    pause
    exit /b 1
)

java -cp out com.example.desktopapp.DesktopApp
if errorlevel 1 (
    echo The app exited with an error.
    pause
    exit /b 1
)
