import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

# Generate a new private key using the P-256 curve
private_key = ec.generate_private_key(ec.SECP256R1())

# Get the corresponding public key
public_key = private_key.public_key()

# VAPID keys need to be URL-safe base64 encoded and without padding
def urlsafe_b64encode_nopad(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')

# Serialize the public key in the required uncompressed format.
# This is the modern, correct replacement for the deprecated `encode_point`.
public_key_bytes = public_key.public_bytes(
    encoding=serialization.Encoding.X962,
    format=serialization.PublicFormat.UncompressedPoint
)

# Serialize the private key to get its raw value.
private_key_bytes = private_key.private_numbers().private_value.to_bytes(32, byteorder="big")

print("\n✅ Successfully generated your VAPID keys!")
print("="*40)
print(f"Public Key:  {urlsafe_b64encode_nopad(public_key_bytes)}")
print(f"Private Key: {urlsafe_b64encode_nopad(private_key_bytes)}")
print("="*40)
print("\nCopy these keys into your .env file.\n")