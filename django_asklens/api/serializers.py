"""DRF serializers for the AskLens API."""

from rest_framework import serializers

from django_asklens.models import SemanticQueryRun


class QueryRequestSerializer(serializers.Serializer):
    """Validate query endpoint input."""

    question = serializers.CharField(allow_blank=False, trim_whitespace=True)
    debug = serializers.BooleanField(default=False, required=False)


class SemanticQueryRunSerializer(serializers.ModelSerializer):
    """Serialize query-run audit records safely."""

    class Meta:
        model = SemanticQueryRun
        fields = (
            "id",
            "question",
            "plan",
            "status",
            "row_count",
            "duration_ms",
            "error",
            "created_at",
        )
        read_only_fields = fields
