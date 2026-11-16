# Reverse:1999 Summon Link Grabber - PowerShell launcher
#
# Usage (paste into PowerShell):
#   Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://raw.githubusercontent.com/lonelytragedy/r1999-SummonHistoryLinkGrabber/main/getlink.ps1'))
#
# Downloads the latest R1999LinkGrabber.exe from GitHub Releases into %TEMP%
# (cached per release) and runs it in the current console window.
# The whole script is wrapped in a script block so it never closes the
# caller's PowerShell window, even when run through iex.

& {
    $ErrorActionPreference = 'Stop'

    $Repo      = 'lonelytragedy/r1999-SummonHistoryLinkGrabber'
    $AssetName = 'R1999LinkGrabber.exe'
    $ProxyAddr = '127.0.0.1:8080'
    $CacheDir  = Join-Path $env:TEMP 'R1999LinkGrabber'
    $InetKey   = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings'

    [System.Net.ServicePointManager]::SecurityProtocol =
        [System.Net.ServicePointManager]::SecurityProtocol -bor 3072  # TLS 1.2

    function New-WebClient {
        $wc = New-Object System.Net.WebClient
        $wc.Headers['User-Agent'] = 'R1999LinkGrabber-ps1'
        $wc
    }

    function Get-LatestAsset {
        # Returns @{ Tag; Url; Size } or $null if the API is unreachable.
        try {
            $json = (New-WebClient).DownloadString("https://api.github.com/repos/$Repo/releases/latest")
            $rel = $json | ConvertFrom-Json
            $asset = $rel.assets | Where-Object { $_.name -eq $AssetName } | Select-Object -First 1
            if ($asset) {
                return @{ Tag = $rel.tag_name; Url = $asset.browser_download_url; Size = [long]$asset.size }
            }
        } catch { }
        return $null
    }

    function Reset-LeftoverProxy {
        # Safety net: if the grabber was killed and left our proxy enabled, turn it off.
        try {
            $s = Get-ItemProperty -Path $InetKey -ErrorAction Stop
            if ($s.ProxyEnable -eq 1 -and $s.ProxyServer -eq $ProxyAddr) {
                Set-ItemProperty -Path $InetKey -Name ProxyEnable -Value 0
                Write-Host "Leftover proxy $ProxyAddr disabled." -ForegroundColor Yellow
            }
        } catch { }
    }

    Write-Host 'Reverse:1999 Summon Link Grabber' -ForegroundColor Cyan

    if (-not (Test-Path $CacheDir)) { New-Item -ItemType Directory -Path $CacheDir | Out-Null }

    $info = Get-LatestAsset
    if ($info) {
        $safeTag = ($info.Tag -replace '[^\w\.\-]', '_')
        $exe = Join-Path $CacheDir "R1999LinkGrabber-$safeTag.exe"
        $url = $info.Url
        $expectedSize = $info.Size
    } else {
        $exe = Join-Path $CacheDir $AssetName
        $url = "https://github.com/$Repo/releases/latest/download/$AssetName"
        $expectedSize = 0
    }

    $cached = (Test-Path $exe) -and (
        $expectedSize -eq 0 -or (Get-Item $exe).Length -eq $expectedSize)

    if ($cached) {
        Write-Host "Using cached $exe"
    } else {
        if ($info) { Write-Host "Downloading $AssetName ($($info.Tag))..." }
        else       { Write-Host "Downloading $AssetName..." }
        $tmp = "$exe.download"
        try {
            (New-WebClient).DownloadFile($url, $tmp)
        } catch {
            Write-Host "Download failed: $($_.Exception.Message)" -ForegroundColor Red
            if (Test-Path $tmp) { Remove-Item $tmp -Force }
            return
        }
        if ($expectedSize -gt 0 -and (Get-Item $tmp).Length -ne $expectedSize) {
            Write-Host 'Downloaded file has an unexpected size, aborting.' -ForegroundColor Red
            Remove-Item $tmp -Force
            return
        }
        Move-Item -Path $tmp -Destination $exe -Force
        # Remove old cached versions.
        Get-ChildItem $CacheDir -Filter 'R1999LinkGrabber*.exe' |
            Where-Object { $_.FullName -ne $exe } |
            Remove-Item -Force -ErrorAction SilentlyContinue
    }

    try { Unblock-File -Path $exe } catch { }

    Write-Host ''
    try {
        & $exe
    } finally {
        Reset-LeftoverProxy
    }
}
