import base64
import json
import jwt
import uuid
import datetime
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

def create_jwk(public_pem, kid=None, rsa_alg="RS384"):
    """
    Converts an RSA public key in PEM format to a JSON Web Key (JWK).
    """
    public_key = serialization.load_pem_public_key(public_pem.encode())

    # Extract modulus (n) and exponent (e)
    numbers = public_key.public_numbers()
    n = base64.urlsafe_b64encode(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, 'big')).decode().rstrip("=")
    e = base64.urlsafe_b64encode(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, 'big')).decode().rstrip("=")

    jwk = {
        "kty": "RSA",
        "n": n,
        "e": e,
        "use": "sig",
        "alg": rsa_alg,
        "kid": kid or str(uuid.uuid4())
    }

    return jwk

def create_jwt_assertion(private_pem, aud, client_id, kid, rsa_alg="RS384"):
    """
    Generates a JWT assertion signed with an RSA private key.
    """
    # Load private key
    private_key = serialization.load_pem_private_key(private_pem.encode(), password=None)

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

    # Create signed JWT
    jwt_token = jwt.encode(payload, private_key, algorithm=rsa_alg, headers=header)
    return jwt_token

# Example Usage
if __name__ == "__main__":
    # Generate RSA key pair for testing
    private_key_obj = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key_obj.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode()

    public_pem = private_key_obj.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()

    # Generate JWK
    jwk = create_jwk(public_pem)
    print("Generated JWK:\n", json.dumps(jwk, indent=4))

    # Generate JWT assertion
    jwt_assertion = create_jwt_assertion(private_pem, "https://auth.fhirserver.com/token", "your-client-id", jwk["kid"])
    print("\nGenerated JWT Assertion:\n", jwt_assertion)
