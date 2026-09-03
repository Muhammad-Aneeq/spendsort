<#
.SYNOPSIS
    PowerShell mirror of the Makefile — `make` is not installed on this box (BLOCKERS.md B2).

.DESCRIPTION
    Same target names as the Makefile, so the documented commands work on Windows unchanged:
        ./make.ps1 dev      ./make.ps1 test     ./make.ps1 eval
    One-line fix to use the real Makefile instead: winget install ezwinports.make

.EXAMPLE
    ./make.ps1 dev

.EXAMPLE
    # Port 8000 is taken by Docker/WSL on this box (BLOCKERS.md B6):
    ./make.ps1 dev -Port 8123
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('help', 'install', 'dev', 'dev-api', 'dev-web', 'test', 'test-live',
        'eval', 'eval-live', 'seed', 'lint', 'fmt', 'typecheck', 'up', 'down', 'clean')]
    [string]$Target = 'help',

    # API port. Override when 8000 is occupied (BLOCKERS.md B6).
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
Set-Location $Root

# Keeps the Vite dev-server proxy pointed at whichever port the API is on.
$env:VITE_API_PORT = "$Port"

function Test-PortFree {
    param([int]$Number)
    -not (Get-NetTCPConnection -LocalPort $Number -State Listen -ErrorAction SilentlyContinue)
}

function Invoke-Step {
    param([string]$Label, [scriptblock]$Body)
    Write-Host "==> $Label" -ForegroundColor Cyan
    & $Body
    if ($LASTEXITCODE -ne 0 -and $null -ne $LASTEXITCODE) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

switch ($Target) {

    'help' {
        Write-Host "SpendSort targets" -ForegroundColor Green
        @(
            @('install', 'Install backend (uv) and frontend (npm) dependencies'),
            @('dev', 'Run API + SPA together (the demo entrypoint; -Port to override 8000)'),
            @('dev-api', 'Run the FastAPI backend with reload'),
            @('dev-web', 'Run the Vite dev server'),
            @('test', 'Backend + frontend tests (LLM mocked; no spend, no key needed)'),
            @('test-live', 'Tests that hit the real OpenAI API (needs OPENAI_API_KEY)'),
            @('eval', 'Eval suite + auto-precision CI gate, mock mode'),
            @('eval-live', 'Eval suite against the real model (needs OPENAI_API_KEY)'),
            @('seed', 'Regenerate examples/ and evals/cases.jsonl from fixed seeds'),
            @('lint', 'ruff check'),
            @('fmt', 'ruff format (writes)'),
            @('typecheck', 'mypy (backend) + tsc (frontend)'),
            @('up', 'docker compose up'),
            @('down', 'docker compose down'),
            @('clean', 'Remove local DB, caches and build output')
        ) | ForEach-Object { Write-Host ("  {0,-12} {1}" -f $_[0], $_[1]) }
    }

    'install' {
        Invoke-Step 'uv sync' { uv sync }
        Invoke-Step 'npm install' { Push-Location frontend; npm install --no-fund --no-audit; Pop-Location }
    }

    'dev' {
        if (-not (Test-PortFree $Port)) {
            throw "Port $Port is already in use (BLOCKERS.md B6). Try: ./make.ps1 dev -Port 8123"
        }

        # Two processes; the API is backgrounded so the SPA can hold the foreground.
        Write-Host "API  -> http://127.0.0.1:$Port/docs" -ForegroundColor Green
        Write-Host 'SPA  -> http://127.0.0.1:5173' -ForegroundColor Green
        Write-Host 'Ctrl+C stops the SPA; the API is stopped with it.' -ForegroundColor DarkGray

        $api = Start-Process -PassThru -FilePath 'uv' `
            -ArgumentList 'run', 'uvicorn', 'app.main:app', '--app-dir', 'backend', '--reload', '--port', "$Port" `
            -WorkingDirectory $Root
        try {
            Push-Location frontend
            npm run dev
        }
        finally {
            Pop-Location
            if ($api -and -not $api.HasExited) {
                Write-Host 'Stopping API...' -ForegroundColor DarkGray
                Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue
            }
        }
    }

    'dev-api' {
        uv run uvicorn app.main:app --app-dir backend --reload --port $Port
    }

    'dev-web' {
        Push-Location frontend; try { npm run dev } finally { Pop-Location }
    }

    'test' {
        Invoke-Step 'pytest' { uv run pytest -q -m "not live" }
        Invoke-Step 'vitest' { Push-Location frontend; npm test; Pop-Location }
    }

    'test-live' {
        if (-not $env:OPENAI_API_KEY) { throw 'OPENAI_API_KEY is not set (BLOCKERS.md B3).' }
        Invoke-Step 'pytest -m live' { uv run pytest -q -m live }
    }

    'eval' { Invoke-Step 'evals' { uv run pytest evals -q -m "not live" } }

    'eval-live' {
        if (-not $env:OPENAI_API_KEY) { throw 'OPENAI_API_KEY is not set (BLOCKERS.md B3).' }
        Invoke-Step 'evals (live)' { uv run python evals/run_live.py }
    }

    'seed' {
        # `ledgerfab` lives under backend/, which is not on sys.path for a bare `python -m`.
        $env:PYTHONPATH = 'backend'
        Invoke-Step 'ledgerfab export' { uv run python -m ledgerfab.export }
        if (Test-Path 'evals/build_cases.py') {
            Invoke-Step 'build eval cases' { uv run python evals/build_cases.py }
        }
        else {
            Write-Host 'skip: evals/build_cases.py not found' -ForegroundColor DarkGray
        }
    }

    'lint' {
        Invoke-Step 'ruff check' { uv run ruff check backend evals }
        Invoke-Step 'ruff format --check' { uv run ruff format --check backend evals }
    }

    'fmt' {
        Invoke-Step 'ruff format' { uv run ruff format backend evals }
        Invoke-Step 'ruff check --fix' { uv run ruff check --fix backend evals }
    }

    'typecheck' {
        Invoke-Step 'mypy' { uv run mypy backend/app backend/ledgerfab }
        Invoke-Step 'tsc' { Push-Location frontend; npm run typecheck; Pop-Location }
    }

    'up' { docker compose up --build }
    'down' { docker compose down -v }

    'clean' {
        @('backend/spendsort.db', 'backend/spendsort.db-wal', 'backend/spendsort.db-shm',
            '.pytest_cache', '.ruff_cache', '.mypy_cache', 'frontend/dist') |
            ForEach-Object {
                if (Test-Path $_) { Remove-Item -Recurse -Force $_; Write-Host "removed $_" -ForegroundColor DarkGray }
            }
    }
}
