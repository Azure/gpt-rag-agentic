#!/bin/bash

# This script assigns permissions to run the solution locally with services in potentially different resource groups.

# Display the currently logged-in Azure account with subscription ID and user name
accountInfo=$(az account show --query '{Name:name, User: user.name, SubscriptionID:id, TenantID:tenantId}')
echo "Account Name: $(echo $accountInfo | grep -oP '"Name": "\K[^"]*')"
echo "User: $(echo $accountInfo | grep -oP '"User": "\K[^"]*')"
echo "Subscription ID: $(echo $accountInfo | grep -oP '"SubscriptionID": "\K[^"]*')"
echo "Tenant ID: $(echo $accountInfo | grep -oP '"TenantID": "\K[^"]*')"

signedInType=$(az account show --query "user.type" -o tsv)
if [ "$signedInType" = "servicePrincipal" ]; then
  assigneePrincipalType="ServicePrincipal"
else
  assigneePrincipalType="User"
fi
echo "Assignee principal type: $assigneePrincipalType"

# Extract the subscription ID
subscriptionId=$(echo $accountInfo | grep -oP '"SubscriptionID": "\K[^"]*')

# Get the object ID of the currently logged-in user
principalId=$(az ad signed-in-user show --query id --output tsv)
echo "Detected user object ID: $principalId"

echo "Please confirm the above account details are correct. If not, log in using 'az login'."
read -p "Press Enter to continue..."

# Prompt for CosmosDB resource group and account name
read -p "Enter the resource group for your CosmosDB account: " cosmosResourceGroup
read -p "Enter the name of your CosmosDB account: " cosmosDbAccountName

# Assign CosmosDB Data Contributor role
roleDefinitionId='00000000-0000-0000-0000-000000000002'
echo "Assigning CosmosDB Data Contributor role..."
az cosmosdb sql role assignment create \
  --account-name "$cosmosDbAccountName" \
  --resource-group "$cosmosResourceGroup" \
  --scope "/" \
  --principal-id "$principalId" \
  --role-definition-id "$roleDefinitionId"

# Prompt for resource group for Storage if different from CosmosDB
read -p "Is the Storage account in the same resource group as the CosmosDB service? (y/n): " sameGroupStorage
if [[ "$sameGroupStorage" == "y" ]]; then
  storageResourceGroup=$cosmosResourceGroup
else
  read -p "Enter the resource group for your Storage account: " storageResourceGroup
fi

# Prompt for Storage account name
read -p "Enter the name of your Storage account: " storageAccountName

# Assign Storage Blob Data Reader role
echo "Assigning Storage Blob Data Reader role..."
az role assignment create \
  --role "Storage Blob Data Reader" \
  --scope "/subscriptions/$subscriptionId/resourceGroups/$storageResourceGroup/providers/Microsoft.Storage/storageAccounts/$storageAccountName" \
  --assignee-object-id "$principalId" \
  --assignee-principal-type "$assigneePrincipalType"

# Prompt for Azure OpenAI service resource group
read -p "Is the Azure OpenAI service in the same resource group as the Storage Account? (y/n): " sameGroupOpenAI
if [[ "$sameGroupOpenAI" == "y" ]]; then
  openAIResourceGroup=$storageResourceGroup
else
  read -p "Enter the resource group for your Azure OpenAI service: " openAIResourceGroup
fi

# Prompt for Azure OpenAI account name
read -p "Enter the name of your Azure OpenAI service: " openAIAccountName

echo "Assigning Cognitive Services OpenAI User role..."
az role assignment create \
  --role "Cognitive Services OpenAI User" \
  --scope "/subscriptions/$subscriptionId/resourceGroups/$openAIResourceGroup/providers/Microsoft.CognitiveServices/accounts/$openAIAccountName" \
  --assignee-object-id "$principalId" \
  --assignee-principal-type "$assigneePrincipalType"


# Prompt for AI Search service resource group
read -p "Is the AI Search service in the same resource group as the Azure OpenAI service? (y/n): " sameGroupSearch
if [[ "$sameGroupSearch" == "y" ]]; then
  searchResourceGroup=$openAIResourceGroup
else
  read -p "Enter the resource group for your AI Search service: " searchResourceGroup
fi

# Prompt for AI Search account name
read -p "Enter the name of your AI Search service: " searchServiceName

# Assign Search Index Data Reader role
echo "Assigning Search Index Data Reader role..."
az role assignment create \
  --role "Cognitive Services OpenAI User" \
  --scope "/subscriptions/$subscriptionId/resourceGroups/$openAIResourceGroup/providers/Microsoft.CognitiveServices/accounts/$openAIAccountName" \
  --assignee-object-id "$principalId" \
  --assignee-principal-type "$assigneePrincipalType"

echo "Role assignments completed successfully."
