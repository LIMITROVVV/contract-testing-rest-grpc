"""
Contract tests for Orders API using Schemathesis.

Schemathesis generates test cases from the OpenAPI spec and checks that:
- every response matches the declared schema
- required fields are present
- response codes are within the declared set

By default tests run against BASE_URL. Override with:
  BASE_URL=http://staging:8080 pytest test_openapi_contract.py

To run the full Schemathesis CLI instead (more options):
  schemathesis run openapi.yaml --base-url http://localhost:8080 --checks all
"""

import os
import pytest
import schemathesis
from schemathesis import Case

BASE_URL = os.getenv("BASE_URL", "http://localhost:8080")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "openapi.yaml")

# load schema once; schemathesis will parametrize test cases from it
schema = schemathesis.from_path(SCHEMA_PATH, base_url=BASE_URL)


@schema.parametrize()
def test_api_contract(case: Case):
    """
    Auto-generated test: schemathesis creates one test per operation x strategy.
    Checks: response schema, status code is declared, no 5xx on valid input.
    """
    response = case.call()
    case.validate_response(response)


@schema.parametrize(endpoint="/orders/{order_id}", method="GET")
def test_get_order_response_shape(case: Case):
    """
    Extra assertions on GET /orders/{order_id} response shape.
    Schemathesis validates schema; we check specific fields we care about.
    """
    response = case.call()

    if response.status_code == 200:
        data = response.json()
        assert "id" in data, "id field must be present"
        assert "status" in data, "status field must be present"
        assert data["status"] in (
            "pending", "processing", "completed", "cancelled"
        ), f"unexpected status value: {data['status']}"
        assert "items" in data and isinstance(data["items"], list)
        assert len(data["items"]) >= 1, "order must have at least one item"

        for item in data["items"]:
            assert "product_id" in item
            assert "quantity" in item and item["quantity"] >= 1
            assert "unit_price" in item and item["unit_price"] >= 0

    elif response.status_code == 404:
        data = response.json()
        # error schema: code + message required
        assert "code" in data
        assert "message" in data

    else:
        case.validate_response(response)


@schema.parametrize(endpoint="/orders", method="POST")
def test_create_order_returns_201(case: Case):
    """
    POST /orders with a valid payload must return 201 with the created order.
    Schema validation happens in validate_response; this adds a check on
    the created_at field that we know downstream services depend on.
    """
    response = case.call()
    case.validate_response(response)

    if response.status_code == 201:
        data = response.json()
        assert "id" in data, "created order must have an id"
        assert "created_at" in data, "created_at must be present - downstream services use it"
        # total_amount should be non-negative
        assert data.get("total_amount", 0) >= 0


# TODO: add stateful tests once the service has stable test fixtures
# schemathesis supports stateful (links-based) testing via schema.parametrize(stateful=...)
