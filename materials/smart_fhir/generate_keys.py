import base64
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from jwcrypto import jwk
import json
import hashlib
import uuid


# Step 1: Generate RSA private/public key pair
def generate_rsa_key_pair(key_size=2048):
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size
    )
    return private_key


# Step 2: Serialize keys
def serialize_keys(private_key):
    # Private key in PEM format
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')

    # Public key in PEM format
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')

    return private_pem, public_pem


# Step 3: Convert keys to JWKS
def create_jwks(private_key, kid=None):
    public_key = private_key.public_key()

    # Serialize the public key to PEM format
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    # Create a JWK object
    jwk_obj = jwk.JWK.from_pem(public_pem)

    # Generate a unique key ID based on the public key
    _kid = hashlib.sha256(public_pem).hexdigest()[:16]

    # Add additional metadata
    jwk_obj["kid"] = kid or _kid
    jwk_obj["alg"] = "RS384"  # Set the algorithm to RS384
    jwk_obj["use"] = "sig"

    jwks = {"keys": [json.loads(jwk_obj.export(private_key=False))]}
    return jwks


def verify_public_key(jwks, private_key_path):
    # Load private key
    with open(private_key_path, "rb") as f:
        private_key = serialization.load_pem_private_key(f.read(), password=None)
    
    # Extract the public key from private key
    expected_public_key = private_key.public_key()

    # Parse JWKS
    for jwk_key in jwks["keys"]:
        n = int.from_bytes(base64.urlsafe_b64decode(jwk_key["n"] + "=="), byteorder="big")
        e = int.from_bytes(base64.urlsafe_b64decode(jwk_key["e"] + "=="), byteorder="big")

        # Reconstruct public key
        public_key = rsa.RSAPublicNumbers(e, n).public_key()

        # Verify public key matches
        if public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ) == expected_public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ):
            print("Public key in JWKS matches the private key!")
        else:
            print("Public key in JWKS does NOT match the private key.")


# Main script execution
if __name__ == "__main__":
    rsa_private_key = generate_rsa_key_pair()
    private_pem, public_pem = serialize_keys(rsa_private_key)
    jwks = create_jwks(rsa_private_key, kid=str(uuid.uuid4()))
    
    # Save keys and JWKS to files
    try:
        with open("private_key.pem", "w") as private_file:
            private_file.write(private_pem)

        with open("public_key.pem", "w") as public_file:
            public_file.write(public_pem)

        with open("jwks.json", "w") as jwks_file:
            json.dump(jwks, jwks_file, indent=4)

        print("Private key, public key, and JWKS have been generated and saved:")
        print("- private_key.pem")
        print("- public_key.pem")
        print("- jwks.json")

        verify_public_key(jwks, "private_key.pem")

    except Exception as e:
        print(f"An error occurred: {e}")