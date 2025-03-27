# organizations/models.py
from django.db import models
from django.contrib.postgres.fields import ArrayField

class Organization(models.Model):
    id = models.BigAutoField(primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)
    name = models.TextField()
    members = ArrayField(models.BigIntegerField(), null=True, blank=True)
    projects = ArrayField(models.BigIntegerField(), null=True, blank=True)
    admins = ArrayField(models.BigIntegerField(), null=True, blank=True)
    owner = models.BigIntegerField()
    avatar_url = models.TextField(null=True, blank=True)
    
    class Meta:
        db_table = 'public.organizations'  # the name of the Supabase table
        managed = False  # Django won't try to create or alter this table
        
    def __str__(self):
        return self.name