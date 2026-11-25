param([ValidateSet('apk', 'web', 'all', 'check')][string]$Target = 'all')
. (Join-Path $PSScriptRoot 'flutter-env.ps1')
$mobileDirectory = Join-Path $projectRoot 'mobile'
Push-Location $mobileDirectory
try {
    if ($Target -eq 'check') {
        & $flutter analyze
        if ($LASTEXITCODE -ne 0) { throw 'Flutter analyze failed.' }
        & $flutter test
        if ($LASTEXITCODE -ne 0) { throw 'Flutter tests failed.' }
    }
    if ($Target -in @('apk', 'all')) {
        & $flutter build apk --debug
        if ($LASTEXITCODE -ne 0) { throw 'APK build failed.' }
        $releaseDirectory = Join-Path $projectRoot 'releases'
        New-Item -ItemType Directory -Force -Path $releaseDirectory | Out-Null
        Copy-Item -LiteralPath (Join-Path $mobileDirectory 'build/app/outputs/flutter-apk/app-debug.apk') -Destination (Join-Path $releaseDirectory 'tushum-ai-test.apk') -Force
    }
    if ($Target -in @('web', 'all')) {
        & $flutter build web --release --no-web-resources-cdn
        if ($LASTEXITCODE -ne 0) { throw 'Web build failed.' }
    }
} finally {
    Pop-Location
}
