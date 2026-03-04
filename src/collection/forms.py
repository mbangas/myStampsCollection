"""Formulários da aplicação Coleção."""

from django import forms

from .models import ItemColecao


class FormularioItemColecao(forms.ModelForm):
    """Formulário para adicionar ou editar um item na coleção."""

    class Meta:
        model = ItemColecao
        fields = (
            'quantidade_possuida',
            'quantidade_repetidos',
            'condicao',
            'notas',
            'localizacao',
            'variantes_possuidas',
        )
        widgets = {
            'quantidade_possuida': forms.NumberInput(
                attrs={'class': 'form-control form-control-sm', 'min': 1}
            ),
            'quantidade_repetidos': forms.NumberInput(
                attrs={'class': 'form-control form-control-sm', 'min': 0}
            ),
            'condicao': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'notas': forms.Textarea(
                attrs={
                    'class': 'form-control form-control-sm',
                    'rows': 2,
                    'placeholder': 'Notas pessoais sobre este selo…',
                }
            ),
            'localizacao': forms.TextInput(
                attrs={
                    'class': 'form-control form-control-sm',
                    'placeholder': 'Ex.: Álbum A, Caixa 3, Envelope azul…',
                }
            ),
            'variantes_possuidas': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, selo=None, **kwargs):
        """Filtra variantes pelo selo específico."""
        super().__init__(*args, **kwargs)
        if selo is not None:
            self.fields['variantes_possuidas'].queryset = selo.variantes.all()
            if not selo.variantes.exists():
                self.fields['variantes_possuidas'].widget = forms.HiddenInput()
        else:
            self.fields['variantes_possuidas'].widget = forms.HiddenInput()

    def clean(self):
        cleaned_data = super().clean()
        possuida = cleaned_data.get('quantidade_possuida', 0)
        repetidos = cleaned_data.get('quantidade_repetidos', 0)
        if repetidos > possuida:
            raise forms.ValidationError(
                'Os repetidos não podem exceder a quantidade total possuída.'
            )
        return cleaned_data


class FormularioLocalizacaoBulk(forms.Form):
    """Formulário para atualizar a localização de múltiplos itens da coleção."""

    localizacao = forms.CharField(
        max_length=100,
        label='Nova Localização',
        widget=forms.TextInput(
            attrs={'placeholder': 'Ex.: Álbum B, Gaveta 2…', 'class': 'form-control'}
        ),
    )
    itens = forms.CharField(widget=forms.HiddenInput())
