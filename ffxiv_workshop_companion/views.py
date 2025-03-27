from django.shortcuts import render
from django.conf import settings
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import csv
from workshop_projects import consolidate_csv_files
from workshop_projects import generate_gathering_list

def index(request):
    table_data = []
    consolidated_data = consolidate_csv_files()
    utils_dir = 'workshop_utilities/'
    if consolidated_data is not None:
        generate_gathering_list(
            total_csv=os.path.join(utils_dir, 'workshop_output.csv'),
            recipe_book_csv=os.path.join(utils_dir, 'recipe_book.csv'),
            recipe_gathering_csv=os.path.join(utils_dir, 'recipe_gathering.csv'),
            output_csv=os.path.join(utils_dir, 'gathering_list.csv')
        )
        
    # Read the output CSV into a list of dictionaries
    gathering_output = os.path.join(utils_dir, 'gathering_list.csv')
    with open(gathering_output, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            table_data.append(row)
    
    # Render the data in the template
    return render(request, "index.html", {"table_data": table_data})
