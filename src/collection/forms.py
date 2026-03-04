"""Formulários da aplicação Coleção."""

from django import forms

from .models import ItemColecao


class FormularioItemColecao(forms.ModelForm):
    """Formulário para adicionar ou editar um item na coleção."""

    class Meta:
        model = ItemColecao
        fields = ('quantidade_possuida', 'quantidade_repetidos', 'condicao', 'notas')
        widgets = {
            'notas': forms.Textarea(attrs={'rows': 2}),
        }

    def clean(self):
        cleaned_data = super().clean()
        possuida = cleaned_data.get('quantidade_possuida', 0)
        repetidos = cleaned_data.get('quantidade_repetidos', 0)
        if repetidos > possuida:
            raise forms.ValidationError(
                'Os repetidos não podem exceder a quantidade total possuída.'
            )
        return cleaned_data
