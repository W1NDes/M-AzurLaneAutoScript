@echo off
cd /d "%~dp0"

echo Installing dependencies...
call npm install --legacy-peer-deps

echo Building...
set MODE=production
call npm run build

echo Packaging...
call npx electron-builder build --config electron-builder.config.js --dir

echo Copying to toolkit\webapp...
xcopy /E /Y "dist\win-unpacked\*" "..\toolkit\webapp\"

echo Done!
pause
