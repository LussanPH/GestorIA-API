from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager



class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("O endereço de email é obrigatório!")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError("superuser precisa ter is_staff=True.")
        if extra_fields.get('is_superuser') is not True:
            raise ValueError("superuser precisa ter is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class Usuarios(AbstractUser):
    username = None

    email = models.EmailField(unique=True)

    USERNAME_FIELD = 'email'

    REQUIRED_FIELDS = ['nome_completo']

    nome_completo = models.CharField(unique=True, max_length=100)

    objects = CustomUserManager()


class NotasFiscais(models.Model):
    chave_acesso = models.CharField(primary_key=True, max_length=44)
    fk_usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    data_compra = models.DateField(null=False)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2)
    cnpj = models.CharField(max_length=14, blank=True, default="")
    metodo_pag = models.CharField(max_length=20, blank=True, default="")


class Categorias(models.Model):
    categoria = models.CharField(max_length=50, blank=False)


class ProdutosNotasFiscais(models.Model):
    nota_fk = models.ForeignKey(NotasFiscais, on_delete=models.CASCADE)
    un = models.DecimalField(max_digits=10, decimal_places=3, blank=False)
    valor_unitario = models.DecimalField(max_digits=10, decimal_places=2, blank=False)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, blank=False)
    nome = models.CharField(max_length=100, blank=False)
    marca = models.CharField(max_length=50, blank=True, default="nao_identificada")
    categoria_fk = models.ForeignKey(Categorias, on_delete=models.CASCADE)