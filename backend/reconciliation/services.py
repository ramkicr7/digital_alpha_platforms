import csv
import io
import re
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.db.models import F
from rest_framework.exceptions import APIException, NotFound

from .models import BankTransaction, CapitalCallLineItem, ReconciliationMatch

REQUIRED_COLUMNS = ("date", "description", "amount", "type", "reference")
NAME_SUFFIXES = {"LLC", "LP", "LTD", "INC"}
CENT = Decimal("0.01")
MAX_AMOUNT = Decimal("999999999999.99")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
OPEN_STATES = (BankTransaction.Status.SUGGESTED, BankTransaction.Status.NEEDS_REVIEW)


class BadRequest(APIException):
    status_code = 400
    default_detail = "Bad request"
    default_code = "bad_request"


class Conflict(APIException):
    status_code = 409
    default_detail = "Conflict"
    default_code = "conflict"


def normalize_reference(value):
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def normalize_name(value):
    words = re.sub(r"[^A-Z0-9]+", " ", (value or "").upper()).split()
    while words and words[-1] in NAME_SUFFIXES:
        words.pop()
    return " ".join(words)


def parse_amount(raw):
    try:
        value = Decimal(raw.replace(",", "").strip())
        if not value.is_finite():
            raise InvalidOperation
        value = value.quantize(CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        raise ValueError("amount is not a valid number")
    if value == 0:
        raise ValueError("amount must not be zero")
    if abs(value) > MAX_AMOUNT:
        raise ValueError("amount is too large")
    return abs(value)


def parse_date(raw):
    if not DATE_PATTERN.match(raw):
        raise ValueError("date must use YYYY-MM-DD")
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("date is not a valid calendar date")


def clean_row(row):
    values = {name: (row.get(name) or "").strip() for name in REQUIRED_COLUMNS}
    problems = []

    if not values["description"]:
        problems.append("description is required")
    if not values["reference"]:
        problems.append("reference is required")

    parsed_date = None
    try:
        parsed_date = parse_date(values["date"])
    except ValueError as exc:
        problems.append(str(exc))

    amount = None
    try:
        amount = parse_amount(values["amount"])
    except ValueError as exc:
        problems.append(str(exc))

    kind = values["type"].lower()
    if kind not in ("credit", "debit"):
        problems.append("type must be credit or debit")

    if problems:
        return None, problems

    return {
        "date": parsed_date,
        "description": values["description"],
        "reference": values["reference"],
        "amount": amount if kind == "credit" else -amount,
    }, []


def set_status(txn, status, reason=""):
    txn.status = status
    txn.review_reason = reason
    txn.save(update_fields=["status", "review_reason"])


def propose(txn, item, reason):
    return ReconciliationMatch.objects.create(
        organization_id=txn.organization_id,
        transaction=txn,
        line_item=item,
        amount=txn.amount,
        reason=reason,
    )


def resolve_by_reference(txn, hits):
    if len(hits) == 1:
        item = hits[0]
        if txn.amount > item.remaining_amount:
            set_status(
                txn,
                BankTransaction.Status.NEEDS_REVIEW,
                f"Overpayment: credit of {txn.amount} exceeds the remaining "
                f"{item.remaining_amount} on {item.reference}",
            )
            return
        propose(txn, item, f"Reference {item.reference} found in the transaction text")
        set_status(txn, BankTransaction.Status.SUGGESTED)
        return

    refs = ", ".join(item.reference for item in hits)
    fitting = [item for item in hits if txn.amount <= item.remaining_amount]
    for item in fitting:
        propose(txn, item, f"Reference {item.reference} found in the transaction text")
    set_status(
        txn,
        BankTransaction.Status.NEEDS_REVIEW,
        f"Ambiguous: references for {len(hits)} line items found ({refs}); manual selection required",
    )


def resolve_by_name(txn, items):
    haystack = f" {normalize_name(txn.description)} "
    name_hits = []
    for item in items:
        name = normalize_name(item.investor_name)
        if name and f" {name} " in haystack:
            name_hits.append(item)

    if not name_hits:
        set_status(
            txn,
            BankTransaction.Status.NEEDS_REVIEW,
            "No reference or investor name matched an open capital call",
        )
        return

    exact = [item for item in name_hits if item.remaining_amount == txn.amount]

    if len(exact) == 1:
        item = exact[0]
        propose(
            txn,
            item,
            f"Investor name {item.investor_name} and exact remaining balance {item.remaining_amount}",
        )
        set_status(txn, BankTransaction.Status.SUGGESTED)
    elif len(exact) > 1:
        for item in exact:
            propose(
                txn,
                item,
                f"Investor name {item.investor_name} and exact remaining balance {item.remaining_amount}",
            )
        set_status(
            txn,
            BankTransaction.Status.NEEDS_REVIEW,
            f"Ambiguous: {len(exact)} line items share the investor name and remaining balance",
        )
    else:
        largest = max(item.remaining_amount for item in name_hits)
        label = "Overpayment" if txn.amount > largest else "Amount mismatch"
        set_status(
            txn,
            BankTransaction.Status.NEEDS_REVIEW,
            f"{label}: investor name matched but {txn.amount} differs from the remaining balance",
        )


def evaluate_credit(txn):
    items = list(
        CapitalCallLineItem.objects.filter(
            organization_id=txn.organization_id,
            call_date__lte=txn.date,
            funded_amount__lt=F("called_amount"),
        )
    )
    haystacks = (normalize_reference(txn.description), normalize_reference(txn.reference))
    hits = []
    for item in items:
        key = normalize_reference(item.reference)
        if key and any(key in text for text in haystacks):
            hits.append(item)

    if hits:
        resolve_by_reference(txn, hits)
    else:
        resolve_by_name(txn, items)


def import_statement(organization, uploaded_file):
    try:
        text = uploaded_file.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        raise BadRequest("The file must be UTF-8 encoded CSV", code="invalid_encoding")

    reader = csv.DictReader(io.StringIO(text))
    header = [(name or "").strip().lower() for name in (reader.fieldnames or [])]
    missing = [name for name in REQUIRED_COLUMNS if name not in header]
    if missing:
        raise BadRequest(
            "Missing required columns: " + ", ".join(missing), code="missing_columns"
        )
    reader.fieldnames = header

    imported, duplicates, errors = [], [], []

    try:
        with transaction.atomic():
            for line_no, row in enumerate(reader, start=2):
                data, problems = clean_row(row)
                if problems:
                    errors.append({"line": line_no, "errors": problems})
                    continue

                is_credit = data["amount"] > 0
                try:
                    with transaction.atomic():
                        txn = BankTransaction.objects.create(
                            organization=organization,
                            status=(
                                BankTransaction.Status.NEEDS_REVIEW
                                if is_credit
                                else BankTransaction.Status.IGNORED
                            ),
                            review_reason="" if is_credit else "Debit transaction, not matched",
                            **data,
                        )
                except IntegrityError:
                    duplicates.append({"line": line_no, "reference": data["reference"]})
                    continue

                if is_credit:
                    evaluate_credit(txn)
                imported.append(txn)
    except csv.Error as exc:
        raise BadRequest(f"Malformed CSV: {exc}", code="malformed_csv")

    return {"imported": imported, "duplicates": duplicates, "errors": errors}


def approve_match(organization, match_id):
    with transaction.atomic():
        match = (
            ReconciliationMatch.objects.select_for_update()
            .filter(organization=organization, pk=match_id)
            .first()
        )
        if match is None:
            raise NotFound("Match not found")

        txn = BankTransaction.objects.select_for_update().get(pk=match.transaction_id)
        item = CapitalCallLineItem.objects.select_for_update().get(pk=match.line_item_id)

        if match.status != ReconciliationMatch.Status.PROPOSED:
            raise Conflict(f"Match is already {match.status}")
        if txn.status not in OPEN_STATES:
            raise Conflict(f"Transaction is already {txn.status}")
        if match.amount > item.remaining_amount:
            raise Conflict("Approval would overfund the capital call")

        item.funded_amount += match.amount
        item.status = (
            CapitalCallLineItem.Status.FUNDED
            if item.remaining_amount == 0
            else CapitalCallLineItem.Status.PARTIALLY_FUNDED
        )
        item.save(update_fields=["funded_amount", "status"])

        match.status = ReconciliationMatch.Status.APPROVED
        match.save(update_fields=["status"])

        ReconciliationMatch.objects.filter(
            transaction=txn, status=ReconciliationMatch.Status.PROPOSED
        ).exclude(pk=match.pk).update(status=ReconciliationMatch.Status.REJECTED)

        set_status(txn, BankTransaction.Status.RECONCILED)
        return txn


def reject_match(organization, match_id):
    with transaction.atomic():
        match = (
            ReconciliationMatch.objects.select_for_update()
            .filter(organization=organization, pk=match_id)
            .first()
        )
        if match is None:
            raise NotFound("Match not found")

        txn = BankTransaction.objects.select_for_update().get(pk=match.transaction_id)

        if match.status != ReconciliationMatch.Status.PROPOSED:
            raise Conflict(f"Match is already {match.status}")

        match.status = ReconciliationMatch.Status.REJECTED
        match.save(update_fields=["status"])

        still_open = ReconciliationMatch.objects.filter(
            transaction=txn, status=ReconciliationMatch.Status.PROPOSED
        ).exists()
        if txn.status in OPEN_STATES and not still_open:
            set_status(
                txn,
                BankTransaction.Status.NEEDS_REVIEW,
                "All proposed matches were rejected; manual review required",
            )
        return txn


def ignore_transaction(organization, transaction_id):
    with transaction.atomic():
        txn = (
            BankTransaction.objects.select_for_update()
            .filter(organization=organization, pk=transaction_id)
            .first()
        )
        if txn is None:
            raise NotFound("Transaction not found")
        if txn.status == BankTransaction.Status.RECONCILED:
            raise Conflict("A reconciled transaction cannot be ignored")

        if txn.status != BankTransaction.Status.IGNORED:
            ReconciliationMatch.objects.filter(
                transaction=txn, status=ReconciliationMatch.Status.PROPOSED
            ).update(status=ReconciliationMatch.Status.REJECTED)
            set_status(txn, BankTransaction.Status.IGNORED, "Ignored by reviewer")
        return txn