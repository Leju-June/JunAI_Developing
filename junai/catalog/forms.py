from django import forms

class AskForm(forms.Form):
    question = forms.CharField(
        label="질문",
        widget=forms.Textarea(attrs={
            "rows": 4, "placeholder": "여기에 질문을 입력하세요..."
        })
    )
