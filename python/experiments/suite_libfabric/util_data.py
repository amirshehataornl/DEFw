import struct
import hashlib

def generate_data(size, seq_num):
	if size < 12:
		raise ValueError("Size must be at least 12 bytes")

	data = bytearray(size)

	struct.pack_into("!I", data, 0, seq_num)

	for i in range(4, size - 8):
		data[i] = (i + seq_num) % 256

	checksum = hashlib.sha256(data[:-8]).digest()[:8]

	data[-8:] = checksum

	return data

def verify_data(data):
	if len(data) < 12:
		raise ValueError("Data too small")

	seq_num = struct.unpack_from("!I", data, 0)[0]

	expected_checksum = data[-8:]

	computed_checksum = hashlib.sha256(data[:-8]).digest()[:8]

	if expected_checksum != computed_checksum:
		raise ValueError(f"Checksum mismatch! Expected: {expected_checksum.hex()}, Computed: {computed_checksum.hex()}")

	return True
