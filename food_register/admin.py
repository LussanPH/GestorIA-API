from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Categorias, Usuarios


@admin.register(Usuarios)
class CustomUserAdmin(UserAdmin):
    ordering = ('email',)

    list_display = ('email', 'nome_completo', 'is_staff')

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Informações Pessoais', {'fields': ('nome_completo',)}),
        ('Permissões', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Datas Importantes', {'fields': ('last_login', 'date_joined')})
    )

    add_fieldsets = (
        (None, {
            'classes':('wide',),
            'fields':('email', 'nome_completo', 'password1', 'password2'),
        }),
    )


@admin.register(Categorias)
class CategoriasAdmin(admin.ModelAdmin):
    list_display = ('id', 'categoria', 'grupo_canonico')
    search_fields = ('categoria', 'grupo_canonico')
    ordering = ('categoria',)



