from django.test.runner import DiscoverRunner

class NoDBTestRunner(DiscoverRunner):
    def setup_databases(self, **kwargs):
        """Override to not create a test database"""
        return {}
        
    def teardown_databases(self, old_config, **kwargs):
        """Override to not destroy a test database"""
        pass