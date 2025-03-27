import csv
import json
import re
import time
import requests
import pandas as pd
import os
import glob
from collections import defaultdict

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
def consolidate_csv_files(folder_path="workshop_utilities/item_data"):
    # Create an object to store item quantities
    item_quantities = {}
    
    # Get all CSV files in the specified folder
    csv_files = glob.glob(os.path.join(folder_path, "*.csv"))
    
    if not csv_files:
        print(f"No CSV files found in {folder_path}")
        return None
    
    # Process each CSV file
    for file in csv_files:
        try:
            # Read the CSV file line by line
            with open(file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and ',' in line:
                        # Split the line into item and quantity
                        parts = line.split(',', 1)
                        if len(parts) == 2:
                            item = parts[0].strip()
                            try:
                                quantity = int(parts[1].strip())
                                # Add to our item quantities dictionary
                                if item in item_quantities:
                                    item_quantities[item] += quantity
                                else:
                                    item_quantities[item] = quantity
                            except ValueError:
                                # Skip lines where quantity isn't a valid integer
                                continue
        except Exception as e:
            print(f"Error reading file {file}: {str(e)}")
    
    # Convert to DataFrame and sort alphabetically by item
    if item_quantities:
        df = pd.DataFrame(
            [[item, qty] for item, qty in item_quantities.items()],
            columns=['Item', 'Quantity']
        ).sort_values('Item').reset_index(drop=True)
        
        # Save to output.csv without headers
        output_path = 'workshop_utilities/workshop_output.csv'
        df.to_csv(output_path, index=False, header=False)
        print(f"Consolidated CSV saved to {output_path} (without headers)")
        
        return df
    else:
        print("No valid data found in the CSV files")
        return None



# --- Gathering List Generation ---

def generate_gathering_list(total_csv, recipe_book_csv, recipe_gathering_csv, output_csv):
    """
    Generate the comprehensive list of base ingredients needed (gathering list).
    
    - total_csv: path to total_shark_class_sub_parts.csv (top-level items)
    - recipe_book_csv: path to recipe_book.csv (crafting recipes)
    - recipe_gathering_csv: path to recipe_gathering.csv (gathering locations)
    - output_csv: file name to write the final gathering list.
    
    Returns the resulting DataFrame.
    """
    # Load CSV files
    df_total = load_csv_with_max_columns(total_csv)
    df_recipe_book = load_csv_with_max_columns(recipe_book_csv)
    df_recipe_gathering = load_csv_with_max_columns(recipe_gathering_csv)
    
    # Build recipe dictionary from recipe_book.csv
    max_fields_recipe_book = df_recipe_book.shape[1]
    recipes = {}
    for _, row in df_recipe_book.iterrows():
        product = row[0]
        ingredients = []
        for i in range(1, max_fields_recipe_book, 2):
            if pd.isna(row[i]):
                break
            ingredient = row[i]
            if i + 1 < max_fields_recipe_book and not pd.isna(row[i+1]):
                qty = float(row[i+1])
            else:
                qty = 0
            ingredients.append((ingredient, qty))
        recipes[product] = ingredients

    # Build top-level dictionary from total_shark_class_sub_parts.csv
    top_level = {}
    for _, row in df_total.iterrows():
        product = row[0]
        qty = float(row[1])
        top_level[product] = qty

    # Recursively compute base ingredient requirements.
    requirements = defaultdict(float)
    def compute_requirements(item, multiplier):
        if item in recipes:
            for ingredient, qty in recipes[item]:
                compute_requirements(ingredient, qty * multiplier)
        else:
            requirements[item] += multiplier

    for product, qty in top_level.items():
        compute_requirements(product, qty)

    df_requirements = pd.DataFrame(list(requirements.items()), columns=["Ingredient", "Total Quantity"])

    # Process the recipe_gathering.csv: combine location columns.
    def combine_location(row):
        parts = [str(x) for x in row[1:] if pd.notna(x)]
        return ', '.join(parts)
    df_recipe_gathering["Location Info"] = df_recipe_gathering.apply(combine_location, axis=1)
    df_recipe_gathering = df_recipe_gathering[[0, "Location Info"]]
    df_recipe_gathering.columns = ["Ingredient", "Location Info"]

    # Merge and sort the output.
    df_output = pd.merge(df_requirements, df_recipe_gathering, on="Ingredient", how="left")
    df_output = df_output.sort_values("Ingredient")
    df_output.to_csv(output_csv, index=False)
    return df_output

# --- Crafting Recipes List ---

def get_crafting_recipes(total_csv):
    """
    Generate the list of crafting recipes from total_shark_class_sub_parts.csv.
    
    Returns a DataFrame with the crafted product list sorted alphabetically.
    """
    df_crafting = load_csv_with_max_columns(total_csv)
    df_crafting = df_crafting.sort_values(by=0)
    df_crafting.rename(columns={0: "Product", 1: "Required Quantity"}, inplace=True)
    return df_crafting

# --- Market Data Fetching ---

def fetch_market_data(item_id, world, market_columns):
    """
    Query the Universalis API for market data on a given item.
    
    Returns a dictionary with market data (or None values on failure).
    """
    url = f"https://universalis.app/api/v2/aggregated/{world}/{item_id}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if "results" in data and len(data["results"]) > 0:
                result = data["results"][0]
                return {
                    "minListing_world": result.get("nq", {}).get("minListing", {}).get("world", {}).get("price"),
                    "minListing_dc": result.get("nq", {}).get("minListing", {}).get("dc", {}).get("price"),
                    "recentPurchase_world": result.get("nq", {}).get("recentPurchase", {}).get("world", {}).get("price"),
                    "recentPurchase_dc": result.get("nq", {}).get("recentPurchase", {}).get("dc", {}).get("price"),
                    "averageSalePrice_dc": result.get("nq", {}).get("averageSalePrice", {}).get("dc", {}).get("price"),
                    "dailySaleVelocity_dc": result.get("nq", {}).get("dailySaleVelocity", {}).get("dc", {}).get("quantity"),
                }
            else:
                print(f"No results found for item ID {item_id}")
        else:
            print(f"Error fetching data for item ID {item_id}. Status code: {response.status_code}")
    except Exception as e:
        print(f"Exception for item ID {item_id}: {e}")
    return {col: None for col in market_columns}

def fetch_market_data_for_subparts(gathering_csv, crafting_csv, item_ids_json, output_csv, world="Seraph"):
    """
    Combine items from the gathering list and the crafting recipes list, look up their IDs,
    query the Universalis API for market data, and write the results to output_csv.
    """
    # Load the gathering list.
    # Here we assume gathering_csv already has headers, so we use the default header.
    df_gathering = pd.read_csv(gathering_csv).copy()
    df_gathering = df_gathering[["Ingredient"]].copy()
    df_gathering.rename(columns={"Ingredient": "Item Name"}, inplace=True)
    df_gathering["Category"] = "Gathering"

    # Load the crafting recipes using the helper function to handle variable columns.
    df_crafting = load_csv_with_max_columns(crafting_csv).copy()
    # The first column in the crafting CSV (e.g., recipe_book.csv) is the crafted product.
    df_crafting = df_crafting[[0]].copy()
    df_crafting.rename(columns={0: "Item Name"}, inplace=True)
    df_crafting["Category"] = "Crafting"

    # Combine the two lists and remove duplicates.
    df_combined = pd.concat([df_gathering, df_crafting], ignore_index=True)
    df_combined = df_combined.drop_duplicates(subset=["Item Name"])

    # Load item ID mapping from JSON.
    with open(item_ids_json, "r", encoding="utf-8") as f:
        item_json = json.load(f)
    item_mapping = {}
    for item_id, names in item_json.items():
        en_name = names.get("en", "").strip().lower()
        if en_name:
            item_mapping[en_name] = item_id

    # Helper functions for cleaning names and looking up IDs.
    def clean_item_name(name):
        return name.lower().strip()

    def get_item_id(name):
        cleaned = clean_item_name(name)
        if cleaned in item_mapping:
            return item_mapping[cleaned]
        else:
            print(f"Error: No ID found for item '{name}' (cleaned as '{cleaned}').")
            return None

    df_combined["Item ID"] = df_combined["Item Name"].apply(get_item_id)

    # Initialize market data columns.
    market_columns = [
        "minListing_world", 
        "minListing_dc", 
        "recentPurchase_world", 
        "recentPurchase_dc", 
        "averageSalePrice_dc", 
        "dailySaleVelocity_dc"
    ]
    for col in market_columns:
        df_combined[col] = None

    # Fetch market data for each item.
    for idx, row in df_combined.iterrows():
        item_id = row["Item ID"]
        if item_id is not None:
            market_data = fetch_market_data(item_id, world, market_columns)
            for key, value in market_data.items():
                df_combined.at[idx, key] = value
            time.sleep(0.5)
        else:
            print(f"Skipping market query for '{row['Item Name']}' due to missing ID.")

    df_combined.to_csv(output_csv, index=False)
    return df_combined