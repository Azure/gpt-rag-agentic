# Function to check if a package is installed
function Check-PackageInstalled {
    param (
        [string]$PackageName
    )
    $package = pip show $PackageName 2>&1
    return $package -notlike "*WARNING: Package(s) not found*"
}

# Colors for different messages
$colorInfo = "Cyan"
$colorWarning = "Yellow"
$colorSuccess = "Green"
$packagesMissing = $false

# Check if autogen and azure-functions are installed
Write-Host "Checking if required packages are installed..." -ForegroundColor $colorInfo
if (!(Check-PackageInstalled "autogen")) {
    Write-Host "Warning: 'autogen' is missing." -ForegroundColor $colorWarning
    $packagesMissing = $true
}
if (!(Check-PackageInstalled "azure-functions")) {
    Write-Host "Warning: 'azure-functions' is missing." -ForegroundColor $colorWarning
    $packagesMissing = $true
}

# If packages are missing, display a message and exit
if ($packagesMissing) {
    Write-Host "Please run 'pip install -r requirements.txt' to install the necessary dependencies." -ForegroundColor $colorWarning
    exit 1
} else {
    Write-Host "All required packages are installed!" -ForegroundColor $colorSuccess
}

# Run the Python script
$env:PYTHONPATH = "./;$env:PYTHONPATH"
python evaluations/genai_evaluation.py