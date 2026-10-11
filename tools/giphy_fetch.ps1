# GIPHY GIF 다운로드. Python 런타임은 인터넷이 막혀 있어 PowerShell에서 받는다.
# usage: powershell -File tools/giphy_fetch.ps1 -Url "https://giphy.com/gifs/slug-ID" -Out assets/gifs/YYYY-MM-DD/NN/g1.gif [-User "@uploader"] [-Keyword "검색어"]
# -Url: GIPHY 페이지 URL 또는 media.giphy.com / i.giphy.com 주소. 같은 이름의 .json(출처 기록)을 함께 저장한다.
param(
    [Parameter(Mandatory = $true)][string]$Url,
    [Parameter(Mandatory = $true)][string]$Out,
    [string]$User = '',
    [string]$Keyword = ''
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

if ($Url -match 'giphy\.com/media/(?:v1\.[^/]+/)?([A-Za-z0-9]+)/') { $id = $Matches[1] }
elseif ($Url -match 'i\.giphy\.com/(?:media/)?([A-Za-z0-9]+)(?:\.gif|/)') { $id = $Matches[1] }
elseif ($Url -match 'giphy\.com/(?:gifs|stickers)/(?:[^/?#]*-)?([A-Za-z0-9]+)(?:[/?#]|$)') { $id = $Matches[1] }
else { Write-Error "GIPHY ID를 찾지 못함: $Url"; exit 1 }

$path = if ([IO.Path]::IsPathRooted($Out)) { $Out } else { Join-Path $root $Out }
New-Item -ItemType Directory -Force (Split-Path -Parent $path) | Out-Null
$src = "https://i.giphy.com/$id.gif"
$ok = $false
for ($try = 1; $try -le 3 -and -not $ok; $try++) {
    try {
        Invoke-WebRequest -Uri $src -OutFile $path -UseBasicParsing
        $head = [Text.Encoding]::ASCII.GetString([IO.File]::ReadAllBytes($path), 0, 6)
        if ($head -notlike 'GIF8*') { throw "GIF 형식 아님 ($head)" }
        $ok = $true
    } catch {
        Write-Output "retry $try : $($_.Exception.Message)"; Start-Sleep -Seconds (3 * $try)
    }
}
if (-not $ok) { Write-Error "GIF 다운로드 실패: $src"; exit 1 }

$meta = [ordered]@{ id = $id; page_url = $Url; media_url = $src; user = $User; keyword = $Keyword
    downloaded = (Get-Date -Format 'yyyy-MM-ddTHH:mm:ss'); bytes = (Get-Item $path).Length }
[IO.File]::WriteAllText([IO.Path]::ChangeExtension($path, '.json'), ($meta | ConvertTo-Json), (New-Object Text.UTF8Encoding $false))
Write-Output "ok $path ($($meta.bytes) bytes)"
