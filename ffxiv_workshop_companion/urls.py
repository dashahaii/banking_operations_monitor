"""
URL configuration for ffxiv_workshop_companion project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path
from ffxiv_workshop_companion.views import get_all_parts, calculate_items_for_manifest
# from projects.views import create_project, update_project, delete_project

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/ffxiv/get-all-parts/', get_all_parts, name='get_all_parts'),
    path('api/ffxiv/total-manifest/', calculate_items_for_manifest, name='calculate_items_for_manifest'),
]