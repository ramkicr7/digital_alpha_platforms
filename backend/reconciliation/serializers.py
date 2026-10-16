from rest_framework import serializers

from .models import BankTransaction, CapitalCallLineItem, ReconciliationMatch

MAX_UPLOAD_BYTES = 5 * 1024 * 1024


class LineItemSerializer(serializers.ModelSerializer):
    remaining_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = CapitalCallLineItem
        fields = [
            "id",
            "reference",
            "investor_name",
            "call_date",
            "called_amount",
            "funded_amount",
            "remaining_amount",
            "status",
        ]


class MatchSerializer(serializers.ModelSerializer):
    line_item_reference = serializers.CharField(source="line_item.reference", read_only=True)
    investor_name = serializers.CharField(source="line_item.investor_name", read_only=True)

    class Meta:
        model = ReconciliationMatch
        fields = [
            "id",
            "line_item",
            "line_item_reference",
            "investor_name",
            "amount",
            "status",
            "reason",
        ]


class TransactionSerializer(serializers.ModelSerializer):
    type = serializers.ReadOnlyField(source="kind")
    matches = MatchSerializer(many=True, read_only=True)

    class Meta:
        model = BankTransaction
        fields = [
            "id",
            "date",
            "description",
            "reference",
            "amount",
            "type",
            "status",
            "review_reason",
            "matches",
        ]


class CSVUploadSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, value):
        if value.size > MAX_UPLOAD_BYTES:
            raise serializers.ValidationError("File is larger than 5 MB")
        return value