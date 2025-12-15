#!/usr/bin/env bash
# ================================================================
# Application Deployment Script for VideoAgent Function App
# ================================================================
# Packages the Function App and deploys via zip with remote build
#
# Usage:
#   ./deploy_script.sh    - Deploy application code
#
# Configuration:
#   - ../.env: Azure subscription, resource group, and application settings
#   - parameters.json: Resource prefix and timer schedules
#
# Prerequisites:
#   - Azure CLI installed and logged in (az login)
#   - .env file configured with Azure subscription and resource group
#   - parameters.json configured
#   - Function App already deployed via deploy_infra.sh
#   - uv package manager installed (optional)
# ================================================================

set -euo pipefail

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/.."
ENV_FILE="$PROJECT_ROOT/.env"
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
RESOURCE_PREFIX=$(jq -r '.parameters.resourcePrefix.value' "$PARAMS_FILE")
ORCHESTRATOR_SCHEDULE=$(jq -r '.parameters.orchestratorSchedule.value' "$PARAMS_FILE")
VIDEO_SCHEDULE=$(jq -r '.parameters.videoSchedule.value' "$PARAMS_FILE")

# Validate required .env variables
REQUIRED_ENV_VARS=(
    # Azure deployment settings
    "AZURE_SUBSCRIPTION_ID"
    "AZURE_RESOURCE_GROUP"
    # Tableau settings
    "TABLEAU_SERVER_URL"
    "TABLEAU_SITE_ID"
    "TABLEAU_WORKBOOK_ID"
    "TABLEAU_AUTH_METHOD"
    # Azure OpenAI settings
    "AZURE_OPENAI_API_KEY"
    "AZURE_OPENAI_ENDPOINT"
    "AZURE_OPENAI_DEPLOYMENT_NAME"
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

FUNC_APP_NAME="${RESOURCE_PREFIX}-func"

echo ""
echo "================================================================"
echo "VideoAgent Function App Deployment"
echo "================================================================"
echo "Resource Group:     $AZURE_RESOURCE_GROUP"
echo "Function App:       $FUNC_APP_NAME"
echo "================================================================"
echo ""

# Set subscription
echo "Setting Azure subscription..."
az account set --subscription "$AZURE_SUBSCRIPTION_ID"

# Check if function app exists
if ! az functionapp show --name "$FUNC_APP_NAME" --resource-group "$AZURE_RESOURCE_GROUP" &>/dev/null; then
    echo "Error: Function App '$FUNC_APP_NAME' does not exist"
    echo ""
    echo "Please deploy infrastructure first:"
    echo "   ./deploy_infra.sh"
    exit 1
fi

# Step 1: Generate requirements.txt from pyproject.toml
echo "Step 1: Generating requirements.txt from pyproject.toml..."
cd "$PROJECT_ROOT"

# Check if uv is available
if command -v uv &> /dev/null; then
    uv pip compile pyproject.toml -o requirements.txt --quiet
    echo "   Generated requirements.txt using uv"
else
    echo "Warning: uv not found, checking for existing requirements.txt..."
    if [ ! -f "requirements.txt" ]; then
        echo "Error: requirements.txt not found and uv is not installed"
        echo "Please install uv or create requirements.txt manually"
        exit 1
    fi
    echo "   Using existing requirements.txt"
fi

# Add azure-functions to requirements if not present
if ! grep -q "azure-functions" requirements.txt; then
    echo "azure-functions" >> requirements.txt
    echo "   Added azure-functions to requirements.txt"
fi

# Step 2: Create deployment package
echo "Step 2: Creating deployment package..."
DEPLOY_DIR=$(mktemp -d)
ZIP_FILE="$DEPLOY_DIR/function_app.zip"

# Copy required files
cp function_app.py "$DEPLOY_DIR/"
cp host.json "$DEPLOY_DIR/"
cp requirements.txt "$DEPLOY_DIR/"
cp orchestrator.py "$DEPLOY_DIR/"
cp -r videoagent "$DEPLOY_DIR/"

# Remove __pycache__ directories
find "$DEPLOY_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$DEPLOY_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true

# Create zip file
cd "$DEPLOY_DIR"
zip -r "$ZIP_FILE" . -x "*.pyc" -x "__pycache__/*" > /dev/null
echo "   Created deployment package: $(du -h "$ZIP_FILE" | cut -f1)"

# Step 3: Deploy with remote build
echo "Step 3: Deploying to Azure Function App..."
az functionapp deployment source config-zip \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --name "$FUNC_APP_NAME" \
    --src "$ZIP_FILE" \
    --build-remote true \
    --output none

echo "   Deployment initiated with remote build"

# Step 4: Configure app settings
echo "Step 4: Configuring application settings..."

# Build settings array
SETTINGS=(
    "TABLEAU_SERVER_URL=$TABLEAU_SERVER_URL"
    "TABLEAU_SITE_ID=$TABLEAU_SITE_ID"
    "TABLEAU_WORKBOOK_ID=$TABLEAU_WORKBOOK_ID"
    "TABLEAU_AUTH_METHOD=$TABLEAU_AUTH_METHOD"
    "AZURE_OPENAI_API_KEY=$AZURE_OPENAI_API_KEY"
    "AZURE_OPENAI_ENDPOINT=$AZURE_OPENAI_ENDPOINT"
    "AZURE_OPENAI_DEPLOYMENT_NAME=$AZURE_OPENAI_DEPLOYMENT_NAME"
)

# Add optional Tableau PAT settings
if [ -n "${TABLEAU_PAT_NAME:-}" ]; then
    SETTINGS+=("TABLEAU_PAT_NAME=$TABLEAU_PAT_NAME")
fi
if [ -n "${TABLEAU_PAT_VALUE:-}" ]; then
    SETTINGS+=("TABLEAU_PAT_VALUE=$TABLEAU_PAT_VALUE")
fi

# Add optional Tableau username/password settings
if [ -n "${TABLEAU_USERNAME:-}" ]; then
    SETTINGS+=("TABLEAU_USERNAME=$TABLEAU_USERNAME")
fi
if [ -n "${TABLEAU_PASSWORD:-}" ]; then
    SETTINGS+=("TABLEAU_PASSWORD=$TABLEAU_PASSWORD")
fi

# Add optional Azure OpenAI API version
if [ -n "${AZURE_OPENAI_API_VERSION:-}" ]; then
    SETTINGS+=("AZURE_OPENAI_API_VERSION=$AZURE_OPENAI_API_VERSION")
fi

az functionapp config appsettings set \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --name "$FUNC_APP_NAME" \
    --settings "${SETTINGS[@]}" \
    --output none

echo "   Application settings configured"

# Step 5: Cleanup
echo "Step 5: Cleaning up..."
rm -rf "$DEPLOY_DIR"
echo "   Temporary files removed"

echo ""
echo "================================================================"
echo "Deployment complete!"
echo "================================================================"
echo ""
echo "Function App URL: https://${FUNC_APP_NAME}.azurewebsites.net"
echo ""
echo "Timer triggers configured:"
echo "   - OrchestratorTimer: $ORCHESTRATOR_SCHEDULE"
echo "   - VideoGeneratorTimer: $VIDEO_SCHEDULE"
echo ""
echo "To check deployment status:"
echo "   az functionapp deployment list --resource-group $AZURE_RESOURCE_GROUP --name $FUNC_APP_NAME"
echo ""
echo "To view function logs:"
echo "   az functionapp log stream --resource-group $AZURE_RESOURCE_GROUP --name $FUNC_APP_NAME"
echo ""
