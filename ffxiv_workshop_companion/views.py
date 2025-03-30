from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from ffxiv_workshop_companion.services import consolidate_csv_files, generate_gathering_list
import json
import os
import pandas as pd
import re
import tempfile
from collections import defaultdict
import csv

def get_all_parts(request):
    """
    Returns a JSON response containing a list of parts in "item_data".
    """
    item_data_path = os.path.join(settings.BASE_DIR, 'workshop_utilities', 'item_data')
    parts = []

    if os.path.exists(item_data_path):
        for filename in os.listdir(item_data_path):
            if filename.endswith('.csv') and 'total_' not in filename:
                part_name = filename.replace('_parts.csv', '')

                parts.append({
                    'id': part_name,
                    'name': format_part_name(part_name),
                    'file': filename
                })
    
    parts.sort(key=lambda x: x['name'])
    return JsonResponse({'parts': parts})

def format_part_name(part_name):
    """
    Returns part name with display-friendly format.
    """
    formatted_name = part_name.replace('_', ' ')
    formatted_name = ' '.join(word.capitalize() for word in formatted_name.split())
    formatted_name = re.sub(r'\bIi\b', 'II', formatted_name)
    return formatted_name

@csrf_exempt
@require_http_methods(["POST"])
def calculate_items_for_manifest(request):
    """
    Calculates all items needed (both for gathering and crafting) based on selected parts.
    """
    try:
        # Parse JSON data from request
        data = json.loads(request.body)
        parts_data = data.get('parts', [])
        
        # Extract just the part IDs from the objects
        selected_parts = []
        for part_obj in parts_data:
            if isinstance(part_obj, dict) and 'id' in part_obj:
                selected_parts.append(part_obj['id'])
        
        if not selected_parts:
            return JsonResponse({
                'status': 'error',
                'message': 'No valid parts selected'
            }, status=400)
        
        # Get the base path for item data
        item_data_path = os.path.join(settings.BASE_DIR, 'workshop_utilities', 'item_data')
        
        # Create a list of file paths for the selected parts
        part_files = []
        for part_id in selected_parts:
            file_path = os.path.join(item_data_path, f"{part_id}_parts.csv")
            if os.path.exists(file_path):
                part_files.append(file_path)
            else:
                print(f"File not found: {file_path}")
        
        if not part_files:
            return JsonResponse({
                'status': 'error',
                'message': 'No valid part files found'
            }, status=400)
        
        # create temporary directory for consolidation
        with tempfile.TemporaryDirectory() as temp_dir:
            # Copy all the part files to a temporary directory
            import shutil
            temp_data_dir = os.path.join(temp_dir, 'item_data')
            os.makedirs(temp_data_dir, exist_ok=True)
            
            for file in part_files:
                filename = os.path.basename(file)
                shutil.copy(file, os.path.join(temp_data_dir, filename))
            
            # Now pass the directory to consolidate_csv_files
            consolidated_df = consolidate_csv_files(temp_data_dir)
            
            # Create a temporary file for the consolidated data
            temp_total_csv = os.path.join(temp_dir, 'temp_total.csv')
            consolidated_df.to_csv(temp_total_csv, index=False, header=False)

            recipe_book_csv = os.path.join(settings.BASE_DIR, 'workshop_utilities', 'recipe_book.csv')
            recipe_gathering_csv = os.path.join(settings.BASE_DIR, 'workshop_utilities', 'recipe_gathering.csv')
            
            # generate gathering list
            gathering_output_csv = os.path.join(temp_dir, 'gathering_list.csv')
            gathering_df = generate_gathering_list(
                temp_total_csv,
                recipe_book_csv,
                recipe_gathering_csv,
                gathering_output_csv,
            )

            all_items = []
            for _, row in gathering_df.iterrows():
                all_items.append({
                    'name': row['Ingredient'],
                    'quantity': float(row['Total Quantity']),
                    'type': 'Gatherer\'s',
                    'location': row['Location Info'] if not pd.isna(row['Location Info']) else ''
                })

            for _, row in consolidated_df.iterrows():
                all_items.append({
                    'name': row['Item'],
                    'quantity': int(row['Quantity']),
                    'type': 'Crafter\'s'
                })
            
        return JsonResponse({
            'status': 'success',
            'items': all_items
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)