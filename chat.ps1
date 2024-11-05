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

# Load environment variables from .env file
if (Test-Path .env) {
    Get-Content .env | ForEach-Object {
        if ($_ -match "^\s*([^#=]+)\s*=\s*(.+?)\s*$") {
            $envName = $matches[1].Trim()
            $envValue = $matches[2].Trim()
            [System.Environment]::SetEnvironmentVariable($envName, $envValue)
        }
    }
    Write-Host "Environment variables loaded from .env file." -ForegroundColor $colorInfo
} else {
    Write-Host "Warning: No .env file found. Please create one if you have environment-specific configurations." -ForegroundColor $colorWarning
}

# Run the Python script if all packages are installed
python chat.py
