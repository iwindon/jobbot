param([Parameter(Mandatory)] [string] $Root, [Parameter(Mandatory)] [string] $Destination)
# Builds a zip with forward-slash entry names (Compress-Archive on Windows PowerShell 5 writes backslashes, which break on Linux).
Add-Type -AssemblyName System.IO.Compression, System.IO.Compression.FileSystem
if (Test-Path $Destination) { Remove-Item $Destination }
$zip = [IO.Compression.ZipFile]::Open($Destination, 'Create')
try {
    $files = @('function_app.py', 'host.json', 'requirements.txt') | ForEach-Object { Get-Item (Join-Path $Root $_) }
    $files += Get-ChildItem (Join-Path $Root 'jobbot') -Recurse -File -Filter *.py
    foreach ($f in $files) {
        $entry = $f.FullName.Substring($Root.TrimEnd('\').Length + 1).Replace('\', '/')
        [void][IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $f.FullName, $entry)
    }
} finally { $zip.Dispose() }
