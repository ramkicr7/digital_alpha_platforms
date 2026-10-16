from django.contrib import admin

from .models import BankTransaction, CapitalCallLineItem, Organization, ReconciliationMatch


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")


@admin.register(CapitalCallLineItem)
class CapitalCallLineItemAdmin(admin.ModelAdmin):
    list_display = ("reference", "organization", "investor_name", "called_amount", "funded_amount", "status")
    list_filter = ("organization", "status")


@admin.register(BankTransaction)
class BankTransactionAdmin(admin.ModelAdmin):
    list_display = ("reference", "organization", "date", "amount", "status")
    list_filter = ("organization", "status")


@admin.register(ReconciliationMatch)
class ReconciliationMatchAdmin(admin.ModelAdmin):
    list_display = ("transaction", "line_item", "amount", "status")
    list_filter = ("organization", "status")