# My Desktop App

A small Java Swing desktop application.

## Run on Windows

Install a Java JDK (not just a JRE), then double-click `run.bat` in this folder. The launcher compiles the source and opens the app in a separate window.

You can also run it from PowerShell in this folder:

```powershell
javac -d out src\main\java\com\example\desktopapp\DesktopApp.java
java -cp out com.example.desktopapp.DesktopApp
```

## Project layout

```text
desktop-app/
├── README.md
├── run.bat
└── src/
    └── main/
        └── java/
            └── com/
                └── example/
                    └── desktopapp/
                        └── DesktopApp.java
```
