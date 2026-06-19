"""
Proto contract tests - validate structural guarantees without a live gRPC server.

What we check:
1. Field numbers haven't changed (breaking if they do - binary wire format depends on them)
2. Required fields are still present in messages
3. Service RPCs still exist
4. Enum has UNSPECIFIED=0 (proto3 default value safety)
5. No field types changed for critical fields

These tests parse the descriptor from the compiled *_pb2 modules.
Run the protoc command in the README to compile before running.

Note: this doesn't test actual gRPC communication. For that you'd want
a running server + a client fixture. These are schema-level checks.
"""

import importlib
import os
import sys
import pytest
from google.protobuf import descriptor as proto_descriptor

# add parent dir so we can import generated stubs
sys.path.insert(0, os.path.dirname(__file__))

# fail fast if stubs aren't compiled - common mistake
try:
    import order_pb2
    import order_pb2_grpc
except ImportError:
    pytest.skip(
        "Proto stubs not compiled. Run: "
        "python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. order.proto",
        allow_module_level=True,
    )


def get_message_descriptor(message_class) -> proto_descriptor.Descriptor:
    return message_class.DESCRIPTOR


def field_numbers(message_class) -> dict[str, int]:
    """return {field_name: field_number} for a message"""
    desc = get_message_descriptor(message_class)
    return {f.name: f.number for f in desc.fields}


def field_types(message_class) -> dict[str, int]:
    """return {field_name: FieldDescriptor.TYPE_*} for a message"""
    desc = get_message_descriptor(message_class)
    return {f.name: f.type for f in desc.fields}


class TestOrderMessage:
    """
    The Order message is the core contract. Downstream consumers depend
    on stable field numbers and presence of certain fields.
    """

    # these are the field numbers we've published - changing them is a breaking change
    EXPECTED_FIELD_NUMBERS = {
        "id": 1,
        "customer_id": 2,
        "status": 3,
        "items": 4,
        "total_amount": 5,
        "created_at_unix": 6,
        "updated_at_unix": 7,
    }

    def test_field_numbers_stable(self):
        """field numbers must not change - wire format depends on them"""
        actual = field_numbers(order_pb2.Order)
        for field, expected_num in self.EXPECTED_FIELD_NUMBERS.items():
            assert field in actual, f"field '{field}' missing from Order"
            assert actual[field] == expected_num, (
                f"Order.{field} field number changed: "
                f"expected {expected_num}, got {actual[field]}. "
                "this is a breaking change."
            )

    def test_required_fields_present(self):
        """fields that must exist - if any disappear, consumers break"""
        required = {"id", "customer_id", "status", "items", "total_amount", "created_at_unix"}
        actual = set(field_numbers(order_pb2.Order).keys())
        missing = required - actual
        assert not missing, f"required fields removed from Order: {missing}"

    def test_no_new_fields_reused_old_numbers(self):
        """
        Simplified check: make sure no field number from our known set
        is now used by a different field name. Reusing numbers = silent data corruption.
        """
        actual = field_numbers(order_pb2.Order)
        # invert: number -> name
        number_to_name = {v: k for k, v in actual.items()}
        for field, expected_num in self.EXPECTED_FIELD_NUMBERS.items():
            current_owner = number_to_name.get(expected_num)
            assert current_owner == field, (
                f"field number {expected_num} was used by '{field}', "
                f"now used by '{current_owner}'. "
                "this is a binary compatibility break."
            )

    def test_total_amount_is_double(self):
        """total_amount type must stay double - consumers parse it as float64"""
        types = field_types(order_pb2.Order)
        assert "total_amount" in types
        # TYPE_DOUBLE = 1 in protobuf FieldDescriptor
        assert types["total_amount"] == proto_descriptor.FieldDescriptor.TYPE_DOUBLE, (
            "total_amount type changed - downstream float parsing will break"
        )


class TestOrderItemMessage:
    EXPECTED_FIELD_NUMBERS = {
        "product_id": 1,
        "quantity": 2,
        "unit_price": 3,
    }

    def test_field_numbers_stable(self):
        actual = field_numbers(order_pb2.OrderItem)
        for field, expected_num in self.EXPECTED_FIELD_NUMBERS.items():
            assert field in actual, f"OrderItem.{field} missing"
            assert actual[field] == expected_num, (
                f"OrderItem.{field} field number changed to {actual[field]}"
            )


