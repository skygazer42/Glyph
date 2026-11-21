param([string]$PlanPath = 'F:\Glyph\resources\archive\pre_changzhou_20261121\retirement_plan.json')
$ErrorActionPreference = 'Stop'
$workspace = [IO.Path]::GetFullPath('F:\Glyph')
$archiveRoot = [IO.Path]::GetFullPath('F:\Glyph\resources\archive\pre_changzhou_20261121\files')
$plan = Get-Content -LiteralPath $PlanPath -Raw | ConvertFrom-Json
# Validate every exact source and destination before moving any file or directory.
foreach ($item in $plan.file_moves) {
    $source = [IO.Path]::GetFullPath($item.source)
    $target = [IO.Path]::GetFullPath($item.target)
    if (-not $source.StartsWith($workspace + '\') -or -not $target.StartsWith($archiveRoot + '\')) {
        throw 'Migration path escaped the verified workspace or archive.'
    }
    if ((Test-Path -LiteralPath $source) -and (Test-Path -LiteralPath $target)) {
        throw "Both source and archive exist: $source"
    }
    if (-not (Test-Path -LiteralPath $source) -and -not (Test-Path -LiteralPath $target)) {
        throw "Missing source and archive: $source"
    }
}
foreach ($item in $plan.file_moves) {
    if (Test-Path -LiteralPath $item.source) {
        $null = New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($item.target)) -Force
        Move-Item -LiteralPath $item.source -Destination $item.target
    }
    foreach ($file in $item.sha256.PSObject.Properties) {
        $archived = Join-Path $archiveRoot ($file.Name.Replace('/', '\'))
        if ((Get-FileHash -LiteralPath $archived -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.Value) {
            throw "Archive hash mismatch: $archived"
        }
    }
}
Write-Output "Archived and hash-verified $($plan.file_moves.Count) exact paths."
