# Function to check if a package is installed
function Check-PackageInstalled {
    param (
        [string]$PackageName
    )
    $package = pip show $PackageName 2>&1
    return $package -notlike "*WARNING: Package(s) not found*"
}

# Function to check if the user is logged into Azure
function Check-AzureLogin {
    $account = az account show 2>&1
    if ($account -like "*Please run 'az login'*") {
        Write-Host "⚠️ You are not logged into Azure. Please run 'az login' to log in." -ForegroundColor Yellow
        exit 1
    } else {
        Write-Host "✅ You are logged into Azure." -ForegroundColor Green
    }
}

# Colors for different messages
$colorInfo = "Cyan"
$colorWarning = "Yellow"
$colorSuccess = "Green"

# Check if the user is logged into Azure
Write-Host "🔍 Verifying Azure login status..." -ForegroundColor $colorInfo
Check-AzureLogin

$packagesMissing = $false

# Check if required packages are installed
Write-Host "🔍 Checking if required packages are installed..." -ForegroundColor $colorInfo

$requiredPackages = @("autogen", "azure-functions")
foreach ($pkg in $requiredPackages) {
    if (-not (Check-PackageInstalled $pkg)) {
        Write-Host "⚠️ Warning: '$pkg' is missing." -ForegroundColor $colorWarning
        $packagesMissing = $true
    }
}

# If packages are missing, display a message and exit
if ($packagesMissing) {
    Write-Host "💡 Please run 'pip install -r requirements.txt' to install the necessary dependencies." -ForegroundColor $colorWarning
    exit 1
} else {
    Write-Host "✅ All required packages are installed!" -ForegroundColor $colorSuccess
}

# Determine the directory where the script is located
$scriptDir = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition
Write-Host "📁 Script is located in: $scriptDir" -ForegroundColor $colorInfo

# Define the directory where .jsonl files are located (the script directory itself)
$dataDir = $scriptDir

Write-Host "🔍 Searching for .jsonl files in: $dataDir" -ForegroundColor $colorInfo

# Find all .jsonl files directly inside DATA_DIR without descending into subdirectories
$jsonlFiles = Get-ChildItem -Path $dataDir -Filter *.jsonl -File | Where-Object { $_.Name -like "test-*.jsonl" }

# Check if any .jsonl files are found
if ($jsonlFiles.Count -eq 0) {
    Write-Host "⚠️ No .jsonl files found in $dataDir." -ForegroundColor $colorWarning
    exit 1
}

# Display the list of .jsonl files with numbering
Write-Host "📄 Available .jsonl files:" -ForegroundColor $colorInfo
for ($i = 0; $i -lt $jsonlFiles.Count; $i++) {
    Write-Host "$($i + 1)) $($jsonlFiles[$i].Name)" -ForegroundColor $colorInfo
}

# Function to prompt user for selection
function Prompt-ForSelection {
    param (
        [int]$Max
    )
    while ($true) {
        $selection = Read-Host "Please enter the number corresponding to the .jsonl file you want to use"
        if ($selection -match '^\d+$' -and $selection -ge 1 -and $selection -le $Max) {
            return [int]$selection
        } else {
            Write-Host "⚠️ Invalid selection. Please enter a number between 1 and $Max." -ForegroundColor $colorWarning
        }
    }
}

# Prompt the user to select a file
$selectedNumber = Prompt-ForSelection -Max $jsonlFiles.Count
$chosenFile = $jsonlFiles[$selectedNumber - 1].FullName
Write-Host "✅ You have selected: $(Split-Path $chosenFile -Leaf)" -ForegroundColor $colorSuccess

# Set the PYTHONPATH environment variable
$env:PYTHONPATH = "$dataDir;$env:PYTHONPATH"

# Run the Python evaluation script with the selected file as a parameter
Write-Host "🚀 Running the Python evaluation script..." -ForegroundColor $colorInfo
python "$dataDir\evaluations\genai_evaluation.py" --test-data "`"$chosenFile`""

# Optional: Check the exit code of the Python script
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ The Python script encountered an error." -ForegroundColor $colorWarning
    exit $LASTEXITCODE
} else {
    Write-Host "✅ Python evaluation script completed successfully!" -ForegroundColor $colorSuccess
}
