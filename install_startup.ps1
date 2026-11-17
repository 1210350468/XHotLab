Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$pythonw = Join-Path $PSScriptRoot '.venv\Scripts\pythonw.exe'
if (!(Test-Path -LiteralPath $pythonw)) {
    throw 'Missing Python background executable. Install the project virtual environment.'
}
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$arguments = '-m app.background_service'

$action = New-ScheduledTaskAction -Execute $pythonw -Argument $arguments -WorkingDirectory $PSScriptRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $identity
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Days 365) -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName 'XHotLab Creator' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Start local XHotLab trend and visual creator on user sign-in' -Force | Out-Null
Get-ScheduledTask -TaskName 'XHotLab Creator' | Select-Object TaskName, State
