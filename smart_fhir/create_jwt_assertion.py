import base64
import json
import jwt
import uuid
import datetime
from cryptography.hazmat.primitives import serialization

print(jwt.__version__)

def load_private_key_from_file(file_path):
    """
    Loads an RSA private key from a PEM file.
    """
    with open(file_path, "rb") as key_file:
        private_key = serialization.load_pem_private_key(
            key_file.read(),
            password=None  # Use password if the key is encrypted
        )
    return private_key


def create_jwt_assertion(private_key, aud, client_id, kid, rsa_alg="RS384"):
    """
    Generates a JWT assertion signed with an RSA private key.
    """
    # JWT Header
    header = {
        "alg": rsa_alg,
        "typ": "JWT",
        "kid": kid
    }

    # JWT Payload
    epoch_now = int(datetime.datetime.utcnow().timestamp())
    epoch_exp = epoch_now + (60 * 4)  # Expiry in 4 minutes

    payload = {
        "iss": client_id,
        "sub": client_id,
        "aud": aud,
        "jti": str(uuid.uuid4()),
        "exp": epoch_exp,
        "nbf": epoch_now,
        "iat": epoch_now
    }

    # Extract private key in PEM format
    pem_private_key = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    # Create signed JWT
    jwt_token = jwt.encode(payload, private_key, algorithm=rsa_alg, headers=header)
    return jwt_token


# Example Usage
if __name__ == "__main__":
    private_key_path = "private_key.pem"  # Update with the actual path to your PEM file

    # Load the private key from the local file
    private_key = load_private_key_from_file(private_key_path)

    # Generate JWT assertion
    jwt_assertion = create_jwt_assertion(private_key, "https://auth.fhirserver.com/token", "your-client-id", "your-kid")
    
    print("\nGenerated JWT Assertion:\n", jwt_assertion)
