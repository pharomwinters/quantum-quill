<#
.SYNOPSIS
    Builds the folder tree described by Folder-layout.yaml (Johnny Decimal + PARA).

.DESCRIPTION
    Creates area folders and their category folders. Item folders (32.01 Acme Corp)
    are NOT created — those are per-record and belong to whatever fills the tree later.

    Idempotent: New-Item -Force returns existing directories untouched, so re-running
    after adding a category to the YAML backfills only what is missing.

.EXAMPLE
    .\New-VaultTree.ps1 -LayoutFile .\Folder-layout.yaml -Root D:\vault -WhatIf

.EXAMPLE
    .\New-VaultTree.ps1 -LayoutFile .\Folder-layout.yaml -Root D:\vault -WriteAreaReadme
#>

[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)]
    [ValidateScript({ Test-Path $_ -PathType Leaf })]
    [string]$LayoutFile,

    # Overrides meta.root in the YAML. Required if meta.root is still null.
    [string]$Root,

    # Rule 'x0-reserved' says every area gets an x0 meta category, but no x0 is
    # declared in the file. Synthesized here unless skipped.
    [switch]$SkipAreaMeta,

    [string]$AreaMetaName = 'Meta',

    # Drop a README.md in each area's x0 folder, built from the area's own rule text.
    [switch]$WriteAreaReadme
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Import-Module powershell-yaml -ErrorAction Stop

# --- Load -------------------------------------------------------------------

$layout = Get-Content -Path $LayoutFile -Raw | ConvertFrom-Yaml

$root = if ($Root) { $Root } elseif ($layout.meta.root) { $layout.meta.root } else {
    throw "meta.root is null in $LayoutFile. Pass -Root, or set it in the file."
}

$conventions = $layout.conventions
$invalidChars = [System.IO.Path]::GetInvalidFileNameChars()

# --- Helpers ----------------------------------------------------------------

function Expand-NameTemplate {
    # Literal token substitution, not regex — display names may contain & and other
    # characters that would otherwise be interpreted.
    param([string]$Template, [hashtable]$Tokens)

    $name = $Template
    foreach ($key in $Tokens.Keys) {
        $name = $name.Replace("{$key}", [string]$Tokens[$key])
    }
    return $name
}

function Assert-ValidFolderName {
    # conventions.name_charset is 'unrestricted', which the filesystem does not agree
    # with. Fail loudly here rather than half-building the tree.
    param([string]$Name)

    $offenders = $Name.ToCharArray() | Where-Object { $invalidChars -contains $_ }
    if ($offenders) {
        throw "Folder name '$Name' contains characters illegal on this filesystem: $($offenders -join ' ')"
    }
    return $Name
}

$created = 0
function New-VaultFolder {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        Write-Verbose "create  $Path"
        $script:created++
    }
    New-Item -Path $Path -ItemType Directory -Force | Out-Null
}

# --- Build ------------------------------------------------------------------

New-VaultFolder -Path $root

foreach ($area in $layout.areas) {

    $areaFolder = Assert-ValidFolderName (Expand-NameTemplate $conventions.area_folder @{
        jd     = $area.jd
        letter = $area.letter
        name   = $area.name
    })
    $areaPath = Join-Path $root $areaFolder
    New-VaultFolder -Path $areaPath

    # Synthesize the x0 meta category. "00-09" -> "00", "30-39" -> "30".
    if (-not $SkipAreaMeta) {
        $x0 = ($area.jd -split '-')[0].Substring(0, 1) + '0'

        $declared = @($area.categories | ForEach-Object { $_.jd })
        if ($declared -notcontains $x0) {
            $metaFolder = Expand-NameTemplate $conventions.category_folder @{
                jd = $x0; name = $AreaMetaName
            }
            $metaPath = Join-Path $areaPath $metaFolder
            New-VaultFolder -Path $metaPath

            if ($WriteAreaReadme) {
                $readme = Join-Path $metaPath 'README.md'
                if (-not (Test-Path -LiteralPath $readme)) {
                    $body = @(
                        "# $($area.jd)$($area.letter) $($area.name)"
                        ""
                        "- **id:** ``$($area.id)``"
                        "- **zone:** $($area.zone)"
                        "- **provenance:** $($area.provenance)"
                        ""
                        "## Rule"
                        ""
                        $area.rule.Trim()
                    ) -join [Environment]::NewLine

                    if ($PSCmdlet.ShouldProcess($readme, 'Write README')) {
                        Set-Content -Path $readme -Value $body -Encoding UTF8
                    }
                }
            }
        }
    }

    foreach ($category in $area.categories) {
        $categoryFolder = Assert-ValidFolderName (Expand-NameTemplate $conventions.category_folder @{
            jd = $category.jd; name = $category.name
        })
        New-VaultFolder -Path (Join-Path $areaPath $categoryFolder)
    }
}

# --- Report -----------------------------------------------------------------

if ($WhatIfPreference) {
    Write-Host "`nDry run. $created folders would be created under $root."
} else {
    Write-Host "`nDone. $created folders created under $root (existing folders left alone)."
}