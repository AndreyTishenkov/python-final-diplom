from django import forms
from django.core.exceptions import ValidationError
from backend.models import User


class UserAdminForm(forms.ModelForm):
    """Кастомная форма для создания/редактирования пользователя в админке"""

    class Meta:
        model = User
        fields = '__all__'

    def clean_email(self):
        email = self.cleaned_data.get('email')

        # При создании нового пользователя
        if not self.instance.pk:
            if User.objects.filter(email=email).exists():
                raise ValidationError(
                    f'Пользователь с email "{email}" уже существует. '
                    f'Пожалуйста, используйте другой email или отредактируйте существующего пользователя.'
                )
        # При редактировании существующего
        else:
            if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
                raise ValidationError(
                    f'Пользователь с email "{email}" уже существует. '
                    f'Пожалуйста, используйте другой email.'
                )

        return email