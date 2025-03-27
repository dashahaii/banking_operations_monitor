# organizations/tests.py
from django.test import SimpleTestCase
import os

class OrganizationConnectionTest(SimpleTestCase):
    # Add this line to allow database access
    databases = {'default'}
    
    def test_organization_connection(self):
        # Skip test if not explicitly enabled
        if not os.environ.get('RUN_LIVE_DB_TESTS'):
            self.skipTest("Skipping live database tests")
            
        try:
            # Use raw SQL instead of ORM to test connection
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM public.organizations")
                result = cursor.fetchone()
                print(f"Found {result[0]} organizations in the database")
                
                # If there are organizations, fetch one to verify structure
                if result[0] > 0:
                    cursor.execute("SELECT name FROM public.organizations LIMIT 1")
                    org = cursor.fetchone()
                    print(f"Sample organization name: {org[0]}")
                
                # We're just testing if the connection works
                self.assertTrue(True)
        except Exception as e:
            self.fail(f"Failed to connect to Organizations table: {e}")