from django import forms

class SystemForm(forms.ModelForm):
	class Meta:
		model = System
		exclude = ('sist_oppdatert',)