"""Realtrack.com authenticated session management."""

import logging

import httpx

from cleo.config import REALTRACK_BASE

logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Raised when login to Realtrack fails."""


class RealtrackSession:
    """Manages an authenticated httpx session with Realtrack.com.

    Realtrack uses server-side sessions with cookies. After a successful
    POST to ?page=login, the response body changes (shows "Successful Login!"
    and a logout link) but the URL does NOT change. All subsequent requests
    use the session cookies set during login.
    """

    def __init__(self, username: str, password: str):
        self.client = httpx.Client(
            base_url=REALTRACK_BASE,
            follow_redirects=True,
            timeout=30.0,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            },
        )
        self._login(username, password)

    def _login(self, username: str, password: str) -> None:
        """POST login form and verify success.

        The login form has three fields:
        - username (text)
        - password (password)
        - function = "login" (the submit button's name/value)

        Success is detected by checking for the logout link in the response
        body, because the URL does NOT change on successful login.
        """
        logger.info("Logging in to Realtrack...")

        resp = self.client.post(
            "/?page=login",
            data={
                "username": username,
                "password": password,
                "function": "login",
            },
        )
        resp.raise_for_status()

        # Success: response contains logout link and "Successful Login!"
        # Failure: response still shows the login form
        body = resp.text
        if "page=signout" in body and "Successful Login" in body:
            logger.info("Login successful.")
        else:
            raise AuthenticationError(
                "Login failed. Check username and password. "
                "Response did not contain logout link."
            )

    def get(self, path: str) -> httpx.Response:
        """Authenticated GET request."""
        resp = self.client.get(path)
        resp.raise_for_status()
        return resp

    def post(self, path: str, data: dict) -> httpx.Response:
        """Authenticated POST request."""
        resp = self.client.post(path, data=data)
        resp.raise_for_status()
        return resp

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
