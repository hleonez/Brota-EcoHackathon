<#
.SYNOPSIS
  Brota con un solo comando: base de datos, API, bot de WhatsApp, túnel y panel de coordinación.

.DESCRIPTION
  .\brota.ps1            Levanta todo (o lo actualiza) y espera a que Brisa quede conectada a Meta.
  .\brota.ps1 estado     Muestra los contenedores y la URL pública del bot.
  .\brota.ps1 logs bot   Sigue los registros de un servicio (db, api, bot, tunel, panel).
  .\brota.ps1 bajar      Detiene todo (los datos de la base se conservan).

  El túnel publica el webhook del bot y el bot lo registra solo en Meta: no hay que pegar URLs.
  Requisitos: Docker Desktop abierto, infra/env/dev.env, api/.env y bot/.env.
#>
param(
    [ValidateSet("levantar", "estado", "logs", "bajar")]
    [string]$Accion = "levantar",
    [string]$Servicio = ""
)
$ErrorActionPreference = "Stop"
$raiz = $PSScriptRoot
$envFile = Join-Path $raiz "infra\env\dev.env"

function Get-Valor([string]$nombre, [string]$porDefecto) {
    $linea = Get-Content $envFile -ErrorAction SilentlyContinue | Where-Object { $_ -match "^\s*$nombre\s*=" } | Select-Object -Last 1
    if ($linea) { return ($linea -split "=", 2)[1].Trim() }
    return $porDefecto
}

function Invoke-Compose([string[]]$extra) {
    $capas = "compose.yaml", "compose.dev.yaml", "compose.api.yaml", "compose.bot.yaml", "compose.tunel.yaml", "compose.panel.yaml"
    $args_ = @("compose", "--env-file", $envFile)
    foreach ($c in $capas) { $args_ += @("-f", (Join-Path $raiz "infra\$c")) }
    # Docker escribe su progreso en stderr: en PowerShell 5.1 eso no debe contar como error.
    $ErrorActionPreference = "Continue"
    & docker @args_ @extra
    if ($LASTEXITCODE -ne 0) { throw "docker compose terminó con error ($LASTEXITCODE)." }
}

function Test-Requisitos {
    & docker info *> $null
    if ($LASTEXITCODE -ne 0) { throw "Docker no responde. Abre Docker Desktop y vuelve a intentar." }
    foreach ($f in "infra\env\dev.env", "api\.env", "bot\.env") {
        if (-not (Test-Path (Join-Path $raiz $f))) { throw "Falta $f (copia su .example y complétalo)." }
    }
    $puerto = [int](Get-Valor "BOT_LOCAL_PORT" "8090")
    $ocupado = Get-NetTCPConnection -LocalPort $puerto -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($ocupado) {
        $proceso = (Get-Process -Id $ocupado.OwningProcess -ErrorAction SilentlyContinue).ProcessName
        if ($proceso -match "python|uvicorn") {
            throw "El puerto $puerto lo usa el bot de desarrollo ($proceso). Ciérralo (Ctrl+C en su terminal) y vuelve a intentar."
        }
    }
    if (Get-Process cloudflared -ErrorAction SilentlyContinue) {
        Write-Warning "Hay un cloudflared corriendo fuera de Docker. Ciérralo para que no compita por el webhook."
    }
}

function Show-Estado {
    $bot = Get-Valor "BOT_LOCAL_PORT" "8090"
    $api = Get-Valor "API_LOCAL_PORT" "8000"
    $panel = Get-Valor "PANEL_LOCAL_PORT" "3000"
    try { $salud = Invoke-RestMethod "http://localhost:$bot/health" -TimeoutSec 5 } catch { $salud = $null }
    Write-Host ""
    Write-Host "  Brota" -ForegroundColor Green
    Write-Host "  Panel de coordinación : http://localhost:$panel"
    Write-Host "  API                   : http://localhost:$api"
    if ($salud -and $salud.url_publica) {
        Write-Host "  Brisa en WhatsApp     : $($salud.url_publica)/webhook (registrado en Meta)" -ForegroundColor Green
    } else {
        Write-Host "  Brisa en WhatsApp     : conectando... (revisa: .\brota.ps1 logs bot)" -ForegroundColor Yellow
    }
    Write-Host ""
}

switch ($Accion) {
    "levantar" {
        Test-Requisitos
        Write-Host "Levantando Brota (la primera vez tarda unos minutos en construir)..." -ForegroundColor Cyan
        Invoke-Compose @("up", "-d", "--build", "--wait")
        # El túnel gratuito de Cloudflare caduca si queda prendido muchas horas ("Tunnel not found"):
        # se reinicia en cada arranque para tener siempre una dirección nueva; Brisa la registra en Meta.
        Invoke-Compose @("restart", "tunel")
        $bot = Get-Valor "BOT_LOCAL_PORT" "8090"
        Write-Host "Esperando a que Brisa se conecte a Meta..." -ForegroundColor Cyan
        for ($i = 0; $i -lt 30; $i++) {
            try { if ((Invoke-RestMethod "http://localhost:$bot/health" -TimeoutSec 5).url_publica) { break } } catch { }
            Start-Sleep -Seconds 3
        }
        Show-Estado
    }
    "estado" { Invoke-Compose @("ps"); Show-Estado }
    "logs" {
        $extra = @("logs", "-f", "--tail", "100")
        if ($Servicio) { $extra += $Servicio }
        Invoke-Compose $extra
    }
    "bajar" { Invoke-Compose @("down"); Write-Host "Brota detenido. Los datos se conservan." -ForegroundColor Cyan }
}
