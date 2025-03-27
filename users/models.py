# users/models.py
from django.db import models
from django.contrib.postgres.fields import ArrayField

class Profile(models.Model):
    id = models.BigAutoField(primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)
    username = models.TextField(unique=True)
    ffxiv_name = models.TextField(null=True, blank=True)
    organizations = ArrayField(models.BigIntegerField(), null=True, blank=True)
    projects = ArrayField(models.BigIntegerField(), null=True, blank=True)
    avatar_url = models.BigIntegerField(null=True, blank=True)
    
    class Meta:
        db_table = 'public.profiles'  # name of the Supabase table
        managed = False  # Django won't try to create or alter this table
        
    def __str__(self):
        return self.username