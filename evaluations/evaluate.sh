#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Function to check if a package is installed
check_package_installed() {
    pip show "$1" > /dev/null 2>&1
    return $?
}

# Function to check if the user is logged in to Azure
check_azure_login() {
    if ! az account show > /dev/null 2>&1; then
        echo "⚠️ You are not logged into Azure. Please run 'az login' to log in."
        exit 1
    else
        echo "✅ You are logged into Azure."
    fi
}

# Check if the user is logged into Azure
echo "🔍 Verifying Azure login status..."
check_azure_login

# Check if 'autogen' is installed
echo "🔍 Checking if required packages are installed..."
if ! check_package_installed "autogen"; then
    echo "⚠️ Oops! It looks like 'autogen' is missing."
    echo "💡 Please run 'pip install -r requirements.txt' to install the necessary dependencies."
    exit 1
else
    echo "✅ All required packages are installed!"
fi

# Determine the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
echo "📁 Script is located in: $SCRIPT_DIR"

# Define the directory where .jsonl files are located (the evaluations folder itself)
DATA_DIR="$SCRIPT_DIR"

echo "🔍 Searching for .jsonl files in: $DATA_DIR"

# Find all .jsonl files directly inside DATA_DIR without descending into subdirectories
mapfile -t jsonl_files < <(find "$DATA_DIR" -maxdepth 1 -type f \( -iname "test-*.jsonl" \))

# Check if any .jsonl files are found
if [ ${#jsonl_files[@]} -eq 0 ]; then
    echo "⚠️ No .jsonl files found in $DATA_DIR."
    exit 1
fi

# Display the list of .jsonl files with relative paths for better readability
echo "📄 Available .jsonl files:"
for i in "${!jsonl_files[@]}"; do
    # Get the basename of the file for display
    basename_file="$(basename "${jsonl_files[$i]}")"
    echo "$((i + 1))) $basename_file"
done

# Prompt the user to select a file
while true; do
    read -rp "Please enter the number corresponding to the .jsonl file you want to use: " selection
    # Check if the input is a valid number within the range
    if [[ "$selection" =~ ^[0-9]+$ ]] && [ "$selection" -ge 1 ] && [ "$selection" -le "${#jsonl_files[@]}" ]; then
        chosen_file="${jsonl_files[$((selection - 1))]}"
        echo "✅ You have selected: $(basename "$chosen_file")"
        break
    else
        echo "⚠️ Invalid selection. Please enter a number between 1 and ${#jsonl_files[@]}."
    fi
done

# Run the Python script with the selected file as a parameter
export PYTHONPATH=./:$PYTHONPATH
echo "🚀 Running the Python evaluation script..."
python evaluations/genai_evaluation.py --test-data "$chosen_file"
