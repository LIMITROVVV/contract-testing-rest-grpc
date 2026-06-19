# gRPC contract tests

Tests proto schema stability without needing a live gRPC server. Parses the compiled descriptor and checks field numbers, message structure, enum values, and service method signatures.

## Compile stubs first

```bash
# from the grpc/ directory
python -m grpc_tools.protoc \
  -I. \
  --python_out=. \
  --grpc_python_out=. \
  order.proto
```

This generates `order_pb2.py` and `order_pb2_grpc.py`. Both are in `.gitignore` - they're build artifacts.

## Run tests

```bash
pytest test_proto_contract.py -v
```

## What's checked

- **Field numbers** - proto wire format encodes field numbers, not names. Renaming a field is fine; changing its number breaks binary compatibility silently.
- **Required fields** - fields that downstream consumers read must still be there.
- **Enum values** - `ORDER_STATUS_UNSPECIFIED = 0` must stay at 0 (proto3 default). Known enum values must keep their numbers.
- **Service methods** - `GetOrder`, `CreateOrder`, `ListOrders` must not disappear.
- **Round-trip serialization** - messages serialize/deserialize cleanly.

## Notes

This is a lighter alternative to `buf breaking` for teams that don't want another tool in the chain. The tradeoff: you maintain the `EXPECTED_FIELD_NUMBERS` dicts by hand. If your team grows or you have many protos, buf is worth it.

For testing actual gRPC communication (not just the schema), you'd add a fixture that starts the server in a subprocess or uses a test double. That's out of scope here.
