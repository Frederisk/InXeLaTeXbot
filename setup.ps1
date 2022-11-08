#!/usr/bin/env -S pwsh -nop

using namespace System;
using namespace System.IO;

if (Get-Item -Path '.env') {
    Remove-Item -Path '.env' -Force;
}

[String]$resourcePath = [Path]::Combine('.', 'resources');
[String]$pklPath = [Path]::Combine($resourcePath, 'default.pkl');

@('options', 'preambles', 'users') | ForEach-Object -Process {
    Copy-Item -Path $pklPath -Destination [Path]::Combine($resourcePath, "$_.pkl")
}

[String]$token = Read-Host -Prompt 'Your bot token';
[Int64]$group = Read-Host -Prompt 'Your group ID';

New-Item -Path '.env' -ItemType File -Value @"
BOT_TOKEN=$token
GROUP_ID=$group
"@
