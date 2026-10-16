param(
    [ValidateSet('patch', 'minor', 'major', 'prepatch', 'preminor', 'premajor', 'prerelease')]
    [string]$Bump = 'patch',

    [string]$Version,

    [ValidateSet('public', 'restricted')]
    [string]$Access,

    [switch]$CheckOnly,
    [switch]$NoGitPush,
    [switch]$NoNpmPublish,
    [switch]$SkipPack
)

$ErrorActionPreference = 'Stop'

function Step($message) {
    Write-Host "`n==> $message" -ForegroundColor Cyan
}

function Fail($message) {
    Write-Error $message
    exit 1
}

function Run($command) {
    Write-Host "-> $command" -ForegroundColor DarkGray
    Invoke-Expression $command
}

function RunAndCapture($filePath, $argumentList) {
    $outputFile = [System.IO.Path]::GetTempFileName()
    $errorFile = [System.IO.Path]::GetTempFileName()

    try {
        & $filePath @argumentList 1> $outputFile 2> $errorFile
        $exitCode = $LASTEXITCODE

        $stdout = ''
        $stderr = ''

        if (Test-Path $outputFile) {
            $stdoutContent = Get-Content $outputFile -Raw
            if ($null -ne $stdoutContent) {
                $stdout = "$stdoutContent".Trim()
            }
        }

        if (Test-Path $errorFile) {
            $stderrContent = Get-Content $errorFile -Raw
            if ($null -ne $stderrContent) {
                $stderr = "$stderrContent".Trim()
            }
        }

        return [pscustomobject]@{
            ExitCode = $exitCode
            StdOut = $stdout
            StdErr = $stderr
        }
    } finally {
        if (Test-Path $outputFile) { Remove-Item -LiteralPath $outputFile -Force }
        if (Test-Path $errorFile) { Remove-Item -LiteralPath $errorFile -Force }
    }
}

if ($Version -and $PSBoundParameters.ContainsKey('Bump')) {
    Fail 'Use either -Bump or -Version, not both.'
}

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Step 'Checking required tools'
foreach ($tool in @('git', 'npm')) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        Fail "Missing required tool: $tool"
    }
}

Step 'Checking git working tree'
$status = git status --porcelain
if ($LASTEXITCODE -ne 0) {
    Fail 'Failed to read git status. Make sure git is available and this repo is trusted on this machine.'
}
if ($status) {
    Fail 'Working tree is not clean. Commit or stash changes before releasing.'
}

Step 'Checking npm login'
$whoami = RunAndCapture 'npm' @('whoami')
if ($whoami.ExitCode -ne 0 -or -not $whoami.StdOut) {
    if ($whoami.StdErr) {
        Write-Host $whoami.StdErr -ForegroundColor DarkYellow
    }
    Fail 'npm login is required before publishing. Run `npm login` first, then rerun this script.'
}
Write-Host "Logged in as: $($whoami.StdOut)"

Step 'Checking published version'
$package = Get-Content 'package.json' | ConvertFrom-Json
$packageName = $package.name
$currentVersion = $package.version
$publishedVersion = ''

try {
    $publishedVersion = (npm view $packageName version 2>$null).Trim()
} catch {
    $publishedVersion = ''
}

if ($publishedVersion) {
    Write-Host "Latest npm version: $publishedVersion"
} else {
    Write-Host 'Package not found on npm yet, or version lookup failed.'
}
Write-Host "Local version: $currentVersion"

if ($CheckOnly) {
    Step 'Preflight complete'
    Write-Host 'Checks passed. No version bump or publish was performed.'
    exit 0
}

Step 'Bumping version'
if ($Version) {
    Run "npm version $Version"
} else {
    Run "npm version $Bump"
}

$newPackage = Get-Content 'package.json' | ConvertFrom-Json
$newVersion = $newPackage.version
Write-Host "New version: $newVersion"

if (-not $SkipPack) {
    Step 'Previewing publish payload'
    Run 'npm pack --dry-run'
}

if (-not $NoNpmPublish) {
    Step 'Publishing to npm'
    if ($Access) {
        Run "npm publish --access $Access"
    } else {
        Run 'npm publish'
    }
}

if (-not $NoGitPush) {
    Step 'Pushing git commit and tag'
    Run 'git push'
    Run 'git push --tags'
}

Step 'Release complete'
Write-Host "Published $packageName@$newVersion"
