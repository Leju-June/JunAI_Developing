from django.contrib import admin

# Register your models here.
from catalog.models import ToolList, AnalysisModel

@admin.register(ToolList)
class ToolListAdmin(admin.ModelAdmin):
	pass
@admin.register(AnalysisModel)
class AnalysisModel(admin.ModelAdmin):
	pass