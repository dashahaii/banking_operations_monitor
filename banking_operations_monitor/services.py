import csv
import json
import re
import time
import requests
import pandas as pd
import os
import glob
from collections import defaultdict
from django.conf import settings
import logging
from pymongo import MongoClient

# Configure logging
logger = logging.getLogger(__name__)

# MongoDB connection
MONGODB_HOST = getattr(settings, 'MONGODB_HOST', 'mongodb')
MONGODB_PORT = int(getattr(settings, 'MONGODB_PORT', 27017))
MONGODB_DATABASE = getattr(settings, 'MONGODB_DATABASE', 'banking_operations_monitor')
MONGODB_USERNAME = getattr(settings, 'MONGODB_USERNAME', '')
MONGODB_PASSWORD = getattr(settings, 'MONGODB_PASSWORD', '')

# Establish MongoDB connection
client = MongoClient(
    host=MONGODB_HOST,
    port=MONGODB_PORT,
    username=MONGODB_USERNAME or None,
    password=MONGODB_PASSWORD or None,
    authSource='admin' if MONGODB_USERNAME else None
)

# Get database
db = client[MONGODB_DATABASE]

# --- Helper Functions ---

def max_columns_in_csv(filepath):
    """Determine the maximum number of columns in a CSV file."""
    with open(filepath, newline='') as f:
        reader = csv.reader(f)
        return max(len(row) for row in reader)

def load_csv_with_max_columns(filepath):
    """Load a CSV file using the Python engine and ensure uniform column count."""
    max_fields = max_columns_in_csv(filepath)
    return pd.read_csv(
        filepath,
        header=None,
        engine='python',
        names=range(max_fields),
        on_bad_lines='skip'  # Skip lines with too many fields
    )

