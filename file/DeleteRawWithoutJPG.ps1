# Define RAW file extensions to look for
$rawExtensions = @(".NEF", ".CR2", ".ARW", ".DNG", ".ORF", ".RAF", ".CR3")

# Get current location
$currentDir = Get-Location

Write-Host "Scanning $currentDir for orphaned RAW files..."

# Get all files matching RAW extensions
$rawFiles = Get-ChildItem -Path $currentDir -File | Where-Object { $rawExtensions -contains $_.Extension.ToUpper() }

foreach ($rawFile in $rawFiles) {
    $baseName = $rawFile.BaseName
    $jpgPath = Join-Path $currentDir ($baseName + ".jpg")
    $jpegPath = Join-Path $currentDir ($baseName + ".jpeg")

    # Check if .jpg or .jpeg exists (Test-Path is case-insensitive on Windows)
    if (-not ((Test-Path $jpgPath) -or (Test-Path $jpegPath))) {
        Write-Host "Deleting orphaned RAW file: $($rawFile.Name)"
        Remove-Item -Path $rawFile.FullName -Force
    }
}

Write-Host "Done."
