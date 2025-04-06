#!/bin/bash

# Colors for better readability
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to run a command and wait for user confirmation
run_test() {
    local description=$1
    local command=$2
    
    echo -e "\n${YELLOW}============================================================${NC}"
    echo -e "${BLUE}TEST: ${description}${NC}"
    echo -e "${YELLOW}============================================================${NC}"
    echo -e "Command: ${command}\n"
    
    read -p "Press Y to run this test, or any other key to skip: " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${GREEN}Running...${NC}\n"
        eval $command
        echo -e "\n${GREEN}Test completed.${NC}"
    else
        echo -e "${YELLOW}Test skipped.${NC}"
    fi
    
    echo -e "\n${YELLOW}------------------------------------------------------------${NC}"
    read -p "Press any key to continue to the next test..." -n 1 -r
    echo
}

# Set the base URL
BASE_URL="http://localhost:8000"

echo -e "${GREEN}Banking IT Operations Resource Management Demo Script${NC}"
echo -e "${GREEN}=====================================================${NC}\n"
echo "This script will walk you through various API endpoints to demonstrate the functionality."
echo "Press Y to run each test or any other key to skip it."
echo "Press Ctrl+C at any time to exit the script."
echo

# 1. Basic API Exploration
run_test "Check health endpoint" "curl -s ${BASE_URL}/health/"

run_test "Check API root to see available endpoints" "curl -s ${BASE_URL}/api/v1/ | json_pp"

# 2. Import Sample Data
run_test "Import resources from CSV" "curl -X POST ${BASE_URL}/api/v1/resources/import \
  -F \"file=@data/resource_data/resource_inventory.csv\" | json_pp"

run_test "Import services and dependencies" "curl -X POST ${BASE_URL}/api/v1/services/import \
  -F \"file=@data/service_dependencies.csv\" | json_pp"

# 3. Resource Management
run_test "List all resources" "curl -s ${BASE_URL}/api/v1/resources/ | json_pp"

run_test "Filter resources by COMPUTE category" "curl -s ${BASE_URL}/api/v1/resources/?category=COMPUTE | json_pp"

run_test "Filter resources by STORAGE category" "curl -s ${BASE_URL}/api/v1/resources/?category=STORAGE | json_pp"

# Find a valid resource ID first
echo "Finding a valid resource ID to use for detailed view..."
RESOURCE_ID=$(curl -s ${BASE_URL}/api/v1/resources/ | grep -o '\"id\":[0-9]*' | head -1 | cut -d':' -f2)
if [ -z "$RESOURCE_ID" ]; then
    RESOURCE_ID=1
    echo "Could not find a resource ID, using default ID: ${RESOURCE_ID}"
else
    echo "Found resource ID: ${RESOURCE_ID}"
fi

run_test "View details of a specific resource" "curl -s ${BASE_URL}/api/v1/resources/${RESOURCE_ID}/ | json_pp"

# 4. Service Management
run_test "List all services" "curl -s ${BASE_URL}/api/v1/services/ | json_pp"

run_test "Filter services by CRITICAL criticality" "curl -s ${BASE_URL}/api/v1/services/?criticality=CRITICAL | json_pp"

# Find a valid service ID
echo "Finding a valid service ID to use for detailed view..."
SERVICE_ID=$(curl -s ${BASE_URL}/api/v1/services/ | grep -o '\"id\":[0-9]*' | head -1 | cut -d':' -f2)
if [ -z "$SERVICE_ID" ]; then
    SERVICE_ID=1
    echo "Could not find a service ID, using default ID: ${SERVICE_ID}"
else
    echo "Found service ID: ${SERVICE_ID}"
fi

run_test "View details of a specific service" "curl -s ${BASE_URL}/api/v1/services/${SERVICE_ID}/ | json_pp"

# 5. Analysis Operations
run_test "Process resource reports" "curl -X POST -s ${BASE_URL}/api/v1/resources/process-reports/ | json_pp"

run_test "Analyze service dependencies" "curl -X POST -s ${BASE_URL}/api/v1/services/analyze-dependencies/ | json_pp"

run_test "Update pricing information" "curl -X POST -s ${BASE_URL}/api/v1/pricing/update/ | json_pp"

# 6. Cost Analysis
run_test "List pricing information" "curl -s ${BASE_URL}/api/v1/pricing/ | json_pp"

run_test "Get cost analysis for a specific service" "curl -s ${BASE_URL}/api/v1/services/${SERVICE_ID}/cost-analysis/ | json_pp"

# 7. Metrics and Monitoring
run_test "Export metrics for Prometheus" "curl -s ${BASE_URL}/api/v1/metrics/export/ | json_pp"

run_test "View metrics directly" "curl -s ${BASE_URL}/metrics/"

run_test "List active alerts" "curl -s ${BASE_URL}/api/v1/alerts/ | json_pp"

# 8. Web Interface Information
echo -e "\n${YELLOW}============================================================${NC}"
echo -e "${BLUE}WEB INTERFACES AVAILABLE:${NC}"
echo -e "${YELLOW}============================================================${NC}"
echo -e "${GREEN}API Documentation:${NC} ${BASE_URL}/api/docs/"
echo -e "${GREEN}Django Admin:${NC} ${BASE_URL}/admin/"
echo -e "${GREEN}Grafana Dashboards:${NC} http://localhost:3000 (login with admin/admin)"
echo -e "${GREEN}Prometheus UI:${NC} http://localhost:9090"

echo -e "\n${GREEN}Demo script completed!${NC}"
echo "You have successfully explored the Banking IT Operations Resource Management System."