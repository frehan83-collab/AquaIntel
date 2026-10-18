# Push from a sandboxed session (Windows, no keyring access)
#
# `git push` fails in this environment with two separate errors:
#   * `schannel: AcquireCredentialsHandle failed: SEC_E_NO_CREDENTIALS` — the schannel TLS
#     backend cannot read the Windows credential store from the sandbox;
#   * `sh.exe: couldn't create signal pipe, Win32 error 5` — a shell-based credential helper
#     cannot start.
#
# This script works around both without ever writing the token to disk or printing it:
#   * TLS on OpenSSL instead of schannel;
#   * credentials in a one-shot `Authorization: Basic` header (x-access-token:<gh token>),
#     with the credential helper disabled so nothing tries to prompt.
#
# Usage:
#   pwsh ./scripts/push_with_gh.ps1                  # pushes the current branch to origin
#   pwsh ./scripts/push_with_gh.ps1 -Remote upstream -Branch master
#
# Requires `gh auth login` (token read via `gh auth token`; scopes: repo).
param(
    [string]$Remote = "origin",
    [string]$Branch = "",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI (gh) is not installed; install it or push with a personal access token."
}

$token = (gh auth token).Trim()
if (-not $token) {
    throw "gh has no token; run 'gh auth login' first."
}

if (-not $Branch) {
    $Branch = (git rev-parse --abbrev-ref HEAD).Trim()
}

# GitHub accepts Basic auth as username + token. Keep the value in memory only.
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("x-access-token:$token"))

$gitArgs = @(
    "-c", "http.sslBackend=openssl",
    "-c", "credential.helper=",
    "-c", "http.extraHeader=Authorization: Basic $encoded"
)

if ($DryRun) {
    Write-Host "would run: git $($gitArgs -join ' ' | ForEach-Object { $_ -replace [regex]::Escape($encoded), '***' }) push $Remote $Branch"
    exit 0
}

$output = & git @gitArgs push $Remote $Branch 2>&1
$code = $LASTEXITCODE

# Scrub the encoded token from anything git prints, then show it.
$output | ForEach-Object {
    ($_ -replace [regex]::Escape($encoded), "***") -replace [regex]::Escape($token), "***"
}

if ($code -ne 0) {
    throw "push failed (exit $code). Check that the token has 'repo' scope and the branch exists."
}

$head = (git rev-parse HEAD).Trim()
$remoteHead = (& git @gitArgs ls-remote $Remote "refs/heads/$Branch" 2>&1 | Select-Object -First 1)
Write-Host "pushed $Branch at $head"
if ($remoteHead -and ($remoteHead -notmatch [regex]::Escape($head))) {
    Write-Warning "remote head does not match local HEAD; fetch and inspect before continuing."
}
