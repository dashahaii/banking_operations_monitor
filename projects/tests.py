# projects/tests.py
from django.test import SimpleTestCase
import os

class ProjectsConnectionTest(SimpleTestCase):
    # Add this line to allow database access
    databases = {'default'}
    
    def test_project_tables_connection(self):
        # Skip test if not explicitly enabled
        if not os.environ.get('RUN_LIVE_DB_TESTS'):
            self.skipTest("Skipping live database tests")
            
        try:
            # Use raw SQL instead of ORM to test connection
            from django.db import connection
            with connection.cursor() as cursor:
                # Test Projects table
                cursor.execute("SELECT COUNT(*) FROM public.projects")
                project_count = cursor.fetchone()[0]
                print(f"Found {project_count} projects in the database")
                
                # Test Project Parts table
                cursor.execute("SELECT COUNT(*) FROM public.project_parts")
                parts_count = cursor.fetchone()[0]
                print(f"Found {parts_count} project parts in the database")
                
                # Test Project Manifests table
                cursor.execute("SELECT COUNT(*) FROM public.project_manifests")
                manifest_count = cursor.fetchone()[0]
                print(f"Found {manifest_count} project manifests in the database")
                
                # If there are projects, fetch one to verify structure
                if project_count > 0:
                    cursor.execute("SELECT name FROM public.projects LIMIT 1")
                    project = cursor.fetchone()
                    print(f"Sample project name: {project[0]}")
                
                # We're just testing if the connection works
                self.assertTrue(True)
        except Exception as e:
            self.fail(f"Failed to connect to Project tables: {e}")