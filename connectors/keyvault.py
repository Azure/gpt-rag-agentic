import os
from azure.identity.aio import DefaultAzureCredential as AsyncDefaultAzureCredential
from azure.keyvault.secrets.aio import SecretClient as AsyncSecretClient
from azure.core.exceptions import ResourceNotFoundError, ClientAuthenticationError

##########################################################
# KEY VAULT 
##########################################################

async def get_secret(secretName):
    try:
        keyVaultName = os.environ["AZURE_KEY_VAULT_NAME"]
        KVUri = f"https://{keyVaultName}.vault.azure.net"
        async with AsyncDefaultAzureCredential() as credential:
            async with AsyncSecretClient(vault_url=KVUri, credential=credential) as client:
                retrieved_secret = await client.get_secret(secretName)
                value = retrieved_secret.value
        return value    
    except KeyError:
        print("Environment variable AZURE_KEY_VAULT_NAME not found.")
        return None
    except ClientAuthenticationError:
        print("Authentication failed. Please check your credentials.")
        return None
    except ResourceNotFoundError:
        print(f"Secret '{secretName}' not found in the Key Vault.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None