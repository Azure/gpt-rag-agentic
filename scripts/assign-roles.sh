#!/bin/bash

# This script should be used to assign permissions so you can run the solution locally.

# Display the currently logged-in Azure account with subscription ID and user name
accountInfo=$(az account show --query '{Name:name, User: user.name, SubscriptionID:id, TenantID:tenantId}')
echo "Account Name: $(echo $accountInfo | grep -oP '"Name": "\K[^"]*')"
echo "User: $(echo $accountInfo | grep -oP '"User": "\K[^"]*')"
echo "Subscription ID: $(echo $accountInfo | grep -oP '"SubscriptionID": "\K[^"]*')"
echo "Tenant ID: $(echo $accountInfo | grep -oP '"TenantID": "\K[^"]*')"

# Extract the subscription ID
subscriptionId=$(echo $accountInfo | grep -oP '"SubscriptionID": "\K[^"]*')

# Get the object ID of the currently logged-in user
principalId=$(az ad signed-in-user show --query id --output tsv)
echo "Detected user object ID: $principalId"

echo "Please confirm the above account details are correct. If not, log in using 'az login'."
read -p "Press Enter to continue..."

# Prompt for user input
read -p "Enter the name of your resource group: " resourceGroupName
read -p "Enter the name of your Cosmos DB account: " cosmosDbaccountName
read -p "Enter the name of your Azure OpenAI service: " openAIAccountName
read -p "Enter the name of your AI Search service: " searchServiceName

# Built-in CosmosDB role ID for Data Contributor
roleDefinitionId='00000000-0000-0000-0000-000000000002'

# Assign CosmosDB Data Contributor role
echo "Assigning CosmosDB Data Contributor role..."
az cosmosdb sql role assignment create \
  --account-name "$cosmosDbaccountName" \
  --resource-group "$resourceGroupName" \
  --scope "/" \
  --principal-id "$principalId" \
  --role-definition-id "$roleDefinitionId"

# Assign Cognitive Services OpenAI User role
# echo "Assigning Cognitive Services OpenAI User role..."
# az role assignment create \
#   --role "Cognitive Services OpenAI User" \
#   --assignee "$principalId" \
#   --scope "/subscriptions/$subscriptionId/resourceGroups/$resourceGroupName/providers/Microsoft.CognitiveServices/accounts/$openAIAccountName"

command="az role assignment create --role \"Cognitive Services OpenAI User\" --scope /subscriptions/$subscriptionId/resourceGroups/$resourceGroupName/providers/Microsoft.CognitiveServices/accounts/$openAIAccountName --assignee-object-id $principalId"
echo "Constructed Command: $command"
eval $command

# Assign Search Index Data Reader role
echo "Assigning Search Index Data Reader role..."
command="az role assignment create --role \"Search Index Data Reader\" --scope /subscriptions/$subscriptionId/resourceGroups/$resourceGroupName/providers/Microsoft.Search/searchServices/$searchServiceName --assignee-object-id $principalId"
echo "Constructed Command: $command"
eval $command


echo "Role assignments completed successfully."