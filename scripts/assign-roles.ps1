# Display the currently logged-in Azure account information
$accountInfo = az account show --query '{Name:name, User:user.name, SubscriptionID:id, TenantID:tenantId}' | ConvertFrom-Json
Write-Host "Account Name: $($accountInfo.Name)"
Write-Host "User: $($accountInfo.User)"
Write-Host "Subscription ID: $($accountInfo.SubscriptionID)"
Write-Host "Tenant ID: $($accountInfo.TenantID)"

# Determine if signed in as service principal
$signedInType = az account show --query "user.type" -o tsv
if ($signedInType -eq "servicePrincipal") {
    $assigneePrincipalType = "ServicePrincipal"
} else {
    $assigneePrincipalType = "User"
}
Write-Host "Assignee principal type: $assigneePrincipalType"

$subscriptionId = $accountInfo.SubscriptionID

# Get the object ID of the currently logged-in user
$principalId = az ad signed-in-user show --query id --output tsv
Write-Host "Detected user object ID: $principalId"

Read-Host "Please confirm the above account details are correct. Press Enter to continue..."

# Prompt for CosmosDB
$cosmosResourceGroup = Read-Host "Enter the resource group for your CosmosDB account"
$cosmosDbAccountName = Read-Host "Enter the name of your CosmosDB account"

Write-Host "Assigning CosmosDB Data Contributor role..."
az cosmosdb sql role assignment create `
  --account-name $cosmosDbAccountName `
  --resource-group $cosmosResourceGroup `
  --scope "/" `
  --principal-id $principalId `
  --role-definition-id "00000000-0000-0000-0000-000000000002"

# Prompt for Storage
$sameGroupStorage = Read-Host "Is the Storage account in the same resource group as the CosmosDB service? (y/n)"
if ($sameGroupStorage -eq "y") {
    $storageResourceGroup = $cosmosResourceGroup
} else {
    $storageResourceGroup = Read-Host "Enter the resource group for your Storage account"
}
$storageAccountName = Read-Host "Enter the name of your Storage account"

Write-Host "Assigning Storage Blob Data Reader role..."
az role assignment create `
  --role "Storage Blob Data Reader" `
  --scope "/subscriptions/$subscriptionId/resourceGroups/$storageResourceGroup/providers/Microsoft.Storage/storageAccounts/$storageAccountName" `
  --assignee-object-id $principalId `
  --assignee-principal-type $assigneePrincipalType

# Prompt for Azure OpenAI
$sameGroupOpenAI = Read-Host "Is the Azure OpenAI service in the same resource group as the Storage Account? (y/n)"
if ($sameGroupOpenAI -eq "y") {
    $openAIResourceGroup = $storageResourceGroup
} else {
    $openAIResourceGroup = Read-Host "Enter the resource group for your Azure OpenAI service"
}
$openAIAccountName = Read-Host "Enter the name of your Azure OpenAI service"

Write-Host "Assigning Cognitive Services OpenAI User role..."
az role assignment create `
  --role "Cognitive Services OpenAI User" `
  --scope "/subscriptions/$subscriptionId/resourceGroups/$openAIResourceGroup/providers/Microsoft.CognitiveServices/accounts/$openAIAccountName" `
  --assignee-object-id $principalId `
  --assignee-principal-type $assigneePrincipalType

# Prompt for AI Search
$sameGroupSearch = Read-Host "Is the AI Search service in the same resource group as the Azure OpenAI service? (y/n)"
if ($sameGroupSearch -eq "y") {
    $searchResourceGroup = $openAIResourceGroup
} else {
    $searchResourceGroup = Read-Host "Enter the resource group for your AI Search service"
}
$searchServiceName = Read-Host "Enter the name of your AI Search service"

Write-Host "Assigning Search Index Data Reader role..."
az role assignment create `
  --role "Cognitive Services OpenAI User" `
  --scope "/subscriptions/$subscriptionId/resourceGroups/$openAIResourceGroup/providers/Microsoft.CognitiveServices/accounts/$openAIAccountName" `
  --assignee-object-id $principalId `
  --assignee-principal-type $assigneePrincipalType

Write-Host "Role assignments completed successfully."