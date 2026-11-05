# GMS Clinical AI — first-time installer for Windows (Docker Desktop, Windows 10/11 Pro or Windows Server).
#
#   Right-click PowerShell → Run as administrator, then:
#       .\install.ps1 -Org "Life Care Medico" -AdminEmail dr@lifecare.in -Site clinic.local -DiskEncrypted
#
# STATUS: written to mirror install.sh step for step, but NOT yet run on a real Windows machine. Run it on a test PC
# first. Updates and rollback use the bash scripts through WSL2:  wsl ./update.sh <bundle>   (Docker Desktop's WSL2 backend).
param(
  [string]$Org = "My Clinic", [string]$AdminName = "Clinic Administrator", [string]$AdminEmail = "admin@example.com",
  [string]$Site = "localhost", [string]$TimeZone = "Asia/Kolkata", [string]$AiUrl = "http://host.docker.internal:11434",
  [string]$DataPath = ".\data", [switch]$DiskEncrypted, [int]$MinDiskGb = 15
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$fail = 0; $warn = 0
function Ok($m)   { Write-Host "  OK    $m" -ForegroundColor Green }
function Warn($m) { Write-Host "  WARN  $m" -ForegroundColor Yellow; $script:warn++ }
function Fail($m) { Write-Host "  FAIL  $m" -ForegroundColor Red; $script:fail++ }
function Key($n)  { $b = New-Object byte[] $n; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); [Convert]::ToBase64String($b).Replace('+','-').Replace('/','_') }

Write-Host "GMS Clinical AI — installation check" -ForegroundColor Cyan
if (Get-Command docker -ErrorAction SilentlyContinue) { Ok "Docker found" } else { Fail "Docker Desktop is not installed." }
docker compose version *> $null; if ($LASTEXITCODE -eq 0) { Ok "Docker Compose" } else { Fail "Docker Compose v2 is missing." }
docker info *> $null; if ($LASTEXITCODE -eq 0) { Ok "Docker is running" } else { Fail "Docker is not running. Start Docker Desktop." }
$mem = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
if ($mem -ge 8) { Ok "$mem GB memory" } elseif ($mem -ge 4) { Warn "$mem GB memory (8 GB or more recommended)" } else { Fail "Only $mem GB memory" }
New-Item -ItemType Directory -Force -Path $DataPath | Out-Null
$drive = (Get-Item (Resolve-Path $DataPath)).PSDrive
$free = [math]::Round($drive.Free / 1GB)
if ($free -ge 50) { Ok "$free GB free" } elseif ($free -ge $MinDiskGb) { Warn "$free GB free (50 GB or more recommended)" } else { Fail "Only $free GB free (at least $MinDiskGb GB needed)" }
foreach ($p in 80, 443) { if (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue) { Warn "Port $p is in use" } else { Ok "Port $p is free" } }
if (-not $DiskEncrypted) {
  try { $bl = Get-BitLockerVolume -MountPoint ($drive.Name + ":") -ErrorAction Stop; if ($bl.ProtectionStatus -eq "On") { $DiskEncrypted = $true; Ok "BitLocker is on for this drive" } } catch {}
}
if (-not $DiskEncrypted) { Warn "Could not confirm the disk is encrypted. Turn on BitLocker: patient records are stored on it." }
if (-not ((Test-Path images\gms-clinical-ai.tar) -or (docker image inspect gms-clinical-ai:current 2>$null))) { Fail "images\gms-clinical-ai.tar is missing." }
if ($fail -gt 0) { Write-Host "`n$fail problem(s) must be fixed before installing." -ForegroundColor Red; exit 1 }

$password = ""
if (Test-Path .env) { Write-Host "`nAn existing .env was found and is kept unchanged (keys are never regenerated over existing data)." -ForegroundColor Yellow }
else {
  $words = "amber anchor aspen basil birch breeze cedar clover coral dawn ember fern flint garnet harbor hazel indigo iris jade juniper lotus maple meadow mint moss oak olive opal orchid pearl pine quartz reef river sage slate spruce stone tulip velvet willow".Split(" ")
  $password = (1..4 | ForEach-Object { $w = $words[(Get-Random -Maximum $words.Count)]; $w.Substring(0,1).ToUpper() + $w.Substring(1) }) -join "-"; $password += "-" + (Get-Random -Minimum 1000 -Maximum 9999)
  $t = Get-Content .env.template -Raw
  $map = @{ "@TIMEZONE@"=$TimeZone; "@SITE_ADDRESS@"=$Site; "@DATA_PATH@"=$DataPath; "@APP_SECRET_KEY@"=(Key 48); "@DATA_ENCRYPTION_KEY@"=(Key 32);
            "@BACKUP_ENCRYPTION_KEY@"=(Key 32); "@DISK_ENCRYPTED@"=$(if ($DiskEncrypted) {"true"} else {"false"}); "@ADMIN_EMAIL@"=$AdminEmail;
            "@ADMIN_NAME@"=$AdminName; "@ADMIN_PASSWORD@"=$password; "@AI_URL@"=$AiUrl }
  foreach ($k in $map.Keys) { $t = $t.Replace($k, $map[$k]) }
  [IO.File]::WriteAllText("$PWD\.env", $t, (New-Object Text.UTF8Encoding $false))
  New-Item -ItemType Directory -Force -Path certs, offsite | Out-Null
  Ok "Created .env with new keys"
}
Write-Host "`nLoading the product"
if (Test-Path images\gms-clinical-ai.tar) { docker load -i images\gms-clinical-ai.tar | Select-Object -Last 1 }
Get-ChildItem images\*.tar -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne "gms-clinical-ai.tar" } | ForEach-Object { docker load -i $_.FullName | Out-Null; Ok "Loaded $($_.Name)" }
$version = (Get-Content VERSION -ErrorAction SilentlyContinue); if (-not $version) { $version = "unknown" }
docker image inspect "gms-clinical-ai:$version" *> $null; if ($LASTEXITCODE -eq 0) { docker tag "gms-clinical-ai:$version" gms-clinical-ai:current }
Set-Content .installed-version $version
Write-Host "`nStarting"
docker compose up -d
Write-Host -NoNewline "Waiting for the application to become healthy"
$healthy = $false
foreach ($i in 1..90) { $s = docker compose ps --format "{{.Service}} {{.Health}}" | Where-Object { $_ -like "app *" }; if ($s -like "*healthy*" -and $s -notlike "*unhealthy*") { $healthy = $true; break }; Write-Host -NoNewline "."; Start-Sleep 2 }
Write-Host ""
if (-not $healthy) { Write-Host "The application did not become healthy. Run: docker compose logs app" -ForegroundColor Red; exit 1 }
Ok "Application is healthy"
docker compose exec -T app python -m app.cli doctor
Write-Host "`nInstalled. Open https://$Site" -ForegroundColor Green
if ($password) {
  Write-Host "  Sign in as  $AdminEmail"; Write-Host "  Password    $password   (shown only now; you must choose your own at first sign-in)" -ForegroundColor White
  Write-Host "`nDo these today:`n  1. Copy the three keys in .env to a password manager or a printed sheet in a safe — NOT only on this PC."
  Write-Host "  2. Trust the certificate on each clinic PC: docker compose cp proxy:/data/caddy/pki/authorities/local/root.crt .\clinic-root-ca.crt"
  Write-Host "     then double-click it → Install → Local Machine → Trusted Root Certification Authorities."
}
