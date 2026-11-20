# Django imports
from django.db import models


# Defines the available transaction types, distinguishing between income and expenses
class Type(models.TextChoices):
        INCOME = "income", "Ganho"
        EXPENSE = "expense", "Gasto"

# Defines the supported financial institutions and an option for unspecified or other banks
class Bank(models.TextChoices):
    NOT_INFORMED = "", "Não informado"
    BANCO_DO_BRASIL = "banco_do_brasil", "Banco do Brasil"
    BRADESCO = "bradesco", "Bradesco"
    BTG_PACTUAL = "btg_pactual", "BTG Pactual"
    C6_BANK = "c6_bank", "C6 Bank"
    CAIXA = "caixa", "Caixa Econômica Federal"
    INTER = "inter", "Banco Inter"
    ITAU = "itau", "Itaú Unibanco"
    MERCADO_PAGO = "mercado_pago", "Mercado Pago"
    NUBANK = "nubank", "Nubank"
    PAGBANK = "pagbank", "PagBank"
    PICPAY = "picpay", "PicPay"
    SANTANDER = "santander", "Santander"
    SICOOB = "sicoob", "Sicoob"
    SICREDI = "sicredi", "Sicredi"
    OTHER = "other", "Outro"