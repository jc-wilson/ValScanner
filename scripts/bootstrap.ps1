param([switch]$SetupOnly, [switch]$NoReveal)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'
$env:PSModulePath = Join-Path $PSHOME 'Modules'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$toolsRoot = Join-Path $projectRoot '.build-tools'
$logRoot = Join-Path $projectRoot 'build'
New-Item -ItemType Directory -Path $toolsRoot, $logRoot -Force | Out-Null
$logPath = Join-Path $logRoot 'setup.log'
'Build setup started.' | Set-Content -LiteralPath $logPath -Encoding UTF8

function Get-PackageHash([string]$Path) {
    $algorithm = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($Path)
    try { return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-', '') }
    finally { $stream.Dispose(); $algorithm.Dispose() }
}

function Invoke-Checked([string]$Program, [string[]]$CommandArguments) {
    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & $Program @CommandArguments >> $logPath 2>&1
    $commandResult = $LASTEXITCODE
    $ErrorActionPreference = $oldPreference
    if ($commandResult -ne 0) { throw "A build step failed (exit $commandResult). See $logPath" }
}

try {
    if (-not [Environment]::Is64BitOperatingSystem) { throw 'This build needs 64-bit Windows 10 or 11.' }
    foreach ($file in @('build.py', 'requirements-build.txt', 'qt_runtime_hook.py', 'frontend\QApplication.py')) {
        if (-not (Test-Path -LiteralPath (Join-Path $projectRoot $file))) {
            throw 'Extract the entire downloaded ZIP first, then run build_exe.bat from the extracted folder.'
        }
    }

    $pythonVersion = '3.13.15'
    $archiveHash = '05357887DF50D3153EFC681BDF432C321D3E2F9CE5788F99F4515B27E8FDA0AC'
    $runtimeRoot = Join-Path $toolsRoot "python-$pythonVersion"
    $runtimePython = Join-Path $runtimeRoot 'tools\python.exe'
    if (-not (Test-Path -LiteralPath $runtimePython)) {
        Write-Host '[1/4] Setting up private Python. No manual installation is needed.'
        $archivePath = Join-Path $toolsRoot "python-$pythonVersion.zip"
        if ((Test-Path -LiteralPath $archivePath) -and
            ((Get-PackageHash $archivePath) -ne $archiveHash)) {
            Remove-Item -LiteralPath $archivePath
        }
        if (-not (Test-Path -LiteralPath $archivePath)) {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            $downloadUrl = "https://api.nuget.org/v3-flatcontainer/python/$pythonVersion/python.$pythonVersion.nupkg"
            for ($attempt = 1; $attempt -le 3; $attempt++) {
                try {
                    Invoke-WebRequest -UseBasicParsing -Uri $downloadUrl -OutFile $archivePath -TimeoutSec 120
                    break
                } catch {
                    if ($attempt -eq 3) { throw 'Python could not be downloaded. Check your internet connection and run the build again.' }
                    Start-Sleep -Seconds 2
                }
            }
        }
        if ((Get-PackageHash $archivePath) -ne $archiveHash) {
            Remove-Item -LiteralPath $archivePath
            throw 'The Python download was incomplete or did not match the expected package. Run the build again.'
        }
        # A new staging directory lets an interrupted extraction recover on retry.
        $extractRoot = Join-Path $toolsRoot ('python-extract-' + [guid]::NewGuid().ToString('N'))
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [IO.Compression.ZipFile]::ExtractToDirectory($archivePath, $extractRoot)
        if (Test-Path -LiteralPath $runtimeRoot) {
            $retainedRoot = Join-Path $toolsRoot ('python-incomplete-' + [guid]::NewGuid().ToString('N'))
            $resolvedRuntime = [IO.Path]::GetFullPath($runtimeRoot)
            $resolvedRetained = [IO.Path]::GetFullPath($retainedRoot)
            $allowedPrefix = [IO.Path]::GetFullPath($toolsRoot) + [IO.Path]::DirectorySeparatorChar
            if (-not ($resolvedRuntime.StartsWith($allowedPrefix) -and $resolvedRetained.StartsWith($allowedPrefix))) {
                throw 'Unexpected Python directory.'
            }
            Move-Item -LiteralPath $runtimeRoot -Destination $retainedRoot
        }
        Move-Item -LiteralPath $extractRoot -Destination $runtimeRoot
    } else {
        Write-Host '[1/4] Private Python is ready.'
    }

    $env:PYTHONHOME = $null
    $env:PYTHONPATH = $null
    $env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
    $env:PYTHONUTF8 = '1'
    $env:TEMP = Join-Path $toolsRoot 'tmp'
    $env:TMP = $env:TEMP
    New-Item -ItemType Directory -Path $env:TEMP -Force | Out-Null
    $environmentRoot = Join-Path $toolsRoot 'environment'
    $buildPython = Join-Path $environmentRoot 'Scripts\python.exe'
    $env:PATH = (Join-Path $runtimeRoot 'tools') + ';' + (Join-Path $environmentRoot 'Scripts') + ";$env:SystemRoot\System32;$env:SystemRoot;$env:SystemRoot\System32\Wbem"
    Invoke-Checked $runtimePython @('-I', '-c', 'import sys; assert sys.version_info[:3] == (3,13,15) and sys.maxsize > 2**32')
    Write-Host '[2/4] Preparing the build environment...'
    Invoke-Checked $runtimePython @('-I', '-m', 'venv', '--upgrade', $environmentRoot)
    Write-Host '[3/4] Installing dependencies. The first run may take several minutes...'
    Invoke-Checked $buildPython @('-I', '-m', 'pip', 'install', '--quiet', '--only-binary=:all:', '-r', (Join-Path $projectRoot 'requirements-build.txt'))
    if ($SetupOnly) { Write-Host 'Automatic setup passed.'; exit 0 }

    Write-Host '[4/4] Downloading assets and building your app. Please keep this window open...'
    Invoke-Checked $buildPython @('-I', (Join-Path $projectRoot 'build.py'))
    $receipt = Get-Content -LiteralPath (Join-Path $logRoot 'last-build.json') -Raw | ConvertFrom-Json
    $executable = [IO.Path]::GetFullPath([string]$receipt.executable)
    $distPrefix = [IO.Path]::GetFullPath((Join-Path $projectRoot 'dist')) + [IO.Path]::DirectorySeparatorChar
    if (-not ($executable.StartsWith($distPrefix) -and (Test-Path -LiteralPath $executable))) {
        throw 'The build did not produce the expected executable.'
    }
    Write-Host ''
    Write-Host "Ready! Open this app: $executable" -ForegroundColor Green
    if (-not $NoReveal) {
        Start-Process -FilePath explorer.exe -ArgumentList ('/select,"{0}"' -f $executable)
    }
    exit 0
} catch {
    $_ | Out-String | Add-Content -LiteralPath $logPath -Encoding UTF8
    Write-Host ''
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host "Details are saved in: $logPath"
    exit 1
}
