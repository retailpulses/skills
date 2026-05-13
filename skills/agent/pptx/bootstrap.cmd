@echo off
REM Bootstrap pptx skill dependencies on Windows (cmd.exe).
REM
REM Mirrors bootstrap.sh: idempotent, fingerprint-based skip,
REM cleans node_modules when fingerprint changes (handles sharp ABI mismatch).
REM
REM Note: in the Phoenix runtime, agent commands prefer Git Bash, which can
REM call bootstrap.sh directly. This .cmd is a fallback for native cmd.exe
REM and PowerShell environments.

setlocal enabledelayedexpansion
cd /d "%~dp0"

REM --- Preflight ----------------------------------------------------
where node >nul 2>&1
if errorlevel 1 (
  echo [bootstrap] ERROR: node not found in PATH 1>&2
  exit /b 1
)
where npm >nul 2>&1
if errorlevel 1 (
  echo [bootstrap] ERROR: npm not found in PATH 1>&2
  exit /b 1
)

for /f %%v in ('node -p "process.versions.node.split(\".\")[0]"') do set NODE_MAJOR=%%v
if %NODE_MAJOR% LSS 18 (
  echo [bootstrap] ERROR: Node ^>= 18.17 required 1>&2
  exit /b 1
)

REM --- Fingerprint (package.json sha256 + node major + platform/arch) ---
for /f %%h in ('node -e "const c=require('crypto'),f=require('fs');console.log(c.createHash('sha256').update(f.readFileSync('package.json')).digest('hex'))"') do set PKG_HASH=%%h
for /f %%p in ('node -p "process.platform"') do set PLATFORM=%%p
for /f %%a in ('node -p "process.arch"') do set ARCH=%%a
set FINGERPRINT=%PKG_HASH%^|node%NODE_MAJOR%^|%PLATFORM%-%ARCH%

set STAMP_DIR=node_modules\.cache
set STAMP_FILE=%STAMP_DIR%\pptx-bootstrap.stamp

REM --- Skip if up-to-date -------------------------------------------
if exist "%STAMP_FILE%" (
  set /p EXISTING=<"%STAMP_FILE%"
  if "!EXISTING!"=="%FINGERPRINT%" (
    echo [bootstrap] up-to-date ^(%PLATFORM%-%ARCH%, node%NODE_MAJOR%^)
    exit /b 0
  )
)

REM --- Reinstall ----------------------------------------------------
echo [bootstrap] installing node deps for %PLATFORM%-%ARCH% ^(node%NODE_MAJOR%^)...

if exist "%STAMP_FILE%" (
  echo [bootstrap] fingerprint changed, removing old node_modules...
  if exist node_modules rmdir /s /q node_modules
)

if exist package-lock.json (
  call npm ci --no-audit --no-fund --loglevel=error
) else (
  call npm install --no-audit --no-fund --loglevel=error
)
if errorlevel 1 exit /b 1

echo [bootstrap] ensuring Playwright Chromium is installed...
call npx --yes playwright install chromium
if errorlevel 1 exit /b 1

echo [bootstrap] verifying installation...
call node -e "require('pptxgenjs');require('playwright');require('sharp');console.log('[bootstrap] all deps require() OK');"
if errorlevel 1 exit /b 1

if not exist "%STAMP_DIR%" mkdir "%STAMP_DIR%"
<nul set /p=%FINGERPRINT%>"%STAMP_FILE%"
echo [bootstrap] done
exit /b 0
