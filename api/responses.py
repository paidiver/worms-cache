"""RFC 9457 errors for the cache API; successful WoRMS shapes are preserved."""

import logging
from collections.abc import Callable
from http import HTTPStatus
from typing import Any

import requests
from django.http import HttpRequest, HttpResponse, JsonResponse
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from api.services.taxamatch_client import TaxamatchError
from api.services.worms_client import WoRMSError

logger = logging.getLogger(__name__)


def field_errors(value: Any, prefix: str = "") -> list[dict[str, str]]:
    """Flatten nested serializer errors into stable field/message entries."""
    if isinstance(value, dict):
        return [error for key, item in value.items() for error in field_errors(item, f"{prefix}.{key}".strip("."))]
    if isinstance(value, list | tuple):
        return [
            error
            for index, item in enumerate(value)
            for error in field_errors(item, f"{prefix}.{index}".strip(".") if isinstance(item, dict | list) else prefix)
        ]
    return [{"field": prefix or "non_field_errors", "message": str(value)}]


def problem_details(data: Any, status_code: int) -> dict:
    """Normalize framework errors and explicitly returned validation errors."""
    if isinstance(data, dict) and data.get("type") == "about:blank" and "status" in data:
        return data
    title = HTTPStatus(status_code).phrase
    code = {
        400: "invalid_parameters",
        401: "not_authenticated",
        403: "permission_denied",
        404: "not_found",
        405: "method_not_allowed",
        415: "unsupported_media_type",
        429: "throttled",
        500: "internal_error",
        502: "upstream_failed",
        504: "upstream_timeout",
    }.get(status_code, "request_failed")
    detail = data.get("detail", data.get("error")) if isinstance(data, dict) else data
    errors = None
    if isinstance(detail, dict | list):
        errors = field_errors(detail)
        detail = "One or more request parameters are invalid."
    elif detail is None:
        errors = field_errors(data)
        detail = "One or more request parameters are invalid."
    elif isinstance(data, dict):
        extra = {key: value for key, value in data.items() if key not in {"detail", "error"}}
        if extra:
            errors = field_errors(extra)
    result = {"type": "about:blank", "title": title, "status": status_code, "detail": str(detail), "code": code}
    if errors:
        result["errors"] = errors
    return result


def exception_handler(exc: Exception, context: dict) -> Response:
    """Handle upstream and unexpected exceptions without exposing internals."""
    response = drf_exception_handler(exc, context)
    if response is not None:
        return response
    if isinstance(exc, TaxamatchError | WoRMSError):
        return Response({"detail": str(exc)}, status=exc.status_code)
    if isinstance(exc, requests.Timeout):
        return Response({"detail": "The taxonomy service did not respond in time."}, status=504)
    if isinstance(exc, requests.RequestException):
        return Response({"detail": "The taxonomy service could not complete the request."}, status=502)
    logger.exception("Unhandled API exception", exc_info=exc)
    return Response({"detail": "An unexpected error occurred."}, status=500)


class ProblemDetailsMiddleware:
    """Normalize both explicit DRF errors and exception-handler responses."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Include routing errors that occur outside DRF views."""
        response = self.get_response(request)
        if (
            request.path.startswith("/api/")
            and response.status_code >= HTTPStatus.BAD_REQUEST
            and not isinstance(response, Response)
        ):
            body = JsonResponse(
                problem_details({"detail": HTTPStatus(response.status_code).phrase}, response.status_code)
            )
            response.content = body.content
            response["Content-Type"] = "application/problem+json"
            if "Content-Length" in response:
                response["Content-Length"] = str(len(response.content))
        return response

    def process_template_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Normalize DRF errors before rendering while retaining response headers."""
        if isinstance(response, Response) and response.status_code >= HTTPStatus.BAD_REQUEST:
            response.data = problem_details(response.data, response.status_code)
            response.content_type = "application/problem+json"
            response.accepted_renderer = JSONRenderer()
            response.accepted_media_type = "application/problem+json"
        return response
