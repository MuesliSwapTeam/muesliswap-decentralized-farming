from fastapi import Query, Body, HTTPException, Depends
from pydantic import BaseModel, ValidationError
from typing import Optional, Type, Dict, Any, List
import inspect

MANDATORY_BODY_PARAMS = set(["utxos"])


def get_body_or_query_params(
    model_cls: Type[BaseModel],
    required_query_params: List[str],
) -> Depends:
    """
    Factory function to create a dependency that checks for the request body or query parameters.
    """
    # Get the model's field names and their default values
    model_fields = model_cls.model_fields
    query_params = {}
    for field_name, field_info in model_fields.items():
        if field_name in MANDATORY_BODY_PARAMS:
            continue
        default = Query(field_info.default if not field_info.is_required() else None)
        query_params[field_name] = (field_info.annotation, default)

    # Dynamically create the dependency function
    def dependency(
        body: Optional[Dict[str, Any]] = Body(None), **kwargs: Dict[str, Any]
    ):
        if body is not None:
            if isinstance(body, model_cls):
                return body
            try:
                return model_cls(**body)
            except TypeError:
                # FastAPI may already give us a Pydantic model-like object.
                model_dump = getattr(body, "model_dump", None)
                if callable(model_dump):
                    return model_cls(**model_dump())
                raise
            except ValidationError as e:
                raise HTTPException(status_code=422, detail=e.errors())
        # Check for missing required query parameters
        missing = [
            param for param in required_query_params if kwargs.get(param) is None
        ]
        if missing:
            raise HTTPException(
                status_code=400, detail=f"Missing required query parameters: {missing}"
            )
        # Filter kwargs to include only model fields
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in model_fields}
        try:
            return model_cls(**filtered_kwargs)
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=e.errors())

    # Set the parameters for the dependency function
    params = [
        inspect.Parameter(
            name=field_name,
            kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default=default,
            annotation=type_annotation,
        )
        for field_name, (type_annotation, default) in query_params.items()
    ]
    params.append(
        inspect.Parameter(
            name="body",
            kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default=Body(None),
            annotation=Optional[model_cls],
        )
    )
    dependency.__signature__ = inspect.Signature(parameters=params)
    return Depends(dependency)
