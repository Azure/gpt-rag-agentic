#!/bin/bash

# Function to check if a package is installed
check_package_installed() {
    pip show "$1" > /dev/null 2>&1
    return $?
}

# Check if autogen and azure-functions are installed
echo "🔍 Checking if required packages are installed..."
if ! check_package_installed "autogen" || ! check_package_installed "asyncio"; then
    echo "⚠️ Oops! It looks like 'autogen' and/or 'azure-functions' are missing."
    echo "💡 Please run 'pip install -r requirements.txt' to install the necessary dependencies."
else
    echo "✅ All required packages are installed!"
fi

# Run the Python script
python chat.py
