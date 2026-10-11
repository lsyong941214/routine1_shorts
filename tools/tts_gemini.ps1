# Google Gemini TTS (generativelanguage API). Python 런타임은 인터넷이 막혀 있어 PowerShell에서 호출한다.
# usage: powershell -File tools/tts_gemini.ps1 -Jobs output/YYYY-MM-DD/NN/tts/jobs.json
# jobs.json: {"model": "...", "voice": "Kore", "items": [{"prompt": "스타일 지시 + 본문", "out": "절대경로.wav"}]}
# 키: config/secrets.local.json 의 GEMINI_API_KEY (또는 환경변수 GEMINI_API_KEY). 키 값은 channels.yaml에 쓰지 않는다.
param([Parameter(Mandatory = $true)][string]$Jobs)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$key = $env:GEMINI_API_KEY
if (-not $key) {
    $sec = Join-Path $root 'config\secrets.local.json'
    $key = ([IO.File]::ReadAllText($sec, [Text.Encoding]::UTF8) | ConvertFrom-Json).GEMINI_API_KEY
}
$job = [IO.File]::ReadAllText((Resolve-Path $Jobs), [Text.Encoding]::UTF8) | ConvertFrom-Json
$url = "https://generativelanguage.googleapis.com/v1beta/models/$($job.model):generateContent"

function Write-Wav([byte[]]$pcm, [string]$path, [int]$rate) {
    $fs = [IO.File]::Create($path); $bw = New-Object IO.BinaryWriter($fs)
    $bw.Write([Text.Encoding]::ASCII.GetBytes('RIFF')); $bw.Write([int](36 + $pcm.Length)); $bw.Write([Text.Encoding]::ASCII.GetBytes('WAVEfmt '))
    $bw.Write([int]16); $bw.Write([int16]1); $bw.Write([int16]1); $bw.Write([int]$rate); $bw.Write([int]($rate * 2)); $bw.Write([int16]2); $bw.Write([int16]16)
    $bw.Write([Text.Encoding]::ASCII.GetBytes('data')); $bw.Write([int]$pcm.Length); $bw.Write($pcm); $bw.Close()
}

# 하루 요청 기록: state/tts_usage.json {"YYYY-MM-DD": {"<model>": {"requests": n, "ok": n, "exhausted": bool}}}
# 한도 초과(429)면 재시도하지 않고 exit 3. Windows TTS 예비는 쓰지 않는다(2026-10-09 운영자 결정).
$usagePath = Join-Path $root 'state\tts_usage.json'
# Gemini 무료 한도는 미국 태평양 시간 자정(한국 16:00~17:00)에 초기화된다 -> 기록 날짜도 태평양 시간 기준
$today = [TimeZoneInfo]::ConvertTimeBySystemTimeZoneId((Get-Date), 'Pacific Standard Time').ToString('yyyy-MM-dd')
function Get-Usage {
    $u = @{}
    if (Test-Path $usagePath) {
        $o = [IO.File]::ReadAllText($usagePath, [Text.Encoding]::UTF8) | ConvertFrom-Json
        foreach ($d in $o.PSObject.Properties) { $u[$d.Name] = @{}; foreach ($m in $d.Value.PSObject.Properties) { $u[$d.Name][$m.Name] = @{ requests = [int]$m.Value.requests; ok = [int]$m.Value.ok; exhausted = [bool]$m.Value.exhausted } } }
    }
    if (-not $u.ContainsKey($today)) { $u[$today] = @{} }
    if (-not $u[$today].ContainsKey($job.model)) { $u[$today][$job.model] = @{ requests = 0; ok = 0; exhausted = $false } }
    return $u
}
function Save-Usage($u) {
    New-Item -ItemType Directory -Force (Split-Path $usagePath) | Out-Null
    [IO.File]::WriteAllText($usagePath, ($u | ConvertTo-Json -Depth 5), (New-Object Text.UTF8Encoding $false))
}
$limit = 10; if ($job.daily_limit) { $limit = [int]$job.daily_limit }

foreach ($it in $job.items) {
    if ((Test-Path $it.out) -and ((Get-Item $it.out).Length -gt 1000)) { Write-Output "skip $($it.out)"; continue }
    $usage = Get-Usage; $mu = $usage[$today][$job.model]
    if ($mu.exhausted -or $mu.requests -ge $limit) { Write-Output "quota $($job.model) $($mu.requests)/$limit"; exit 3 }
    $body = @{ contents = @(@{ parts = @(@{ text = $it.prompt }) }); generationConfig = @{ responseModalities = @('AUDIO');
            speechConfig = @{ voiceConfig = @{ prebuiltVoiceConfig = @{ voiceName = $job.voice } } } } } | ConvertTo-Json -Depth 10
    $ok = $false
    for ($try = 1; $try -le 2 -and -not $ok; $try++) {
        $usage = Get-Usage; $mu = $usage[$today][$job.model]
        if ($mu.requests -ge $limit) { Save-Usage $usage; Write-Output "quota $($job.model) $($mu.requests)/$limit"; exit 3 }
        $mu.requests++; Save-Usage $usage
        try {
            $r = Invoke-RestMethod -Uri $url -Method Post -Headers @{ 'x-goog-api-key' = $key } -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($body))
            $part = $r.candidates[0].content.parts | Where-Object { $_.inlineData } | Select-Object -First 1
            $rate = 24000; if ($part.inlineData.mimeType -match 'rate=(\d+)') { $rate = [int]$Matches[1] }
            Write-Wav ([Convert]::FromBase64String($part.inlineData.data)) $it.out $rate
            $usage = Get-Usage; $usage[$today][$job.model].ok++; Save-Usage $usage
            Write-Output "ok $($it.out) ($($mu.requests)/$limit)"; $ok = $true
        } catch {
            $code = 0; try { $code = [int]$_.Exception.Response.StatusCode } catch {}
            if ($code -eq 429 -or $_.Exception.Message -match 'RESOURCE_EXHAUSTED|quota') {
                $usage = Get-Usage; $usage[$today][$job.model].exhausted = $true; Save-Usage $usage
                Write-Output "quota $($job.model) (429)"; exit 3
            }
            Write-Output "retry $try : $($_.Exception.Message)"; Start-Sleep -Seconds 15
        }
    }
    if (-not $ok) { Write-Error "TTS failed: $($it.out)"; exit 1 }
}
