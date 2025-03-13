import csv
import os
import tempfile
from unittest.mock import patch, Mock

from django.test import TestCase, Client
from django.urls import reverse

from valuable_gathering import timed_nodes


class IndexViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    @patch('valuable_gathering.timed_nodes.requests.get')
    def test_index_view_with_universalis_api(self, mock_get):
        """
        The test simulates a GET request to the index view. We patch `requests.get` with a mock object that returns a
        to simulate a valid response.
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [{
                "nq": {
                    "minListing": {
                        "world": {"price": 100},
                        "dc": {"price": 90}
                    },
                    "recentPurchase": {
                        "world": {"price": 95},
                        "dc": {"price": 91}
                    },
                    "averageSalePrice": {
                        "dc": {"price": 91}
                    },
                    "dailySaleVelocity": {
                        "dc": {"quantity": 5}
                    },
                }
            }]
        }
        mock_get.return_value = mock_response
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        mock_get.assert_called()

    @patch('valuable_gathering.timed_nodes.requests.get')
    def test_generate_market_data_api_call(self, mock_get):
        """
        This is a unit test of the market data function.
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [{
                "nq": {
                    "minListing": {
                        "world": {"price": 100},
                        "dc": {"price": 90}
                    },
                    "recentPurchase": {
                        "world": {"price": 95},
                        "dc": {"price": 91}
                    },
                    "averageSalePrice": {
                        "dc": {"price": 91}
                    },
                    "dailySaleVelocity": {
                        "dc": {"quantity": 5}
                    },
                }
            }]
        }  
        mock_get.return_value = mock_response
        temp_input = tempfile.NamedTemporaryFile(mode='w+', 
                                                 delete=False, 
                                                 newline='', 
                                                 suffix='.csv'
                                                 )
        writer = csv.writer(temp_input)
        writer.writerow(["ID", "Time", "Item Name", "Location", "Coordinates"])
        writer.writerow(["123", "12:00", "Test Item", "Test Location", "(0,0)"])
        temp_input.close()

        temp_output = tempfile.NamedTemporaryFile(mode='w+', 
                                                  delete=False, 
                                                  newline='', 
                                                  suffix='.csv'
                                                  )
        temp_output.close()

        # Call the function that fetches market data.
        timed_nodes.generate_market_data(temp_input.name, temp_output.name)

        # Read the output CSV and verify the market data columns are populated with numeric values.
        with open(temp_output.name, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            self.assertEqual(len(rows), 1)
            row = rows[0]
            market_columns = [
                "minListing_world", 
                "minListing_dc", 
                "recentPurchase_world", 
                "recentPurchase_dc", 
                "averageSalePrice_dc", 
                "dailySaleVelocity_dc"
            ]
            for col in market_columns:
                # Check that a value exists.
                self.assertTrue(row[col], f"{col} should not be empty")
                # Verify that the value is numeric (int or float).
                try:
                    float(row[col])
                except ValueError:
                    self.fail(f"{col} should be numeric, got {row[col]}")

        # Clean up temporary files.
        os.remove(temp_input.name)
        os.remove(temp_output.name)