class TestOrderStatusEnum:
    def test_unspecified_is_zero(self):
        """
        proto3 default enum value must be 0. if ORDER_STATUS_UNSPECIFIED
        isn't 0, proto3 default initialization will give unexpected status values.
        """
        enum_desc = order_pb2.OrderStatus.DESCRIPTOR
        values_by_number = {v.number: v.name for v in enum_desc.values}
        assert 0 in values_by_number, "no enum value with number 0"
        assert "UNSPECIFIED" in values_by_number[0], (
            f"enum value 0 is '{values_by_number[0]}', expected *UNSPECIFIED*"
        )

    def test_known_statuses_exist(self):
        """status values downstream services use - can't disappear"""
        expected = {
            "ORDER_STATUS_PENDING": 1,
            "ORDER_STATUS_PROCESSING": 2,
            "ORDER_STATUS_COMPLETED": 3,
            "ORDER_STATUS_CANCELLED": 4,
        }
        enum_desc = order_pb2.OrderStatus.DESCRIPTOR
        actual = {v.name: v.number for v in enum_desc.values}
        for name, expected_num in expected.items():
            assert name in actual, f"enum value {name} removed"
            assert actual[name] == expected_num, (
                f"{name} enum number changed: expected {expected_num}, got {actual[name]}"
            )


class TestOrderServiceDefinition:
    """
    Check that the gRPC service still exposes the RPCs we depend on.
    We read the service descriptor from the stub class.
    """

    EXPECTED_METHODS = {"GetOrder", "CreateOrder", "ListOrders"}

    def test_service_methods_exist(self):
        service_desc = order_pb2.DESCRIPTOR.services_by_name.get("OrderService")
        assert service_desc is not None, "OrderService not found in descriptor"

        actual_methods = {m.name for m in service_desc.methods}
        missing = self.EXPECTED_METHODS - actual_methods
        assert not missing, f"OrderService RPCs removed: {missing}"

    def test_get_order_request_type(self):
        """GetOrder must still take a GetOrderRequest with order_id field 1"""
        service_desc = order_pb2.DESCRIPTOR.services_by_name["OrderService"]
        method = next((m for m in service_desc.methods if m.name == "GetOrder"), None)
        assert method is not None

        input_type = method.input_type
        assert input_type.name == "GetOrderRequest"
        fields = {f.name: f.number for f in input_type.fields}
        assert fields.get("order_id") == 1, "GetOrderRequest.order_id field number changed"

    def test_create_order_response_has_order(self):
        """CreateOrderResponse must contain an Order - consumers depend on it"""
        service_desc = order_pb2.DESCRIPTOR.services_by_name["OrderService"]
        method = next((m for m in service_desc.methods if m.name == "CreateOrder"), None)
        assert method is not None

        output_type = method.output_type
        assert output_type.name == "CreateOrderResponse"
        field_names = {f.name for f in output_type.fields}
        assert "order" in field_names, "CreateOrderResponse.order field removed"


class TestBackwardCompatSmoke:
    """
    Proto3 allows adding new optional fields without breaking old clients.
    This test makes sure we can still construct old-style messages
    (without new fields) and they serialize/deserialize cleanly.
    """

    def test_order_serializes_with_minimal_fields(self):
        """a consumer sending only id+customer_id shouldn't crash the parser"""
        order = order_pb2.Order(
            id="test-id-123",
            customer_id="cust-456",
            status=order_pb2.OrderStatus.Value("ORDER_STATUS_PENDING"),
        )
        serialized = order.SerializeToString()
        assert len(serialized) > 0

        restored = order_pb2.Order()
        restored.ParseFromString(serialized)
        assert restored.id == "test-id-123"
        assert restored.customer_id == "cust-456"

    def test_unknown_fields_round_trip(self):
        """
        Simulate a newer message being parsed by an older schema.
        Proto3 preserves unknown fields, so they should survive a round-trip.
        This is a simplified version - real test would use two proto versions.
        """
        item = order_pb2.OrderItem(product_id="p-1", quantity=2, unit_price=9.99)
        serialized = item.SerializeToString()

        parsed = order_pb2.OrderItem()
        parsed.ParseFromString(serialized)
        assert parsed.product_id == "p-1"
        assert parsed.quantity == 2

    # TODO: add version-diff test once we snapshot the old descriptor
    # (e.g. serialize FileDescriptorProto to a .bin and diff against current)
