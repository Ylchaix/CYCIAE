@echo off
for %%x in ("%~dp0*.exe") do (
    reg add "HKCU\Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers" /v "%%~fx" /t REG_SZ /d "WINXPSP2 256COLOR HIGHDPIAWARE" /f
)
echo Done.
pause
