# Multi Screen install (Windows). Chalane ke liye: "Install Multi Screen (Windows).bat" pe double-click
$ErrorActionPreference = 'Continue'
$src = Split-Path -Parent $MyInvocation.MyCommand.Path
$dest = Join-Path $env:LOCALAPPDATA 'MultiScreen'
Write-Host ""
Write-Host "=== Multi Screen install ===" -ForegroundColor Cyan

function Find-Python {
  $paths = @("$env:LOCALAPPDATA\Programs\Python\Python313\python.exe", "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
             "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe", "C:\Program Files\Python313\python.exe",
             "C:\Program Files\Python312\python.exe", "C:\Program Files\Python311\python.exe")
  foreach ($p in $paths) { if (Test-Path $p) { return $p } }
  $c = Get-Command python -ErrorAction SilentlyContinue | Where-Object { $_.Source -notlike '*WindowsApps*' } | Select-Object -First 1
  if ($c) { return $c.Source }
  return $null
}

$py = Find-Python
if (-not $py) {
  Write-Host "[1/3] Python install ho raha hai (2-3 min)..." -ForegroundColor Yellow
  winget install -e --id Python.Python.3.12 --scope user --silent --accept-source-agreements --accept-package-agreements
  $py = Find-Python
}
if (-not $py) { Write-Host "Python install nahi hua. python.org se install karke dobara chalao." -ForegroundColor Red; exit 1 }
$pyw = Join-Path (Split-Path $py) 'pythonw.exe'
Write-Host "[1/3] Python: $py" -ForegroundColor Green

New-Item -ItemType Directory -Force -Path $dest | Out-Null
foreach ($f in 'multiscreen.py', 'hotkey.pyw', 'icon.png', 'multiscreen.ico') { Copy-Item (Join-Path $src $f) (Join-Path $dest $f) -Force }
Write-Host "[2/3] App copy ho gaya: $dest" -ForegroundColor Green

$ws = New-Object -ComObject WScript.Shell
foreach ($folder in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {
  $s = $ws.CreateShortcut((Join-Path $folder 'Multi Screen.lnk'))
  $s.TargetPath = $pyw
  $s.Arguments = "`"$dest\multiscreen.py`""
  $s.WorkingDirectory = $dest
  $s.IconLocation = "$dest\multiscreen.ico"
  $s.Description = 'Kai asli Chrome windows ek grid me (Ctrl+Alt+M)'
  $s.Save()
}
# Ctrl+Alt+M: chhota listener, har login pe chupchaap chalta hai
$hk = $ws.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Startup')) 'Multi Screen Hotkey.lnk'))
$hk.TargetPath = $pyw
$hk.Arguments = "`"$dest\hotkey.pyw`""
$hk.WorkingDirectory = $dest
$hk.Description = 'Ctrl+Alt+M = Multi Screen'
$hk.Save()
Start-Process -FilePath $pyw -ArgumentList "`"$dest\hotkey.pyw`"" -WorkingDirectory $dest
Write-Host "[3/3] Desktop aur Start menu me 'Multi Screen' icon lag gaya. Shortcut: Ctrl+Alt+M" -ForegroundColor Green
Start-Process -FilePath $pyw -ArgumentList "`"$dest\multiscreen.py`"" -WorkingDirectory $dest
Write-Host ""
Write-Host "Ho gaya! 'Multi Screen' khul gaya hai. Number dabao, utni Chrome windows grid me lag jayengi." -ForegroundColor Cyan
