import os
import boto3
import hmac
import hashlib
import base64
import json
from jose import jwk, jwt
from jose.utils import base64url_decode
from urllib.request import urlopen

def get_token(username, password, client_id):
    """Get JWT token from Cognito"""
    client = boto3.client('cognito-idp')
    
    # This is the authentication flow for user password auth
    auth_params = {
        'USERNAME': username,
        'PASSWORD': password
    }
    
    response = client.initiate_auth(
        ClientId=client_id,
        AuthFlow='USER_PASSWORD_AUTH',
        AuthParameters=auth_params
    )
    
    return response['AuthenticationResult']['IdToken']

def verify_token(token, user_pool_id):
    """Verify the JWT token from Cognito"""
    if not token:
        return False
        
    # Get the region from the user pool ID
    region = user_pool_id.split('_')[0]
    
    # Get the JWKs from Cognito
    keys_url = f'https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json'
    
    try:
        with urlopen(keys_url) as f:
            response = f.read()
        keys = json.loads(response.decode('utf-8'))['keys']
        
        # Get the kid from the token
        headers = jwt.get_unverified_headers(token)
        kid = headers['kid']
        
        # Find the key with the matching kid
        key = next((k for k in keys if k['kid'] == kid), None)
        if not key:
            return False
            
        # Verify the signature
        public_key = jwk.construct(key)
        message, encoded_signature = token.rsplit('.', 1)
        decoded_signature = base64url_decode(encoded_signature.encode('utf-8'))
        
        # Verify the signature
        if not public_key.verify(message.encode('utf-8'), decoded_signature):
            return False
            
        # Verify the claims
        claims = jwt.get_unverified_claims(token)
        if claims['exp'] < import_time():
            return False
            
        return True
    except Exception as e:
        print(f"Token verification error: {str(e)}")
        return False

def import_time():
    """Import time module and return current time"""
    import time
    return int(time.time())