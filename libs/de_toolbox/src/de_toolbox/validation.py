"""Input validation utilities.

Pure functions — no spark or dbutils dependency.
"""

import re
from string import Template


def is_valid_email(email: str) -> bool:
    """Validate email address format.

    Checks RFC 5322 compliant pattern with additional consecutive-dot check.
    """
    pattern = (
        r"^[a-zA-Z0-9.\!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9]"
        r"(?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z]{2,})+$"
    )
    if re.match(pattern, email):
        if ".." in email:
            return False
        return True
    return False


def is_valid_env(env: str) -> bool:
    """Check if environment string is valid for permission operations."""
    return env.lower() in ("dev", "stg", "prd")


def is_valid_template(template_string: str) -> bool:
    """Validate that a principal template uses only ${project} and ${env} placeholders."""
    template_string = template_string.strip()
    pattern = r"\$\{(\w+)\}"
    placeholders = re.findall(pattern, template_string)
    valid_placeholders = {"project", "env"}

    remaining_chars = re.sub(pattern, "", template_string)
    if "$" in remaining_chars:
        return False

    return set(placeholders) == valid_placeholders


def format_object_principal(principal: str, env: str, project: str) -> str:
    """Format a principal string — either validate as email or substitute template vars.

    Args:
        principal: Either an email address or a template like "${env}_${project}_owners".
        env: Environment (dev, stg, prd).
        project: Project name for substitution.

    Returns:
        Resolved principal string.

    Raises:
        ValueError: If env is invalid or template format is wrong.
    """
    principal = principal.strip()

    if is_valid_email(principal):
        return principal

    if not is_valid_env(env):
        raise ValueError(
            f'Invalid environment: {env.lower()}. Must be one of "dev", "stg", or "prd".'
        )

    if not is_valid_template(principal):
        raise ValueError(
            f"Invalid template format: {principal}. "
            'Principal group name template should contain "${project}" and "${env}".'
        )

    principal_template = Template(principal)
    try:
        return principal_template.substitute(project=project, env=env.lower())
    except KeyError as e:
        raise ValueError(f"Error in template substitution: {e}") from e
