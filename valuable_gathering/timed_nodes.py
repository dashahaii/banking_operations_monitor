# setup file for timed_nodes.py
from datetime import datetime, timedelta
import re
import csv
import pandas as pd
import json
import time
import requests

def clean_unspoiled_data(input_filename, output_filename):
    # Read the entire file as a string
    with open(input_filename, 'r', encoding='utf-8') as f:
        data = f.read()
    
    lines = data.split('\n')

    # We’ll store rows of [Time, Item Name, Location, Coordinates].
    rows = []

    for line in lines:
        line = line.strip()

        # We're looking for lines in the format:
        # |Time || {{item icon|Item Name}} || Slot || [[Location]] || (x..,y..) ...
        if not line.startswith('|'):
            continue
        
        # Split on '||'
        parts = [p.strip() for p in line.split('||')]
        if len(parts) < 5:
            continue

        # Extract the fields we care about:
        # parts[0] -> time  (remove leading '|')
        # parts[1] -> item
        # parts[3] -> location
        # parts[4] -> coordinate
        time = parts[0].lstrip('|').strip()
        item = parts[1]
        location = parts[3]
        coordinate = parts[4]

        # Combine entire line to detect questlink if needed
        entire_line = ' '.join(parts)

        # Skip if 'questlink' is in the line
        if re.search(r'questlink', entire_line, re.IGNORECASE):
            continue

        # Clean up the item name:
        # e.g., {{item icon|Broad Beans}} => Broad Beans
        item_clean = re.sub(r'\{\{.*?\|([^\}]+)\}\}', r'\1', item)
        # Remove leftover braces, "Collectable", "(Item)" text, etc.
        item_clean = re.sub(r'[{}]|\(Item\)|Collectable', '', item_clean).strip()

        # Skip if the item name has the word "cluster" (case-insensitive)
        if re.search(r'cluster', item_clean, re.IGNORECASE):
            continue

        # Clean up location, e.g. [[Il Mheg]] => Il Mheg
        location_clean = re.sub(r'\[\[|\]\]', '', location).strip()

        # Add the row
        rows.append([time, item_clean, location_clean, coordinate])

    # Write results to a CSV
    with open(output_filename, 'w', encoding='utf-8', newline='') as out_csv:
        writer = csv.writer(out_csv)
        writer.writerow(["Time", "Item Name", "Location", "Coordinates"])
        writer.writerows(rows)

def assign_ids(input_filename, output_filename):
    # Load the JSON file with item IDs.
    with open("item_ids.json", "r", encoding="utf-8") as f:
        item_json = json.load(f)

    # Build a mapping: lower-case English item name -> item ID
    item_mapping = {}
    for item_id, names in item_json.items():
        en_name = names.get("en", "").strip().lower()
        item_mapping[en_name] = item_id

    # Read in the cleaned nodes CSV.
    nodes_df = pd.read_csv(input_filename)

    # Function to clean item names for matching:
    # Remove occurrences of "(Rare)" (case-insensitive), then lower-case and strip.
    def clean_item_name(name):
        # Remove the substring (Rare) along with any extra spaces
        name_clean = re.sub(r'\s*\(rare\)', '', name, flags=re.IGNORECASE)
        return name_clean.strip().lower()
        
    nodes_df["Item Name Clean"] = nodes_df["Item Name"].apply(clean_item_name)

    # Function to look up the item ID using the cleaned item name.
    def get_item_id(row):
        name = row["Item Name Clean"]
        if name in item_mapping:
            return item_mapping[name]
        else:
            print(f"Error: No ID found for item '{row['Item Name']}' (cleaned as '{name}').")
            return None
        
    # Apply the lookup function to each row.
    nodes_df["ID"] = nodes_df.apply(get_item_id, axis=1)

    # Reorder columns to prepend the ID.
    final_df = nodes_df[["ID", "Time", "Item Name", "Location", "Coordinates"]]

    # Write the final merged CSV.
    final_df.to_csv(output_filename, index=False)
    print("Merged CSV written to 'final_nodes_with_ids.csv'.")

