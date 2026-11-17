from fastapi import APIRouter, HTTPException

from .collector_registry import COLLECTORS, get_operation

router = APIRouter(prefix="/collectors", tags=["collectors"])


def serialize_operation(operation) -> dict:
    return {
        "key": operation.key,
        "name": operation.name,
        "description": operation.description,
        "purpose": operation.purpose,
        "parameters": [
            {
                "name": parameter.name,
                "data_type": parameter.data_type,
                "required": parameter.required,
                "description": parameter.description,
            }
            for parameter in operation.parameters
        ],
        "datasets": list(operation.datasets),
        "joint": len(operation.datasets) > 1,
    }


@router.get("")
def list_collectors() -> list[dict]:
    return [
        {
            "key": collector.key,
            "name": collector.name,
            "description": collector.description,
            "operations": [serialize_operation(item) for item in collector.operations.values()],
        }
        for collector in COLLECTORS.values()
    ]


@router.get("/{collector_key}/operations/{operation_key}")
def get_collector_operation(collector_key: str, operation_key: str) -> dict:
    operation = get_operation(collector_key, operation_key)
    if operation is None:
        raise HTTPException(status_code=404, detail="collector operation not found")
    return serialize_operation(operation)
