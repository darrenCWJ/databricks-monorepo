"""Tests for de_toolbox.validation — ported from test_common_function.py."""

import pytest
from de_toolbox.validation import (
    format_object_principal,
    is_valid_email,
    is_valid_env,
    is_valid_template,
)


class TestIsValidEmail:
    def test_valid_emails(self):
        valid_emails = [
            "user@example.com",
            "user.name@example.com",
            "user+name@example.com",
            "user-name@example.com",
            "user_name@example.com",
            "user123@example.com",
            "user@subdomain.example.com",
            "user@example-domain.com",
            "user@example.co.uk",
            "user@example.website",
        ]
        for email in valid_emails:
            assert is_valid_email(email), f"Expected valid: {email}"

    def test_invalid_emails(self):
        invalid_emails = [
            "userexample.com",
            "user@.com",
            "user@example",
            "user@exam ple.com",
            "user@exam\!ple.com",
            "user@example..com",
            "@example.com",
            "user@example.c",
            "user name@example.com",
        ]
        for email in invalid_emails:
            assert not is_valid_email(email), f"Expected invalid: {email}"

    def test_edge_cases(self):
        assert not is_valid_email("")
        assert not is_valid_email(" ")
        assert not is_valid_email("@")
        assert not is_valid_email("user@")
        assert not is_valid_email("@example.com")

    def test_case_sensitivity(self):
        assert is_valid_email("USER@EXAMPLE.COM")
        assert is_valid_email("user@example.com")

    def test_uncommon_tlds(self):
        assert is_valid_email("user@example.website")
        assert is_valid_email("user@example.photography")
        assert is_valid_email("user@example.photography.graphic")


class TestIsValidEnv:
    def test_valid_environments(self):
        for env in ["dev", "stg", "prd"]:
            assert is_valid_env(env)

    def test_case_insensitivity(self):
        for env in ["DEV", "STG", "PRD", "Dev", "Stg", "Prd"]:
            assert is_valid_env(env)

    def test_invalid_environments(self):
        for env in ["prod", "staging", "development", "test", "qa", "uat", ""]:
            assert not is_valid_env(env)

    def test_edge_cases(self):
        assert not is_valid_env("")
        assert not is_valid_env(" ")
        assert not is_valid_env("dev ")
        assert not is_valid_env(" dev")

    def test_non_string_input(self):
        with pytest.raises(AttributeError):
            is_valid_env(None)
        with pytest.raises(AttributeError):
            is_valid_env(123)


class TestIsValidTemplate:
    def test_valid_templates(self):
        valid_templates = [
            "${project}_${env}_group",
            "${env}_${project}_name",
            "prefix_${project}_${env}_suffix",
            "${project}${env}",
            "some_text_${project}_more_text_${env}_end",
            "${project}_${env} ",
            " ${project}_${env}",
        ]
        for template in valid_templates:
            assert is_valid_template(template), f"Expected valid: {template}"

    def test_invalid_templates(self):
        invalid_templates = [
            "${project}",
            "${env}",
            "${project}_${environment}",
            "${prject}_${en}",
            "$project_$env",
            "${project}_${env}_${extra}",
            "project_env_group",
            "${PROJECT}_${ENV}",
            "${project ${env}",
            "$${project}_${env}",
        ]
        for template in invalid_templates:
            assert not is_valid_template(template), f"Expected invalid: {template}"

    def test_edge_cases(self):
        assert not is_valid_template("")
        assert not is_valid_template(" ")

    def test_order_insensitivity(self):
        assert is_valid_template("${project}_${env}")
        assert is_valid_template("${env}_${project}")

    def test_multiple_occurrences(self):
        assert is_valid_template("${project}_${env}_${project}")
        assert not is_valid_template("${project}_${env}_${env}_${extra}")


class TestFormatObjectPrincipal:
    def test_valid_email(self):
        result = format_object_principal("user@example.com", "dev", "project1")
        assert result == "user@example.com"

    def test_valid_template(self):
        result = format_object_principal("${project}_${env}_group", "dev", "project1")
        assert result == "project1_dev_group"

    def test_invalid_environment(self):
        with pytest.raises(ValueError, match="Invalid environment"):
            format_object_principal("${project}_${env}_group", "invalid", "project1")

    def test_invalid_template(self):
        with pytest.raises(ValueError, match="Invalid template format"):
            format_object_principal("${project}_${environment}_group", "dev", "project1")

    def test_missing_placeholder(self):
        with pytest.raises(ValueError, match="Invalid template format"):
            format_object_principal("${project}_group", "dev", "project1")

    def test_case_sensitivity(self):
        with pytest.raises(ValueError, match="Invalid template format"):
            format_object_principal("${PROJECT}_${ENV}_group", "DEV", "Project1")

    def test_whitespace_handling(self):
        result = format_object_principal(" ${project}_${env}_group ", "dev", "project1")
        assert result == "project1_dev_group"

    def test_complex_template(self):
        result = format_object_principal(
            "prefix_${project}_middle_${env}_suffix", "stg", "project2"
        )
        assert result == "prefix_project2_middle_stg_suffix"
