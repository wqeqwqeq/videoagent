#!/usr/bin/env bash
# ================================================================
# Infrastructure Deployment Script for VideoAgent Function App
# ================================================================
# Deploys Azure Function App infrastructure using Bicep templates
#
# Usage:
#   ./deploy_infra.sh [--what-if]    - Deploy or preview infrastructure
#
# Options:
#   --what-if    Preview changes without deploying (dry run)
#
# Configuration:
#   - ../.env: Azure subscription, resource group, and storage settings
#   - parameters.json: Bicep template parameters (location, prefix, resource names)
#
# Prerequisites:
#   - Azure CLI installed and logged in (az login)
#   - .env file configured with Azure subscription and resource group
#   - parameters.json configured with bicep parameters
# ================================================================

set -euo pipefail

WHAT_IF=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --what-if)
            WHAT_IF=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo ""
            echo "Usage: ./deploy_infra.sh [--what-if]"
            echo ""
            echo "Options:"
            echo "  --what-if    Preview changes without deploying (dry run)"
            exit 1
            ;;
    esac
done

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env"
PARAMS_FILE="$SCRIPT_DIR/parameters.json"

# Check parameters.json exists
if [ ! -f "$PARAMS_FILE" ]; then
    echo "Error: parameters.json not found at $PARAMS_FILE"
    exit 1
fi

# Check .env exists
if [ ! -f "$ENV_FILE" ]; then
    echo "Error: .env file not found at $ENV_FILE"
    echo ""
    echo "Please copy .env.example to .env and configure your settings:"
    echo "  cp .env.example .env"
    echo "  nano .env"
    echo ""
    exit 1
fi

echo "Loading configuration..."

# Load settings from .env
source "$ENV_FILE"

# Read additional params from parameters.json
AZURE_LOCATION=$(jq -r '.parameters.location.value' "$PARAMS_FILE")
RESOURCE_PREFIX=$(jq -r '.parameters.resourcePrefix.value' "$PARAMS_FILE")

# Validate required .env variables
REQUIRED_ENV_VARS=(
    "AZURE_SUBSCRIPTION_ID"
    "AZURE_RESOURCE_GROUP"
    "STORAGE_ACCOUNT_NAME"
    "STORAGE_CONTAINER"
)

MISSING_VARS=()
for VAR in "${REQUIRED_ENV_VARS[@]}"; do
    if [ -z "${!VAR:-}" ]; then
        MISSING_VARS+=("$VAR")
    fi
done

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    echo "Error: Missing required environment variables in .env:"
    printf '   - %s\n' "${MISSING_VARS[@]}"
    echo ""
    echo "Please configure these in your .env file"
    exit 1
fi

# Set subscription
echo "Setting Azure subscription..."
az account set --subscription "$AZURE_SUBSCRIPTION_ID"

# Check if resource group exists
if ! az group show --name "$AZURE_RESOURCE_GROUP" &>/dev/null; then
    echo "Error: Resource group '$AZURE_RESOURCE_GROUP' does not exist"
    echo ""
    echo "Please create the resource group first or update parameters.json"
    exit 1
fi

# Display deployment info
echo ""
echo "================================================================"
echo "VideoAgent Function App Deployment"
echo "================================================================"
echo "From .env:"
echo "   Subscription ID:    $AZURE_SUBSCRIPTION_ID"
echo "   Resource Group:     $AZURE_RESOURCE_GROUP"
echo "   Storage Account:    $STORAGE_ACCOUNT_NAME"
echo "   Storage Container:  $STORAGE_CONTAINER"
echo ""
echo "From parameters.json:"
echo "   Location:           $AZURE_LOCATION"
echo "   Resource Prefix:    $RESOURCE_PREFIX"
echo "   Function App Name:  ${RESOURCE_PREFIX}-func"
echo "================================================================"
echo ""

if [ "$WHAT_IF" = true ]; then
    echo "Previewing infrastructure deployment (what-if mode)..."
    echo ""

    az deployment group what-if \
        --name "videoagent-whatif-$(date +%s)" \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --template-file "$SCRIPT_DIR/functionapp.bicep" \
        --parameters "$PARAMS_FILE" \
        --parameters \
            storageAccountName="$STORAGE_ACCOUNT_NAME" \
            storageContainerName="$STORAGE_CONTAINER"

    echo ""
    echo "================================================================"
    echo "What-if analysis complete!"
    echo "================================================================"
    echo ""
    echo "To deploy for real, run without --what-if:"
    echo "   ./deploy_infra.sh"
    echo ""
else
    echo "Deploying infrastructure..."
    echo ""

    az deployment group create \
        --name "videoagent-$(date +%s)" \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --template-file "$SCRIPT_DIR/functionapp.bicep" \
        --parameters "$PARAMS_FILE" \
        --parameters \
            storageAccountName="$STORAGE_ACCOUNT_NAME" \
            storageContainerName="$STORAGE_CONTAINER"

    echo ""
    echo "================================================================"
    echo "Infrastructure deployed successfully!"
    echo "================================================================"
    echo ""
    echo "Resources created:"
    echo "   - Function App: ${RESOURCE_PREFIX}-func"
    echo "   - Storage Container: $STORAGE_CONTAINER"
    echo ""
    echo "Next steps:"
    echo "   1. Deploy application code: ./deploy_script.sh"
    echo "   2. View your app: https://${RESOURCE_PREFIX}-func.azurewebsites.net"
    echo ""
fi
