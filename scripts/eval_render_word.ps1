param(
    [Parameter(Mandatory=$true)][string]$InputPath,
    [Parameter(Mandatory=$true)][string]$OutputPath
)
$ErrorActionPreference = 'Stop'
$inputDocumentPath = [System.IO.Path]::GetFullPath($InputPath)
$outputDocumentPath = [System.IO.Path]::GetFullPath($OutputPath)
if (-not (Test-Path -LiteralPath $inputDocumentPath)) { throw 'Input DOCX is missing' }
[System.IO.Directory]::CreateDirectory([System.IO.Path]::GetDirectoryName($outputDocumentPath)) | Out-Null
$wordApplication = $null
$renderDocument = $null
try {
    $wordApplication = New-Object -ComObject Word.Application
    $wordApplication.Visible = $false
    $wordApplication.DisplayAlerts = 0
    $renderDocument = $wordApplication.Documents.Open($inputDocumentPath, $false, $true)
    $renderDocument.Repaginate()
    $bodyPageCount = $renderDocument.ComputeStatistics(2)
    $renderDocument.ExportAsFixedFormat($outputDocumentPath, 17)
    Write-Output "Rendered PDF: $outputDocumentPath"
    Write-Output "Actual Word page count: $bodyPageCount"
} finally {
    if ($null -ne $renderDocument) { $renderDocument.Close(0); [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($renderDocument) }
    if ($null -ne $wordApplication) { $wordApplication.Quit(); [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($wordApplication) }
}
