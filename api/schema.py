"""Custom schema extensions for drf-spectacular to document custom serializer fields."""

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class TokenAuthScheme(OpenApiAuthenticationExtension):
    """Custom authentication scheme for token-based authentication used in the WoRMS cache API."""

    target_class = "api.services.token_auth.TokenAuth"
    name = "BearerAuth"

    def get_security_definition(self, auto_schema: object) -> dict:
        """Return the OpenAPI security definition for token-based authentication.

        Args:
            auto_schema: The AutoSchema instance for which the security definition is being generated.

        Returns:
            dict: A dictionary representing the OpenAPI security definition for token-based authentication.
        """
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "Token",
        }
