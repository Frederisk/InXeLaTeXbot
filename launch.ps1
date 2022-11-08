#!/usr/bin/env -S pwsh -nop

using namespace System;
using namespace System.Management.Automation;

Get-Content -Path '.env' -Encoding utf8NoBOM | ForEach-Object -Process {
    $name, $value = $_.Split('=');
    [Environment]::SetEnvironmentVariable($name, $value);
}

[ApplicationInfo]$python = Get-Command -Name 'python';
&$python 'InLaTeXbot.py';

if (-not $?) {
    Write-Error -Message 'Running bot failed.';
}
