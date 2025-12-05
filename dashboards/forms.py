from django import forms 
 
class DashboardForm(forms.Form): 
    title = forms.CharField(max_length=100) 