def sort_for_current_time(input_filename, output_filename):
    # -----------------------
    # 1. Compute current Eorzean time in 24-hour format
    # -----------------------
    local_epoch = int(time.time() * 1000)
    epoch = local_epoch * 20.571428571428573
    minutes = int((epoch / (1000 * 60)) % 60)
    hours_24 = int((epoch / (1000 * 60 * 60)) % 24)
    et_time_str = f"{hours_24:02d}:{minutes:02d}"
    print("Current Eorzean time (raw):", et_time_str)
    current_time = datetime.strptime(et_time_str, "%H:%M")

    # -----------------------
    # 2. Load final_nodes_with_ids.csv and duplicate ambiguous AM/PM entries
    # -----------------------
    df = pd.read_csv(input_filename)

    new_rows = []

    def standard_parse_time(time_str):
        # If the string contains "AM" or "PM" (but not ambiguous "AM/PM"), parse using 12-hour clock.
        if re.search(r'\b(AM|PM)\b', time_str, re.IGNORECASE) and "AM/PM" not in time_str.upper():
            time_str_fixed = re.sub(r'(\d)(AM|PM)', r'\1 \2', time_str, flags=re.IGNORECASE)
            return datetime.strptime(time_str_fixed, "%I:%M %p")
        else:
            # Otherwise, assume it’s already in 24-hour format.
            return datetime.strptime(time_str, "%H:%M")

    for idx, row in df.iterrows():
        time_str = row["Time"].strip()
        # If the time is ambiguous (contains "AM/PM"), duplicate the row.
        if "AM/PM" in time_str.upper():
            base_time_str = re.sub(r'\s*AM/PM', '', time_str, flags=re.IGNORECASE).strip()
            base_time = datetime.strptime(base_time_str, "%H:%M")
            # Create two interpretations:
            # AM version: keep the base time as-is (special handling for 12:00).
            # PM version: add 12 hours (unless base time is 12:00).
            if base_time.hour == 12:
                am_time = base_time.replace(hour=0)
                pm_time = base_time
            else:
                am_time = base_time
                pm_time = base_time + timedelta(hours=12)
            
            row_am = row.copy()
            row_am["Parsed Time"] = am_time
            row_am["Time"] = am_time.strftime("%H:%M")
            new_rows.append(row_am)
            
            row_pm = row.copy()
            row_pm["Parsed Time"] = pm_time
            row_pm["Time"] = pm_time.strftime("%H:%M")
            new_rows.append(row_pm)
        else:
            parsed = standard_parse_time(time_str)
            row_new = row.copy()
            row_new["Parsed Time"] = parsed
            row_new["Time"] = parsed.strftime("%H:%M")
            new_rows.append(row_new)

    df_new = pd.DataFrame(new_rows)

    # -----------------------
    # 3. Compute the time difference (in minutes) between each node’s spawn time and the current time.
    #    (The difference is computed on a circular 24-hour scale, ranging from -720 to 720.)
    def compute_time_diff_minutes(node_time, current_time):
        node_minutes = node_time.hour * 60 + node_time.minute
        current_minutes = current_time.hour * 60 + current_time.minute
        diff = ((node_minutes - current_minutes + 720) % 1440) - 720
        return diff

    df_new["time_diff"] = df_new["Parsed Time"].apply(lambda t: compute_time_diff_minutes(t, current_time))

    # -----------------------
    # 4. Filter nodes that are active (spawned up to 50 minutes ago or later).
    #    (No upper bound is set; we simply require time_diff >= -50.)
    active_df = df_new[df_new["time_diff"] >= -50]
    active_sorted = active_df.sort_values(by="time_diff")
    df_active_top10 = active_sorted.head(14)

    print("\nActive nodes (with time difference in minutes):")
    print(df_active_top10[["ID", "Time", "Item Name", "Location", "Coordinates", "time_diff"]])

    # Save the active nodes to a CSV file.
    df_active_top10.to_csv(output_filename, index=False)



def generate_market_data(input_filename, output_filename):
    # -----------------------
    # 1. Read the active nodes CSV and filter out any rows with "Rarefied" in the Item Name.
    # -----------------------
    df_sorted = pd.read_csv(input_filename)
    df_filtered = df_sorted[~df_sorted["Item Name"].str.contains("Rarefied", case=False, na=False)]
    df_top10 = df_filtered.head(14).copy()

    # Define new column names for the market data we want to add.
    market_columns = [
        "minListing_world", 
        "minListing_dc", 
        "recentPurchase_world", 
        "recentPurchase_dc", 
        "averageSalePrice_dc", 
        "dailySaleVelocity_dc"
    ]

    # Initialize the new columns with None.
    for col in market_columns:
        df_top10[col] = None

    # -----------------------
    # 2. Set default world and define a function to fetch market data.
    # -----------------------
    world = "Seraph"

    def fetch_market_data(item_id, world):
        url = f"https://universalis.app/api/v2/aggregated/{world}/{item_id}"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                if "results" in data and len(data["results"]) > 0:
                    result = data["results"][0]
                    # Extract the required market values.
                    minListing_world = result.get("nq", {}).get("minListing", {}).get("world", {}).get("price")
                    minListing_dc = result.get("nq", {}).get("minListing", {}).get("dc", {}).get("price")
                    recentPurchase_world = result.get("nq", {}).get("recentPurchase", {}).get("world", {}).get("price")
                    recentPurchase_dc = result.get("nq", {}).get("recentPurchase", {}).get("dc", {}).get("price")
                    averageSalePrice_dc = result.get("nq", {}).get("averageSalePrice", {}).get("dc", {}).get("price")
                    dailySaleVelocity_dc = result.get("nq", {}).get("dailySaleVelocity", {}).get("dc", {}).get("quantity")
                    return {
                        "minListing_world": minListing_world,
                        "minListing_dc": minListing_dc,
                        "recentPurchase_world": recentPurchase_world,
                        "recentPurchase_dc": recentPurchase_dc,
                        "averageSalePrice_dc": averageSalePrice_dc,
                        "dailySaleVelocity_dc": dailySaleVelocity_dc,
                    }
                else:
                    print(f"No results found for item ID {item_id}")
            else:
                print(f"Error fetching data for item ID {item_id}. Status code: {response.status_code}")
        except Exception as e:
            print(f"Exception for item ID {item_id}: {e}")
        # Return a dict with None values if something went wrong.
        return {col: None for col in market_columns}

    # -----------------------
    # 3. Loop through the filtered top 10 rows, fetch market data for each item, and update the DataFrame.
    # -----------------------
    for idx, row in df_top10.iterrows():
        item_id = row["ID"]
        market_data = fetch_market_data(item_id, world)
        for key, value in market_data.items():
            df_top10.at[idx, key] = value

    # -----------------------
    # 4. Save the augmented DataFrame to a new CSV file and display it.
    # -----------------------
    df_top10.to_csv(output_filename, index=False)
    print("CSV file with market data saved as 'final_nodes_with_ids_market.csv'.")