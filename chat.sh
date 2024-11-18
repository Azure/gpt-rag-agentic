#!/bin/bash

# Function to check if a package is installed
check_package_installed() {
    pip show "$1" > /dev/null 2>&1
    return $?
}

# Check if autogen and azure-functions are installed
echo "🔍 Checking if required packages are installed..."
if ! check_package_installed "autogen" ; then
    echo "⚠️ Oops! It looks like 'autogen' is missing."
    echo "💡 Please run 'pip install -r requirements.txt' to install the necessary dependencies."
else
    echo "✅ All required packages are installed!"
fi

# Load environment variables from .env file
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
    echo "🌍 Environment variables loaded from .env file."
else
    echo "⚠️ No .env file found. Please create one if you have environment-specific configurations."
fi

# Run the Python script
python chat.py