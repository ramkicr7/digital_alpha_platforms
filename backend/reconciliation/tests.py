from datetime import date
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from .models import (
    BankTransaction,
    CapitalCallLineItem,
    Organization,
    ReconciliationMatch,
)

HEADER = "date,description,amount,type,reference"


def row(reference, amount="1000.00", description="Wire", kind="credit", day="2026-02-01"):
    return f"{day},{description},{amount},{kind},{reference}"


class BaseCase(APITestCase):
    def setUp(self):
        self.alpha = Organization.objects.create(name="Alpha Fund", slug="alpha")
        self.beta = Organization.objects.create(name="Beta Fund", slug="beta")
        self.item = CapitalCallLineItem.objects.create(
            organization=self.alpha,
            reference="CC-1001",
            investor_name="Alderwood Holdings LLC",
            called_amount=Decimal("1000.00"),
            call_date=date(2026, 1, 1),
        )

    def upload(self, rows, org="alpha", header=HEADER):
        content = header + "\n" + "\n".join(rows) + "\n"
        file = SimpleUploadedFile("statement.csv", content.encode(), content_type="text/csv")
        return self.client.post(
            "/api/imports/", {"file": file}, format="multipart", HTTP_X_ORGANIZATION=org
        )

    def act(self, url, org="alpha"):
        return self.client.post(url, HTTP_X_ORGANIZATION=org)

    def txn(self, reference, org=None):
        return BankTransaction.objects.get(
            organization=org or self.alpha, reference=reference
        )


class CsvImportTests(BaseCase):
    def test_missing_columns_reject_everything(self):
        response = self.upload(["2026-02-01,Wire,100.00,credit"], header="date,description,amount,type")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "missing_columns")
        self.assertEqual(BankTransaction.objects.count(), 0)

    def test_parsing_signs_and_types(self):
        response = self.upload(
            [
                row("R1", '"1,250.50"', kind="CrEdIt"),
                row("R2", "10.00", description="Fee", kind="Debit"),
            ]
        )
        self.assertEqual(response.status_code, 201)
        credit = self.txn("R1")
        debit = self.txn("R2")
        self.assertEqual(credit.amount, Decimal("1250.50"))
        self.assertEqual(debit.amount, Decimal("-10.00"))
        self.assertEqual(debit.status, BankTransaction.Status.IGNORED)

    def test_invalid_rows_reported_by_line_number(self):
        response = self.upload(
            [
                row("R1"),
                row("R2", day="2026-13-01"),
                row("R3", amount="0.00"),
                row("R4", kind="refund"),
            ]
        )
        body = response.json()
        self.assertEqual(body["imported_count"], 1)
        self.assertEqual([e["line"] for e in body["errors"]], [3, 4, 5])

    def test_duplicates_within_and_across_uploads(self):
        body = self.upload([row("R1"), row("R1")]).json()
        self.assertEqual(body["imported_count"], 1)
        self.assertEqual(body["duplicates"][0]["line"], 3)

        again = self.upload([row("R1")]).json()
        self.assertEqual(again["duplicate_count"], 1)
        self.assertEqual(again["imported_count"], 0)

        other = self.upload([row("R1")], org="beta").json()
        self.assertEqual(other["imported_count"], 1)
        self.assertEqual(BankTransaction.objects.filter(reference="R1").count(), 2)


class MatchingTests(BaseCase):
    def test_reference_in_description_with_different_formatting(self):
        self.upload([row("R1", "400.00", description="Payment cc1001 thanks")])
        txn = self.txn("R1")
        self.assertEqual(txn.status, BankTransaction.Status.SUGGESTED)
        self.assertEqual(txn.matches.count(), 1)

    def test_reference_in_bank_reference_field(self):
        self.upload([row("cc-1001", "400.00")])
        self.assertEqual(self.txn("cc-1001").status, BankTransaction.Status.SUGGESTED)

    def test_name_and_exact_amount(self):
        self.upload([row("R1", "1000.00", description="Alderwood Holdings wire")])
        txn = self.txn("R1")
        self.assertEqual(txn.status, BankTransaction.Status.SUGGESTED)
        self.assertIn("Investor name", txn.matches.get().reason)

    def test_name_match_with_wrong_amount_needs_review(self):
        self.upload([row("R1", "999.00", description="Alderwood Holdings wire")])
        txn = self.txn("R1")
        self.assertEqual(txn.status, BankTransaction.Status.NEEDS_REVIEW)
        self.assertEqual(txn.matches.count(), 0)

    def test_multiple_candidates_need_review(self):
        CapitalCallLineItem.objects.create(
            organization=self.alpha,
            reference="CC-1002",
            investor_name="Alderwood Holdings LP",
            called_amount=Decimal("1000.00"),
            call_date=date(2026, 1, 1),
        )
        self.upload([row("R1", "1000.00", description="Alderwood Holdings")])
        txn = self.txn("R1")
        self.assertEqual(txn.status, BankTransaction.Status.NEEDS_REVIEW)
        self.assertEqual(txn.matches.count(), 2)
        self.assertIn("Ambiguous", txn.review_reason)

    def test_overpayment_needs_review(self):
        self.upload([row("R1", "1500.00", description="Capital call CC-1001")])
        txn = self.txn("R1")
        self.assertEqual(txn.status, BankTransaction.Status.NEEDS_REVIEW)
        self.assertIn("Overpayment", txn.review_reason)
        self.assertEqual(txn.matches.count(), 0)

    def test_future_call_date_is_not_eligible(self):
        self.upload([row("R1", "1000.00", description="CC-1001", day="2025-12-31")])
        self.assertEqual(self.txn("R1").status, BankTransaction.Status.NEEDS_REVIEW)


