#!/bin/bash

# Load environment variables from .env file in ../ directory
if [ -f "./.env" ]; then
  export $(grep -v '^#' ./.env | xargs)
else
  echo "Error: .env file not found in ./ directory."
  exit 1
fi

# Assign variables from .env to local variables
FABRIC_CONNECTION_ID=$FABRIC_CONNECTION_ID

# python -m util.test_fabric_connection
python -m util.generate_user_token
