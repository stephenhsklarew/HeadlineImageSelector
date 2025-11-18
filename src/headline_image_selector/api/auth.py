"""
Authentication middleware for Cloud Run with IAP (Identity-Aware Proxy)
"""

import logging
import os
from typing import Optional

from fastapi import Header, HTTPException, Request
from google.auth.transport import requests
from google.oauth2 import id_token

logger = logging.getLogger(__name__)


class IAPAuth:
    """
    Identity-Aware Proxy authentication handler

    Automatically detects if running locally or on Cloud Run:
    - Local: Authentication disabled (for development)
    - Cloud Run: Enforces IAP authentication
    """

    def __init__(self):
        # Detect environment
        self.is_cloud_run = os.getenv("K_SERVICE") is not None
        self.require_auth = os.getenv("REQUIRE_AUTH", "auto").lower()

        # Get expected audience for IAP (Cloud Run service URL)
        self.expected_audience = os.getenv("IAP_AUDIENCE")

        # Get allowed domain from environment
        self.allowed_domain = os.getenv("ALLOWED_DOMAIN")

        if self.require_auth == "auto":
            self.auth_enabled = self.is_cloud_run
        else:
            self.auth_enabled = self.require_auth == "true"

        if self.auth_enabled:
            logger.info(f"🔒 IAP Authentication ENABLED")
            if self.allowed_domain:
                logger.info(f"   Allowed domain: {self.allowed_domain}")
            else:
                logger.warning("   No ALLOWED_DOMAIN set - all authenticated users allowed")
        else:
            logger.info("🔓 IAP Authentication DISABLED (local development mode)")

    async def verify_request(
        self,
        request: Request,
        authorization: Optional[str] = Header(None),
    ) -> Optional[dict]:
        """
        Verify the request is authenticated via IAP

        Args:
            request: FastAPI request object
            authorization: Authorization header

        Returns:
            User info dict if authenticated, None if auth disabled

        Raises:
            HTTPException: If authentication required but fails
        """
        # Skip auth if disabled (local development)
        if not self.auth_enabled:
            return None

        # Skip auth for health checks
        if request.url.path in ["/health", "/docs", "/redoc", "/openapi.json"]:
            return None

        # Get IAP JWT from header
        iap_jwt = request.headers.get("x-goog-iap-jwt-assertion")

        if not iap_jwt:
            # Try authorization header as fallback
            if authorization and authorization.startswith("Bearer "):
                iap_jwt = authorization.replace("Bearer ", "")
            else:
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required. Please access through IAP-protected URL."
                )

        try:
            # Verify JWT token
            if self.expected_audience:
                # Verify with specific audience
                user_info = id_token.verify_oauth2_token(
                    iap_jwt,
                    requests.Request(),
                    audience=self.expected_audience
                )
            else:
                # Verify without audience check (less secure but works)
                user_info = id_token.verify_token(
                    iap_jwt,
                    requests.Request()
                )

            # Check domain restriction if configured
            if self.allowed_domain:
                email = user_info.get("email", "")
                if not email.endswith(f"@{self.allowed_domain}"):
                    logger.warning(f"Access denied for {email} - not in allowed domain")
                    raise HTTPException(
                        status_code=403,
                        detail=f"Access restricted to {self.allowed_domain} domain"
                    )

            logger.info(f"Authenticated user: {user_info.get('email', 'unknown')}")
            return user_info

        except ValueError as e:
            logger.error(f"Token verification failed: {e}")
            raise HTTPException(
                status_code=401,
                detail=f"Invalid authentication token: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise HTTPException(
                status_code=401,
                detail="Authentication failed"
            )


# Global auth instance
iap_auth = IAPAuth()


async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None)
) -> Optional[dict]:
    """
    FastAPI dependency to get current authenticated user

    Usage:
        @app.get("/api/endpoint")
        async def endpoint(user: dict = Depends(get_current_user)):
            email = user.get("email") if user else "anonymous"
            ...
    """
    return await iap_auth.verify_request(request, authorization)
