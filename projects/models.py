# projects/models.py
from django.db import models
from django.contrib.postgres.fields import ArrayField
import uuid

class Project(models.Model):
    id = models.BigAutoField(primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)
    name = models.TextField()
    description = models.TextField(null=True, blank=True)
    organization = models.BigIntegerField()
    parts = ArrayField(models.BigIntegerField())
    manifest = models.BigIntegerField(unique=True)
    admins = ArrayField(models.BigIntegerField())
    members = ArrayField(models.BigIntegerField())
    avatar_url = models.TextField(null=True, blank=True)
    owner = models.BigIntegerField()
    
    class Meta:
        db_table = 'public.projects'
        managed = False
        
    def __str__(self):
        return self.name

class ProjectPart(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    components = models.JSONField()
    project = models.BigIntegerField()
    avatar_url = models.TextField(null=True, blank=True)
    
    class Meta:
        db_table = 'public.project_parts'
        managed = False
        
    def __str__(self):
        return str(self.id)

class ProjectManifest(models.Model):
    id = models.BigAutoField(primary_key=True)
    manifest_data = models.JSONField()
    project = models.BigIntegerField()
    
    class Meta:
        db_table = 'public.project_manifests'
        managed = False
        
    def __str__(self):
        return f"Manifest for project {self.project}"