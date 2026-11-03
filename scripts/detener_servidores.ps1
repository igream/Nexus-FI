# Detiene todos los servidores de Nexus FI que estén corriendo en este equipo.
#
# Solo afecta procesos de Python que ejecutan "main.py --serve" (o uvicorn con backend.app);
# no cierra otros programas de Python.
#
# Uso:
#   stop.bat                 detiene todos los servidores
#   stop.bat -Listar         solo muestra cuáles hay, sin detenerlos

param([switch]$Listar)

$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Get-ServidoresNexus {
    Get-CimInstance Win32_Process | Where-Object {
        $_.Name -match '^(python|pythonw|py)[\d.]*\.exe$' -and $_.CommandLine -and (
            ($_.CommandLine -match 'main\.py' -and $_.CommandLine -match '--serve|(^|\s)-s(\s|$)') -or
            ($_.CommandLine -match 'uvicorn' -and $_.CommandLine -match 'backend\.app')
        )
    }
}

$servidores = @(Get-ServidoresNexus)

if ($servidores.Count -eq 0) {
    Write-Host 'No hay servidores de Nexus FI en ejecución.' -ForegroundColor Green
    exit 0
}

Write-Host ("Servidores de Nexus FI encontrados: {0}" -f $servidores.Count) -ForegroundColor Cyan
foreach ($p in $servidores) {
    $puertos = (Get-NetTCPConnection -OwningProcess $p.ProcessId -State Listen |
                Select-Object -ExpandProperty LocalPort -Unique) -join ', '
    if (-not $puertos) { $puertos = '-' }
    $inicio = if ($p.CreationDate) { $p.CreationDate.ToString('dd/MM HH:mm') } else { '-' }
    Write-Host ("  PID {0,-6} puerto(s) {1,-11} desde {2}   {3}" -f $p.ProcessId, $puertos, $inicio, $p.CommandLine.Trim())
}

if ($Listar) {
    Write-Host 'Modo -Listar: no se detuvo ninguno.' -ForegroundColor Yellow
    exit 0
}

foreach ($p in $servidores) {
    Stop-Process -Id $p.ProcessId -Force
}
Start-Sleep -Milliseconds 800

$restantes = @(Get-ServidoresNexus)
if ($restantes.Count -eq 0) {
    Write-Host 'Listo: todos los servidores de Nexus FI se detuvieron.' -ForegroundColor Green
    $ocupado = Get-NetTCPConnection -LocalPort 8000 -State Listen
    if ($ocupado) {
        Write-Host ('Aviso: el puerto 8000 sigue ocupado por otro programa (PID {0}).' -f ($ocupado.OwningProcess | Select-Object -First 1)) -ForegroundColor Yellow
    }
    exit 0
}

Write-Host ('No se pudieron detener {0} proceso(s); intenta ejecutar stop.bat como administrador.' -f $restantes.Count) -ForegroundColor Red
exit 1
