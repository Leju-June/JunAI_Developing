from django.urls import path
from catalog import views


urlpatterns = [
	path('', views.index, name='index'),
	path('tools/', views.ToolListView.as_view(), name='tools'),
	path('tool/<int:pk>/', views.ToolDetailView.as_view(), name='tool-detail'),
]