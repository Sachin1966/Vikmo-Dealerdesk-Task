"""Standard API exceptions and DRF custom exception handler matching API_CONTRACT.md.

Contract format:
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable text",
    "details": []
  }
}
"""
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_default_exception_handler


class DealerDeskAPIException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "VALIDATION_ERROR"
    default_message = "A validation error occurred."

    def __init__(self, message=None, code=None, details=None, status_code=None):
        if status_code is not None:
            self.status_code = status_code
        self.code = code or self.default_code
        self.message = message or self.default_message
        self.details = details if details is not None else []
        super().__init__(self.message)


class ValidationErrorException(DealerDeskAPIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "VALIDATION_ERROR"


class NotFoundException(DealerDeskAPIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_code = "NOT_FOUND"
    default_message = "Resource not found."


class DuplicateException(DealerDeskAPIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "DUPLICATE"
    default_message = "Resource already exists."


class InsufficientStockException(DealerDeskAPIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "INSUFFICIENT_STOCK"
    default_message = "Insufficient stock available."


class InvalidTransitionException(DealerDeskAPIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "INVALID_TRANSITION"
    default_message = "Status transition is not allowed."


class OrderLockedException(DealerDeskAPIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "ORDER_LOCKED"
    default_message = "Order is locked and cannot be edited."


class IdempotencyConflictException(DealerDeskAPIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "IDEMPOTENCY_CONFLICT"
    default_message = "Idempotency key reuse with differing request body."


class SupplierUnavailableException(DealerDeskAPIException):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_code = "SUPPLIER_UNAVAILABLE"
    default_message = "Supplier API unavailable or authentication failed."


def custom_exception_handler(exc, context):
    """DRF custom exception handler ensuring uniform error response envelope."""
    # First, handle DealerDesk domain exceptions
    if isinstance(exc, DealerDeskAPIException):
        return Response(
            {
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
            status=exc.status_code,
        )

    # Let standard DRF handler process framework exceptions
    response = drf_default_exception_handler(exc, context)

    if response is not None:
        status_code = response.status_code
        details = []
        code = "VALIDATION_ERROR"
        message = "A validation error occurred."

        if status_code == status.HTTP_404_NOT_FOUND:
            code = "NOT_FOUND"
            message = "The requested resource was not found."
        elif status_code == status.HTTP_400_BAD_REQUEST:
            code = "VALIDATION_ERROR"
            # Format DRF validation errors
            if isinstance(response.data, dict):
                # Check for custom error fields
                err_msgs = []
                for field, val in response.data.items():
                    if isinstance(val, list):
                        msg_str = ", ".join(str(v) for v in val)
                    else:
                        msg_str = str(val)
                    err_msgs.append(f"{field}: {msg_str}")
                    details.append({"field": field, "message": msg_str})
                if err_msgs:
                    message = "; ".join(err_msgs)
            elif isinstance(response.data, list):
                message = "; ".join(str(v) for v in response.data)
            else:
                message = str(response.data)
        elif status_code == status.HTTP_409_CONFLICT:
            code = "CONFLICT"
            message = "Conflict occurred."
        elif status_code >= 500:
            code = "SERVER_ERROR"
            message = "An internal server error occurred."
        else:
            message = str(response.data)

        return Response(
            {
                "error": {
                    "code": code,
                    "message": message,
                    "details": details,
                }
            },
            status=status_code,
        )

    # Unhandled unexpected exceptions
    return Response(
        {
            "error": {
                "code": "SERVER_ERROR",
                "message": str(exc),
                "details": [],
            }
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