# Function to consolidate CSV contents
def consolidate_resource_reports(folder_path="operations/resource_data"):
    # Create an object to store item quantities
    resource_utilization = {}
    
    # Get all CSV files in the specified folder
    csv_files = glob.glob(os.path.join(folder_path, "*.csv"))
    
    if not csv_files:
        logger.warning(f"No CSV files found in {folder_path}")
        return None
    
    # Process each CSV file
    for file in csv_files:
        try:
            # Read the CSV file line by line
            with open(file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and ',' in line:
                        # Split the line into resource and utilization
                        parts = line.split(',', 1)
                        if len(parts) == 2:
                            resource = parts[0].strip()
                            try:
                                utilization = int(parts[1].strip())
                                # Add to our resource utilization dictionary
                                if resource in resource_utilization:
                                    resource_utilization[resource] += utilization
                                else:
                                    resource_utilization[resource] = utilization
                            except ValueError:
                                # Skip lines where utilization isn't a valid integer
                                continue
        except Exception as e:
            logger.error(f"Error reading file {file}: {str(e)}")
    
    # Convert to DataFrame and sort alphabetically by resource
    if resource_utilization:
        df = pd.DataFrame(
            [[resource, util] for resource, util in resource_utilization.items()],
            columns=['Resource', 'Utilization']
        ).sort_values('Resource').reset_index(drop=True)
        
        # Save to output.csv without headers
        output_path = 'operations/resource_output.csv'
        df.to_csv(output_path, index=False, header=False)
        logger.info(f"Consolidated resource data saved to {output_path}")
        
        # Store in MongoDB
        db.resource_utilization.delete_many({})  # Clear previous data
        db.resource_utilization.insert_many(df.to_dict('records'))
        logger.info("Resource utilization data stored in MongoDB")
        
        return df
    else:
        logger.warning("No valid data found in the resource files")
        return None



# --- Dependency Chain Analysis ---

def generate_dependency_chain(total_csv, dependency_book_csv, resource_location_csv, output_csv):
    """
    Generate the comprehensive list of base resources needed for all operations.
    
    - total_csv: path to total_services_dependencies.csv (top-level services)
    - dependency_book_csv: path to dependency_book.csv (service dependencies)
    - resource_location_csv: path to resource_location.csv (resource availability)
    - output_csv: file name to write the final resource requirements list.
    
    Returns the resulting DataFrame.
    """
    # Load CSV files
    df_total = load_csv_with_max_columns(total_csv)
    df_dependency_book = load_csv_with_max_columns(dependency_book_csv)
    df_resource_location = load_csv_with_max_columns(resource_location_csv)
    
    # Build dependency dictionary from dependency_book.csv
    max_fields_dependency_book = df_dependency_book.shape[1]
    dependencies = {}
    for _, row in df_dependency_book.iterrows():
        service = row[0]
        resources = []
        for i in range(1, max_fields_dependency_book, 2):
            if pd.isna(row[i]):
                break
            resource = row[i]
            if i + 1 < max_fields_dependency_book and not pd.isna(row[i+1]):
                qty = float(row[i+1])
            else:
                qty = 0
            resources.append((resource, qty))
        dependencies[service] = resources

    # Build top-level dictionary from total_services_dependencies.csv
    top_level = {}
    for _, row in df_total.iterrows():
        service = row[0]
        qty = float(row[1])
        top_level[service] = qty

    # Recursively compute base resource requirements
    requirements = defaultdict(float)
    def compute_requirements(service, multiplier):
        if service in dependencies:
            for resource, qty in dependencies[service]:
                compute_requirements(resource, qty * multiplier)
        else:
            requirements[service] += multiplier

    for service, qty in top_level.items():
        compute_requirements(service, qty)

    df_requirements = pd.DataFrame(list(requirements.items()), columns=["Resource", "Total Requirement"])

    # Process the resource_location.csv: combine location columns
    def combine_location(row):
        parts = [str(x) for x in row[1:] if pd.notna(x)]
        return ', '.join(parts)
    df_resource_location["Location Info"] = df_resource_location.apply(combine_location, axis=1)
    df_resource_location = df_resource_location[[0, "Location Info"]]
    df_resource_location.columns = ["Resource", "Location Info"]

    # Merge and sort the output
    df_output = pd.merge(df_requirements, df_resource_location, on="Resource", how="left")
    df_output = df_output.sort_values("Resource")
    
    # Save to CSV and MongoDB
    df_output.to_csv(output_csv, index=False)
    db.resource_dependencies.delete_many({})
    db.resource_dependencies.insert_many(df_output.to_dict('records'))
    logger.info(f"Dependency chain analysis saved to {output_csv} and MongoDB")
    
    return df_output

# --- Service List Generation ---

def get_service_list(total_csv):
    """
    Generate the list of managed services from total_services_dependencies.csv.
    
    Returns a DataFrame with the service list sorted alphabetically.
    """
    df_services = load_csv_with_max_columns(total_csv)
    df_services = df_services.sort_values(by=0)
    df_services.rename(columns={0: "Service", 1: "Required Resources"}, inplace=True)
    
    # Store in MongoDB
    db.services.delete_many({})
    db.services.insert_many(df_services.to_dict('records'))
    logger.info("Service list updated in MongoDB")
    
    return df_services

# --- Vendor API Integration ---

def fetch_vendor_pricing(resource_id, datacenter, pricing_columns):
    """
    Query vendor API for pricing data on a given resource.
    
    Returns a dictionary with pricing data (or None values on failure).
    """
    url = f"https://pricing.internal-api.bank/v2/pricing/{datacenter}/{resource_id}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if "results" in data and len(data["results"]) > 0:
                result = data["results"][0]
                return {
                    "list_price": result.get("standard", {}).get("listPrice", None),
                    "negotiated_price": result.get("standard", {}).get("ourPrice", None),
                    "recent_purchase": result.get("standard", {}).get("recentPurchase", None),
                    "recent_quote": result.get("standard", {}).get("recentQuote", None),
                    "average_market_price": result.get("standard", {}).get("marketAverage", None),
                    "monthly_usage": result.get("standard", {}).get("monthlyUsage", None),
                }
            else:
                logger.warning(f"No results found for resource ID {resource_id}")
        else:
            logger.error(f"Error fetching data for resource ID {resource_id}. Status code: {response.status_code}")
    except Exception as e:
        logger.error(f"Exception for resource ID {resource_id}: {e}")
    return {col: None for col in pricing_columns}

def fetch_pricing_for_all_resources(resources_csv, services_csv, resource_ids_json, output_csv, datacenter="PRIMARY"):
    """
    Combine items from the resources list and the services list, look up their IDs,
    query the vendor API for pricing data, and write the results to output_csv.
    """
    # Load the resources list
    df_resources = pd.read_csv(resources_csv).copy()
    df_resources = df_resources[["Resource"]].copy()
    df_resources.rename(columns={"Resource": "Item Name"}, inplace=True)
    df_resources["Category"] = "Resource"

    # Load the services list
    df_services = load_csv_with_max_columns(services_csv).copy()
    df_services = df_services[[0]].copy()
    df_services.rename(columns={0: "Item Name"}, inplace=True)
    df_services["Category"] = "Service"

    # Combine the two lists and remove duplicates
    df_combined = pd.concat([df_resources, df_services], ignore_index=True)
    df_combined = df_combined.drop_duplicates(subset=["Item Name"])

    # Load resource ID mapping from JSON
    with open(resource_ids_json, "r", encoding="utf-8") as f:
        resource_json = json.load(f)
    resource_mapping = {}
    for resource_id, names in resource_json.items():
        resource_name = names.get("name", "").strip().lower()
        if resource_name:
            resource_mapping[resource_name] = resource_id

    # Helper functions for cleaning names and looking up IDs
    def clean_item_name(name):
        return name.lower().strip()

    def get_resource_id(name):
        cleaned = clean_item_name(name)
        if cleaned in resource_mapping:
            return resource_mapping[cleaned]
        else:
            logger.error(f"Error: No ID found for resource '{name}' (cleaned as '{cleaned}').")
            return None

    df_combined["Item ID"] = df_combined["Item Name"].apply(get_resource_id)

    # Initialize pricing data columns
    pricing_columns = [
        "list_price", 
        "negotiated_price", 
        "recent_purchase", 
        "recent_quote", 
        "average_market_price", 
        "monthly_usage"
    ]
    for col in pricing_columns:
        df_combined[col] = None

    # Fetch pricing data for each item
    for idx, row in df_combined.iterrows():
        item_id = row["Item ID"]
        if item_id is not None:
            pricing_data = fetch_vendor_pricing(item_id, datacenter, pricing_columns)
            for key, value in pricing_data.items():
                df_combined.at[idx, key] = value
            time.sleep(0.5)  # Rate limiting
        else:
            logger.warning(f"Skipping pricing query for '{row['Item Name']}' due to missing ID.")

    # Save to CSV and MongoDB
    df_combined.to_csv(output_csv, index=False)
    db.resource_pricing.delete_many({})
    db.resource_pricing.insert_many(df_combined.to_dict('records'))
    logger.info(f"Resource pricing data saved to {output_csv} and MongoDB")
    
    return df_combined

# --- Prometheus Metrics Export ---

def export_prometheus_metrics():
    """Export metrics for Prometheus scraping"""
    # Get all resource utilization data
    resources = list(db.resource_utilization.find({}))
    
    # Create metrics output
    metrics = []
    
    # Resource utilization metrics
    for resource in resources:
        resource_name = resource.get('Resource', '').replace(' ', '_').lower()
        utilization = resource.get('Utilization', 0)
        metrics.append(f'bank_resource_utilization{{resource="{resource_name}"}} {utilization}')
    
    # Resource pricing metrics
    pricing_data = list(db.resource_pricing.find({}))
    for item in pricing_data:
        item_name = item.get('Item Name', '').replace(' ', '_').lower()
        category = item.get('Category', '')
        
        if item.get('negotiated_price'):
            metrics.append(f'bank_resource_price{{item="{item_name}",category="{category}"}} {item.get("negotiated_price")}')
        
        if item.get('monthly_usage'):
            metrics.append(f'bank_resource_monthly_usage{{item="{item_name}",category="{category}"}} {item.get("monthly_usage")}')
    
    # Write metrics to file for Prometheus to scrape
    metrics_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'prometheus_metrics', 'resource_metrics.prom')
    os.makedirs(os.path.dirname(metrics_path), exist_ok=True)
    
    with open(metrics_path, 'w') as f:
        f.write('\n'.join(metrics))
    
    logger.info(f"Prometheus metrics exported to {metrics_path}")
    return metrics