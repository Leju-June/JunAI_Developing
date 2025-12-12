from django import forms

class LDAUploadForm(forms.Form):
    csv_file = forms.FileField(label="토큰 CSV 업로드(.csv)")
    
    extra_instruction = forms.CharField(
        label="추가 지시(선택)",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "예) 업데이트 관련 단어를 더 강조해줘"})
    )
