from rest_framework import serializers
from rest_framework.reverse import reverse
from api.models import (
    SurveyData,
    Survey,
    SurveyDataType,
    QuestionData,
    SURVEY_DATA_PRIVATE_FIELDS,
)
from django.contrib.auth.models import User
from urllib.parse import quote


class SurveySerializer(serializers.ModelSerializer):
    control = serializers.JSONField()

    class Meta:
        model = Survey
        fields = "__all__"

    def to_representation(self, instance):
        control_type = SurveyDataType.objects.get(type="Control")

        instance.control = {}
        for control_data in SurveyData.objects.filter(type=control_type, survey=instance).all():
            instance.control[control_data.data.get("field")] = control_data.data.get("value")

        output = super().to_representation(instance)
        output["_url"] = reverse("survey-detail", args=[instance.id], request=self.context["request"])
        output["_data_url"] = reverse("survey-data-list", args=[instance.id], request=self.context["request"])
        return output

    def create(self, validated_data):

        control_data = {key: value for key, value in validated_data.pop("control").items() if value}

        mandatory_fields = set(["Coordinator Email", "Researcher", "Status"])
        if not set(control_data.keys()).issuperset(set(["Coordinator Email", "Researcher", "Status"])):
            raise serializers.ValidationError(f"Need fields {', '.join(mandatory_fields)}")

        survey = Survey.objects.create(**validated_data)

        control_type = SurveyDataType.objects.get(type="Control")

        for key, value in control_data.items():
            SurveyData.objects.create(type=control_type, survey=survey, data={"field": key, "value": value})

        return survey

    def update(self, instance, validated_data):
        control_type = SurveyDataType.objects.get(type="Control")

        current_control_data = {}
        for control_data in SurveyData.objects.filter(type=control_type, survey=instance).all():
            current_control_data[control_data.data.get("field")] = control_data

        for key, value in validated_data.pop("control").items():
            existing_data = current_control_data.get(key)
            if not value:
                if existing_data:
                    existing_data.delete()
                continue
            if existing_data:
                existing_data.data["value"] = value
                existing_data.save()
            else:
                SurveyData.objects.create(
                    type=control_type,
                    survey=instance,
                    data={"field": key, "value": value},
                )
        return instance


class SurveyDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = SurveyData
        fields = ["id", "type", "data"]

    type = serializers.SlugRelatedField(slug_field="type", queryset=SurveyDataType.objects.all())

    def to_internal_value(self, data):
        if "data" not in data:
            data["data"] = {}
            for key, value in list(data.items()):
                if key.startswith("_") or key in SURVEY_DATA_PRIVATE_FIELDS:
                    continue
                data["data"][key] = value
                data.pop(key)

        internal_value = super().to_internal_value(data)

        internal_value["survey_id"] = self.context["view"].kwargs["survey"]

        return internal_value

    def to_representation(self, instance):
        output = super().to_representation(instance)
        data = output.pop("data")
        new_data = {}
        for key in instance.type.fields:
            new_data[key] = data.get(key, "")

        output["_id"] = output.pop("id")
        output.update(new_data)

        output["_url"] = self.context["view"].reverse_action("detail", args=[instance.survey.id, instance.id])

        return output


class SurveyDataTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SurveyDataType
        fields = ["id", "type", "fields"]


class QuestionDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionData
        fields = ["id", "type", "data"]

    def to_internal_value(self, data):
        if "data" not in data:
            data["data"] = {}
            for key, value in list(data.items()):
                if key.startswith("_"):
                    continue
                data["data"][key] = value
                data.pop(key)

        internal_value = super().to_internal_value(data)

        internal_value["name"] = self.context["request"].query_params.get("name", "")

        return internal_value

    def to_representation(self, instance):
        output = super().to_representation(instance)
        data = output.pop("data")

        output.update(data)

        output["_url"] = self.context["view"].reverse_action("detail", args=[instance.id])
        if instance.name:
            output["_url"] += f'?name={quote(instance.name)}'


        return output
