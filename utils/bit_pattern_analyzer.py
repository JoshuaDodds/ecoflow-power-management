#!/usr/bin/env python3
"""
Bit Pattern Analyzer for SOC Anomalies

Analyzes the bit patterns of anomalous SOC readings to identify potential
decoding issues like:
- Byte swapping
- Signed vs unsigned interpretation
- Bit shifting
- Multi-byte field alignment
"""

def analyze_soc_patterns():
    """Analyze the bit patterns of observed anomalous SOC values"""
    
    # Known good value
    good_soc = 90
    
    # Anomalous values from logs
    anomalous_values = [16, 24, 33, 48, 56, 65, 82, 97]
    
    print("=" * 80)
    print("BIT PATTERN ANALYSIS")
    print("=" * 80)
    
    print(f"\n✓ GOOD VALUE: {good_soc}%")
    print(f"   Binary:  {good_soc:08b} (0x{good_soc:02X})")
    print(f"   Decimal: {good_soc}")
    
    print(f"\n⚠ ANOMALOUS VALUES:")
    print(f"{'Value':<10} {'Binary':<15} {'Hex':<8} {'Bit Diff from 90':<20}")
    print("-" * 80)
    
    for val in anomalous_values:
        diff = val ^ good_soc  # XOR to see bit differences
        print(f"{val:<10} {val:08b}    0x{val:02X}    XOR: {diff:08b} (0x{diff:02X})")
    
    # Check for patterns
    print("\n" + "=" * 80)
    print("PATTERN ANALYSIS")
    print("=" * 80)
    
    # Check if values could be bit-shifted versions
    print("\n1. BIT SHIFT ANALYSIS:")
    for shift in [1, 2, 3, 4]:
        shifted_right = good_soc >> shift
        shifted_left = good_soc << shift
        print(f"   90 >> {shift} = {shifted_right:3d} (0b{shifted_right:08b})")
        print(f"   90 << {shift} = {shifted_left:3d} (0b{shifted_left:08b})")
    
    # Check if values could be from different byte interpretations
    print("\n2. BYTE INTERPRETATION:")
    # 90 as different integer types
    good_bytes = good_soc.to_bytes(8, byteorder='little')
    print(f"   90 as bytes (little-endian): {good_bytes.hex()}")
    
    # Try to reverse engineer what could produce these values
    print("\n3. REVERSE ENGINEERING ANOMALIES:")
    for val in anomalous_values:
        # What would need to happen to 90 to get this value?
        print(f"\n   {val}:")
        
        # Check if it's in the byte representation
        if val in good_bytes:
            print(f"      ✓ Found in byte stream at position {good_bytes.index(val)}")
        
        # Check bit flips
        flipped_bits = bin(val ^ good_soc).count('1')
        print(f"      Bit flips from 90: {flipped_bits}")
        
        # Check if it could be from combining with another value
        if val < good_soc:
            possible_and = val & good_soc
            possible_or = val | good_soc
            print(f"      {val} & 90 = {possible_and}")
            print(f"      {val} | 90 = {possible_or}")
    
    # Check varint encoding
    print("\n" + "=" * 80)
    print("PROTOBUF VARINT ENCODING")
    print("=" * 80)
    
    def encode_varint(value):
        """Encode value as protobuf varint"""
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
        for byte in data:
            result |= (byte & 0x7F) << shift
            if not (byte & 0x80):
                return result
            shift += 7
        return result
    
    print(f"\nVarint encoding of 90:")
    varint_90 = encode_varint(good_soc)
    print(f"   Bytes: {varint_90.hex()} = {[f'0x{b:02X}' for b in varint_90]}")
    print(f"   Binary: {' '.join([f'{b:08b}' for b in varint_90])}")
    print(f"   Decoded back: {decode_varint(varint_90)}")
    
    print(f"\nVarint encoding of anomalous values:")
    for val in anomalous_values:
        varint = encode_varint(val)
        print(f"   {val:3d}: {varint.hex()} = {[f'0x{b:02X}' for b in varint]} -> decodes to {decode_varint(varint)}")
    
    # Check if corruption could happen from partial reads
    print("\n" + "=" * 80)
    print("PARTIAL READ / CORRUPTION ANALYSIS")
    print("=" * 80)
    
    # What if we're reading the wrong bytes?
    test_buffer = bytearray([0x5A, 0x10, 0x18, 0x21, 0x30, 0x38, 0x41, 0x52, 0x61])
    print(f"\nTest buffer: {test_buffer.hex()}")
    print(f"Decimal values: {list(test_buffer)}")
    
    # Check if anomalous values appear
    for val in anomalous_values:
        if val in test_buffer:
            idx = test_buffer.index(val)
            print(f"   ✓ {val} found at index {idx} (0x{val:02X})")

if __name__ == "__main__":
    analyze_soc_patterns()
