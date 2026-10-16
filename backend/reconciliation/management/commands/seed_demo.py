from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from reconciliation.models import CapitalCallLineItem, Organization


DEMO = [
    {
        "slug": "northwind",
        "name": "Northwind Ventures",
        "items": [
            ("CC-1001", "Haller Capital LLC", "27500.00", date(2026, 4, 4)),
            ("CC-1002", "Rahul Shah Trust", "25000.00", date(2026, 4, 3)),
            ("CC-1003", "Patel Family Trust", "12500.00", date(2026, 4, 15)),
            ("CC-1004", "Meridian Partners LP", "15000.00", date(2026, 4, 16)),
            ("CC-1005", "Oakridge Holdings LLC", "15000.00", date(2026, 4, 20)),
            ("CC-1006", "Oakridge Holdings LLC", "15000.00", date(2026, 4, 21)),
        ],
    },
    {
        "slug": "bluebird",
        "name": "Bluebird Capital",
        "items": [
            ("CC-2001", "Cedar Grove Fund LP", "40000.00", date(2026, 4, 16)),
        ],
    },
]


class Command(BaseCommand):
    help = "Create demo organizations and capital-call line items"

    @transaction.atomic
    def handle(self, *args, **options):
        new_orgs = 0
        new_items = 0

        for entry in DEMO:
            organization, created = Organization.objects.get_or_create(
                slug=entry["slug"],
                defaults={"name": entry["name"]},
            )
            new_orgs += int(created)

            for reference, investor, amount, call_date in entry["items"]:
                _, created = CapitalCallLineItem.objects.get_or_create(
                    organization=organization,
                    reference=reference,
                    defaults={
                        "investor_name": investor,
                        "called_amount": Decimal(amount),
                        "call_date": call_date,
                    },
                )
                new_items += int(created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {new_orgs} organizations and {new_items} line items"
            )
        )