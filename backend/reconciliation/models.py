from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q


class Organization(models.Model):
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class CapitalCallLineItem(models.Model):
    class Status(models.TextChoices):
        OPEN = "open"
        PARTIALLY_FUNDED = "partially_funded"
        FUNDED = "funded"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="line_items"
    )
    reference = models.CharField(max_length=64)
    investor_name = models.CharField(max_length=200)
    called_amount = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    funded_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    call_date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)

    class Meta:
        ordering = ["call_date", "reference"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "reference"], name="unique_line_item_reference_per_org"
            ),
            models.CheckConstraint(
                condition=Q(funded_amount__gte=0) & Q(funded_amount__lte=F("called_amount")),
                name="funded_amount_within_called_amount",
            ),
        ]

    @property
    def remaining_amount(self):
        return self.called_amount - self.funded_amount

    def __str__(self):
        return f"{self.reference} - {self.investor_name}"


class BankTransaction(models.Model):
    class Status(models.TextChoices):
        SUGGESTED = "suggested"
        NEEDS_REVIEW = "needs_review"
        RECONCILED = "reconciled"
        IGNORED = "ignored"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="transactions"
    )
    date = models.DateField()
    description = models.CharField(max_length=500)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    reference = models.CharField(max_length=128)
    status = models.CharField(max_length=20, choices=Status.choices)
    review_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "reference"], name="unique_transaction_reference_per_org"
            ),
            models.CheckConstraint(condition=~Q(amount=0), name="transaction_amount_not_zero"),
        ]
        indexes = [models.Index(fields=["organization", "-date"])]

    @property
    def kind(self):
        return "credit" if self.amount > 0 else "debit"

    def __str__(self):
        return f"{self.reference} {self.amount}"


class ReconciliationMatch(models.Model):
    class Status(models.TextChoices):
        PROPOSED = "proposed"
        APPROVED = "approved"
        REJECTED = "rejected"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="matches"
    )
    transaction = models.ForeignKey(
        BankTransaction, on_delete=models.CASCADE, related_name="matches"
    )
    line_item = models.ForeignKey(
        CapitalCallLineItem, on_delete=models.CASCADE, related_name="matches"
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PROPOSED)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["transaction", "line_item"], name="unique_match_per_transaction_item"
            ),
        ]