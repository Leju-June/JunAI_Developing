from django.db import models
from django.urls import reverse

# Create your models here.
class ToolList(models.Model):
	name = models.CharField(max_length=200)
	analysismodels = models.ForeignKey('AnalysisModel', on_delete=models.SET_NULL, null=True)

	def __str__(self):
		return self.name
	
	def get_absolute_url(self):
		return reverse('tool-detail', args=[str(self.pk)])

class AnalysisModel(models.Model):
	name = models.CharField(max_length=200)
	description = models.TextField(max_length=1000, help_text='Enter a brief description of the model')

	def __str__(self):
		return self.name