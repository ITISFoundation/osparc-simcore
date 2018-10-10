from aiohttp import web

def login(request: web.Request):
    """
     1. Receive email and password through a /login endpoint.
     2. Check the email and password hash against the database.
     3. Create a new refresh token and JWT access token.
     4. Return both.
    """
