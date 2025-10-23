"""
Custom OpenAPI schema generation with OPTIONS method support.
"""
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute


def custom_openapi_schema(app: FastAPI) -> Dict[str, Any]:
    """
    Generate custom OpenAPI schema that includes OPTIONS methods for all endpoints.

    This function extends the default OpenAPI schema generation to automatically
    add OPTIONS methods for all defined endpoints, which is useful for CORS
    preflight requests and API documentation completeness.

    Args:
        app: The FastAPI application instance

    Returns:
        Dict containing the complete OpenAPI schema with OPTIONS methods
    """
    if app.openapi_schema:
        return app.openapi_schema

    # Generate the base OpenAPI schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Add OPTIONS methods to all paths
    paths = openapi_schema.get("paths", {})

    for path, path_item in paths.items():
        # Skip if OPTIONS already exists
        if "options" in path_item:
            continue

        # Get all existing methods for this path
        existing_methods = [method.upper() for method in path_item.keys()
                          if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]]

        if existing_methods:
            # Create OPTIONS method definition
            options_definition = {
                "summary": f"CORS preflight for {path}",
                "description": f"Handle CORS preflight requests for {path}. "
                             f"Supports methods: {', '.join(existing_methods)}",
                "operationId": f"options_{path.replace('/', '_').replace('{', '').replace('}', '').strip('_')}",
                "tags": _get_tags_from_path_item(path_item),
                "responses": {
                    "200": {
                        "description": "CORS preflight response",
                        "headers": {
                            "Access-Control-Allow-Origin": {
                                "description": "Allowed origins for CORS",
                                "schema": {"type": "string"}
                            },
                            "Access-Control-Allow-Methods": {
                                "description": "Allowed HTTP methods",
                                "schema": {"type": "string"}
                            },
                            "Access-Control-Allow-Headers": {
                                "description": "Allowed headers for CORS",
                                "schema": {"type": "string"}
                            },
                            "Access-Control-Max-Age": {
                                "description": "Maximum age for preflight cache",
                                "schema": {"type": "integer"}
                            }
                        }
                    },
                    "204": {
                        "description": "No content - successful preflight",
                        "headers": {
                            "Access-Control-Allow-Origin": {
                                "description": "Allowed origins for CORS",
                                "schema": {"type": "string"}
                            },
                            "Access-Control-Allow-Methods": {
                                "description": "Allowed HTTP methods",
                                "schema": {"type": "string"}
                            },
                            "Access-Control-Allow-Headers": {
                                "description": "Allowed headers for CORS",
                                "schema": {"type": "string"}
                            }
                        }
                    }
                },
                "parameters": [
                    {
                        "name": "Origin",
                        "in": "header",
                        "description": "Origin of the request",
                        "required": False,
                        "schema": {"type": "string"}
                    },
                    {
                        "name": "Access-Control-Request-Method",
                        "in": "header",
                        "description": "Method that will be used in the actual request",
                        "required": False,
                        "schema": {"type": "string"}
                    },
                    {
                        "name": "Access-Control-Request-Headers",
                        "in": "header",
                        "description": "Headers that will be used in the actual request",
                        "required": False,
                        "schema": {"type": "string"}
                    }
                ]
            }

            # Add the OPTIONS method to the path
            path_item["options"] = options_definition

    # Cache the schema
    app.openapi_schema = openapi_schema
    return openapi_schema


def _get_tags_from_path_item(path_item: Dict[str, Any]) -> List[str]:
    """
    Extract tags from the first available method in a path item.

    Args:
        path_item: OpenAPI path item dictionary

    Returns:
        List of tags for the path
    """
    for method_name, method_info in path_item.items():
        if isinstance(method_info, dict) and "tags" in method_info:
            return method_info["tags"]
    return []


def setup_custom_openapi(app: FastAPI) -> None:
    """
    Setup custom OpenAPI schema generation for the FastAPI app.

    Args:
        app: The FastAPI application instance
    """
    def custom_openapi():
        return custom_openapi_schema(app)

    app.openapi = custom_openapi
