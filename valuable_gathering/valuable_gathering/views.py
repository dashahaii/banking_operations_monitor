from django.http import HttpResponse
from django.conf import settings
import os
from . import timed_nodes

def index(request):
    base_dir = settings.BASE_DIR

    input_file = os.path.join(base_dir, "unspoiled_nodes.txt")
    cleaned_file = os.path.join(base_dir, "cleaned_data.csv")
    final_file = os.path.join(base_dir, "final_nodes_with_ids.csv")
    sorted_file = os.path.join(base_dir, "final_nodes_with_ids_sorted.csv")
    market_file = os.path.join(base_dir, "final_nodes_with_ids_market.csv")

    timed_nodes.clean_unspoiled_data(input_file, cleaned_file)
    timed_nodes.assign_ids(cleaned_file, final_file)
    timed_nodes.sort_for_current_time(final_file, sorted_file)
    timed_nodes.generate_market_data(sorted_file, market_file)

    return HttpResponse("All functions executed in sequence. Check the generated output files.")
