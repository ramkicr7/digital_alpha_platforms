from django.db.models import Prefetch, Q
from rest_framework import generics
from rest_framework.exceptions import NotFound
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView, exception_handler

from . import services
from .models import BankTransaction, CapitalCallLineItem, Organization, ReconciliationMatch
from .serializers import (
    CSVUploadSerializer,
    LineItemSerializer,
    TransactionSerializer,
)


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None
    data = response.data
    message = data["detail"] if isinstance(data, dict) and "detail" in data else data
    codes = exc.get_codes() if hasattr(exc, "get_codes") else "error"
    code = codes if isinstance(codes, str) else "invalid"
    response.data = {"error": {"code": code, "message": message}}
    return response


def transactions_for(organization):
    matches = ReconciliationMatch.objects.select_related("line_item").order_by("id")
    return (
        BankTransaction.objects.filter(organization=organization)
        .prefetch_related(Prefetch("matches", queryset=matches))
        .order_by("-date", "-created_at", "-id")
    )


class OrganizationMixin:
    def get_organization(self):
        cached = getattr(self, "_organization", None)
        if cached is not None:
            return cached
        value = self.request.headers.get("X-Organization", "").strip()
        if not value:
            raise services.BadRequest(
                "The X-Organization header is required", code="organization_required"
            )
        organization = Organization.objects.filter(
            Q(slug__iexact=value) | Q(name__iexact=value)
        ).first()
        if organization is None:
            raise NotFound("Organization not found")
        self._organization = organization
        return organization


class TransactionListView(OrganizationMixin, generics.ListAPIView):
    serializer_class = TransactionSerializer
    pagination_class = None

    def get_queryset(self):
        queryset = transactions_for(self.get_organization())
        status_value = self.request.query_params.get("status")
        if status_value:
            queryset = queryset.filter(status=status_value)
        return queryset


class LineItemListView(OrganizationMixin, generics.ListAPIView):
    serializer_class = LineItemSerializer
    pagination_class = None

    def get_queryset(self):
        return CapitalCallLineItem.objects.filter(organization=self.get_organization())


class TransactionActionView(OrganizationMixin, APIView):
    action = None

    def post(self, request, pk):
        organization = self.get_organization()
        txn = getattr(services, self.action)(organization, pk)
        fresh = transactions_for(organization).get(pk=txn.pk)
        return Response(TransactionSerializer(fresh).data)


class MatchApproveView(TransactionActionView):
    action = "approve_match"


class MatchRejectView(TransactionActionView):
    action = "reject_match"


class TransactionIgnoreView(TransactionActionView):
    action = "ignore_transaction"


class ImportView(OrganizationMixin, APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        organization = self.get_organization()
        serializer = CSVUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = services.import_statement(organization, serializer.validated_data["file"])

        ids = [txn.pk for txn in result["imported"]]
        imported = transactions_for(organization).filter(pk__in=ids)

        body = {
            "imported_count": len(ids),
            "duplicate_count": len(result["duplicates"]),
            "error_count": len(result["errors"]),
            "imported": TransactionSerializer(imported, many=True).data,
            "duplicates": result["duplicates"],
            "errors": result["errors"],
        }
        return Response(body, status=201 if ids else 200)