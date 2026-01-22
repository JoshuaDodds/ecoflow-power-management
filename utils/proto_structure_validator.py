#!/usr/bin/env python3
"""
Protobuf Structure Validator

Tests the protobuf parsing logic to identify structural issues:
1. Verifies varint encoding/decoding
2. Tests recursive message parsing
3. Checks for field collision/duplication
4. Validates tag extraction
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.lib.ecoflow_river3plus import EcoFlowDevice

def test_varint_encoding():
    """Test varint encoding/decoding"""
    print("=" * 80)
    print("VARINT ENCODING TESTS")
    print("=" * 80)
    
    test_values = [0, 1, 90, 127, 128, 255, 256, 16383, 16384]
    
    def encode_varint(value):
        """Encode as protobuf varint"""
        result = []
        while value > 0x7F:
            result.append((value & 0x7F) | 0x80)
            value >>= 7
        result.append(value & 0x7F)
        return bytes(result)
    
    def decode_varint(data):
        """Decode protobuf varint"""
        result = 0
        shift = 0
        for i, byte in enumerate(data):
            result |= (byte & 0x7F) << shift
            if not (byte & 0x80):
                return result, i + 1
            shift += 7
        raise ValueError("Truncated varint")
    
    for val in test_values:
        encoded = encode_varint(val)
        decoded, bytes_consumed = decode_varint(encoded)
        status = "✓" if decoded == val else "✗"
        print(f"{status} Value {val:6d}: encoded={encoded.hex():12s} decoded={decoded:6d} (consumed {bytes_consumed} bytes)")

def test_tag_field_extraction():
    """Test how tags are decoded into field numbers"""
    print("\n" + "=" * 80)
    print("TAG -> FIELD EXTRACTION")
    print("=" * 80)
    
    # Tag format: (field_number << 3) | wire_type
    # Wire types: 0=varint, 1=64bit, 2=length-delimited, 5=32bit
    
    test_cases = [
        (0x30, "field 6, wire type 0 (varint) - SOC"),
        (0x08, "field 1, wire type 0 (varint)"),
        (0x10, "field 2, wire type 0 (varint)"),
        (0xD8, "field 27, wire type 0 (varint) - Grid"),
        (0xE0, "field 28, wire type 0 (varint) - Power"),
    ]
    
    for tag_byte, description in test_cases:
        field = tag_byte >> 3
        wtype = tag_byte & 0x7
        print(f"Tag 0x{tag_byte:02X} = {tag_byte:3d} -> Field {field:2d}, Wire Type {wtype} ({description})")

def test_message_parsing_simple():
    """Test simple protobuf message parsing"""
    print("\n" + "=" * 80)
    print("SIMPLE MESSAGE PARSING")
    print("=" * 80)
    
    # Construct a simple test message with known values
    # Field 6 (SOC) = 90
    # Tag: (6 << 3) | 0 = 0x30
    # Value: 90 = 0x5A
    
    test_message = bytes([0x30, 0x5A])  # Tag 6, value 90
    print(f"Test message: {test_message.hex()} (field 6 = 90)")
    
    device = EcoFlowDevice("TEST")
    messages = device._parse_proto_structure(test_message)
    
    print(f"Parsed messages: {messages}")
    
    if messages and 6 in messages[0]:
        print(f"✓ Field 6 extracted correctly: {messages[0][6]}")
    else:
        print(f"✗ Field 6 NOT found in parsed messages!")

def test_nested_message_parsing():
    """Test nested/recursive message parsing"""
    print("\n" + "=" * 80)
    print("NESTED MESSAGE PARSING")
    print("=" * 80)
    
    # Create a length-delimited message containing a sub-message
    # Outer: Field 1, wire type 2 (length-delimited)
    # Inner: Field 6, value 90
    
    inner = bytes([0x30, 0x5A])  # Field 6 = 90
    outer = bytes([0x0A, len(inner)]) + inner  # Field 1, length-delimited
    
    print(f"Outer message: {outer.hex()}")
    print(f"  - Field 1 (length-delimited)")
    print(f"  - Inner: {inner.hex()} (field 6 = 90)")
    
    device = EcoFlowDevice("TEST")
    messages = device._parse_proto_structure(outer)
    
    print(f"\nParsed messages: {messages}")
    
    # Check if field 6 was extracted from nested message
    found_field6 = any(6 in msg for msg in messages)
    if found_field6:
        print("✓ Field 6 found in nested message")
        for i, msg in enumerate(messages):
            if 6 in msg:
                print(f"  Message {i}: Field 6 = {msg[6]}")
    else:
        print("✗ Field 6 NOT found in nested message!")

def test_multiple_fields():
    """Test message with multiple fields"""
    print("\n" + "=" * 80)
    print("MULTIPLE FIELDS IN SAME MESSAGE")
    print("=" * 80)
    
    # Field 6 = 90, Field 27 = 0, Field 28 = 100
    message = bytes([
        0x30, 0x5A,  # Field 6 = 90 (SOC)
        0xD8, 0x01, 0x00,  # Field 27 = 0 (Grid connected)
        0xE0, 0x01, 0x64,  # Field 28 = 100 (Power * 10)
    ])
    
    print(f"Test message: {message.hex()}")
    
    device = EcoFlowDevice("TEST")
    messages = device._parse_proto_structure(message)
    
    print(f"Parsed messages: {messages}")
    
    if messages:
        msg = messages[0]
        print(f"\nExtracted fields:")
        if 6 in msg:
            print(f"  ✓ Field 6 (SOC): {msg[6]}")
        if 27 in msg:
            print(f"  ✓ Field 27 (Grid): {msg[27]}")
        if 28 in msg:
            print(f"  ✓ Field 28 (Power): {msg[28]}")

def test_real_world_scenario():
    """Test scenario that might cause the bug"""
    print("\n" + "=" * 80)
    print("REAL-WORLD BUG SCENARIO")
    print("=" * 80)
    
    # Hypothesis: When there are multiple nested messages with field 6,
    # the parser might be picking up the wrong one or creating duplicates
    
    # Create message with TWO different field 6 values in nested structures
    inner1 = bytes([0x30, 0x5A])  # Field 6 = 90
    inner2 = bytes([0x30, 0x10])  # Field 6 = 16  <-- ANOMALOUS VALUE!
    
    # Wrap both in outer containers
    message = (
        bytes([0x0A, len(inner1)]) + inner1 +  # Field 1, length-delimited
        bytes([0x12, len(inner2)]) + inner2    # Field 2, length-delimited
    )
    
    print(f"Test message with TWO field 6 values:")
    print(f"  Inner1: field 6 = 90")
    print(f"  Inner2: field 6 = 16")
    print(f"  Raw hex: {message.hex()}")
    
    device = EcoFlowDevice("TEST")
    messages = device._parse_proto_structure(message)
    
    print(f"\nParsed messages: {messages}")
    print(f"Number of messages extracted: {len(messages)}")
    
    # Check which field 6 values were extracted
    field6_values = [msg.get(6) for msg in messages if 6 in msg]
    print(f"Field 6 values found: {field6_values}")
    
    if len(field6_values) > 1:
        print("⚠️  WARNING: Multiple field 6 values detected!")
        print("   This could cause the SOC to jump between different values!")

if __name__ == "__main__":
    test_varint_encoding()
    test_tag_field_extraction()
    test_message_parsing_simple()
    test_nested_message_parsing()
    test_multiple_fields()
    test_real_world_scenario()
    
    print("\n" + "=" * 80)
    print("TEST SUITE COMPLETE")
    print("=" * 80)