class ActionTests(BaseCase):
    def setUp(self):
        super().setUp()
        self.upload([row("R1", "400.00", description="CC-1001")])
        self.match = ReconciliationMatch.objects.get()

    def test_approval_updates_balances(self):
        response = self.act(f"/api/matches/{self.match.pk}/approve/")
        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.funded_amount, Decimal("400.00"))
        self.assertEqual(self.item.remaining_amount, Decimal("600.00"))
        self.assertEqual(self.item.status, CapitalCallLineItem.Status.PARTIALLY_FUNDED)
        self.assertEqual(self.txn("R1").status, BankTransaction.Status.RECONCILED)
        self.match.refresh_from_db()
        self.assertEqual(self.match.status, ReconciliationMatch.Status.APPROVED)

    def test_repeated_approval_is_a_conflict(self):
        url = f"/api/matches/{self.match.pk}/approve/"
        self.assertEqual(self.act(url).status_code, 200)
        self.assertEqual(self.act(url).status_code, 409)
        self.item.refresh_from_db()
        self.assertEqual(self.item.funded_amount, Decimal("400.00"))

    def test_approval_cannot_overfund(self):
        self.item.funded_amount = Decimal("800.00")
        self.item.save()
        response = self.act(f"/api/matches/{self.match.pk}/approve/")
        self.assertEqual(response.status_code, 409)
        self.item.refresh_from_db()
        self.assertEqual(self.item.funded_amount, Decimal("800.00"))

    def test_reject_moves_transaction_to_review(self):
        response = self.act(f"/api/matches/{self.match.pk}/reject/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.txn("R1").status, BankTransaction.Status.NEEDS_REVIEW)

    def test_ignore_rejects_matches(self):
        txn = self.txn("R1")
        response = self.act(f"/api/transactions/{txn.pk}/ignore/")
        self.assertEqual(response.status_code, 200)
        self.match.refresh_from_db()
        self.assertEqual(self.match.status, ReconciliationMatch.Status.REJECTED)
        self.assertEqual(self.txn("R1").status, BankTransaction.Status.IGNORED)

    def test_ignore_reconciled_is_a_conflict(self):
        self.act(f"/api/matches/{self.match.pk}/approve/")
        txn = self.txn("R1")
        self.assertEqual(self.act(f"/api/transactions/{txn.pk}/ignore/").status_code, 409)


class IsolationTests(BaseCase):
    def test_header_rules(self):
        self.assertEqual(self.client.get("/api/transactions/").status_code, 400)
        response = self.client.get("/api/transactions/", HTTP_X_ORGANIZATION="nope")
        self.assertEqual(response.status_code, 404)

    def test_listings_are_scoped(self):
        self.upload([row("R1", "400.00", description="CC-1001")])
        mine = self.client.get("/api/transactions/", HTTP_X_ORGANIZATION="alpha").json()
        theirs = self.client.get("/api/transactions/", HTTP_X_ORGANIZATION="beta").json()
        self.assertEqual(len(mine), 1)
        self.assertEqual(theirs, [])
        items = self.client.get("/api/line-items/", HTTP_X_ORGANIZATION="beta").json()
        self.assertEqual(items, [])

    def test_actions_across_organizations_return_404(self):
        self.upload([row("R1", "400.00", description="CC-1001")])
        match = ReconciliationMatch.objects.get()
        txn = self.txn("R1")
        self.assertEqual(self.act(f"/api/matches/{match.pk}/approve/", org="beta").status_code, 404)
        self.assertEqual(self.act(f"/api/matches/{match.pk}/reject/", org="beta").status_code, 404)
        self.assertEqual(self.act(f"/api/transactions/{txn.pk}/ignore/", org="beta").status_code, 404)
        self.item.refresh_from_db()
        self.assertEqual(self.item.funded_amount, Decimal("0.00"))

    def test_transactions_listed_newest_first(self):
        self.upload([row("R1", day="2026-02-01"), row("R2", day="2026-03-01")])
        data = self.client.get("/api/transactions/", HTTP_X_ORGANIZATION="alpha").json()
        self.assertEqual([t["reference"] for t in data], ["R2", "R1"])