from typing import Optional

from fastapi import Query, Body, APIRouter, Header

from consts.model import ModelConnectStatusEnum, ModelResponse, ModelRequest
from database.model_management_db import create_model_record, update_model_record, delete_model_record, \
    get_model_records, get_model_by_name, get_model_by_display_name
from services.model_health_service import check_model_connectivity
from utils.model_name_utils import split_repo_name, add_repo_to_name

router = APIRouter(prefix="/model")


@router.post("/create", response_model=ModelResponse)
async def create_model(request: ModelRequest, authorization: Optional[str] = Header(None)):
    try:
        model_data = request.model_dump()
        # Split model_name
        model_repo, model_name = split_repo_name(model_data["model_name"])
        # Ensure model_repo is empty string instead of null
        model_data["model_repo"] = model_repo if model_repo else ""
        model_data["model_name"] = model_name

        if not model_data.get("display_name"):
            model_data["display_name"] = model_name

        # Use NOT_DETECTED status as default
        model_data["connect_status"] = model_data.get("connect_status") or ModelConnectStatusEnum.NOT_DETECTED.value

        # Check if display_name conflicts
        if model_data.get("display_name"):
            existing_model_by_display = get_model_by_display_name(model_data["display_name"])
            if existing_model_by_display:
                return ModelResponse(
                    code=409,
                    message=f"Name {model_data['display_name']} is already in use, please choose another display name",
                    data=None
                )

        # Check if this is a multimodal embedding model
        is_multimodal = model_data.get("model_type") == "multi_embedding"
        
        # If it's multi_embedding type, create both embedding and multi_embedding records
        if is_multimodal:
            # Create the multi_embedding record
            create_model_record(model_data)
            
            # Create the embedding record with the same data but different model_type
            embedding_data = model_data.copy()
            embedding_data["model_type"] = "embedding"
            create_model_record(embedding_data)
            
            return ModelResponse(
                code=200,
                message=f"Multimodal embedding model {add_repo_to_name(model_repo, model_name)} created successfully",
                data=None
            )
        else:
            # For non-multimodal models, just create one record
            create_model_record(model_data)
            return ModelResponse(
                code=200,
                message=f"Model {add_repo_to_name(model_repo, model_name)} created successfully",
                data=None
            )
    except Exception as e:
        return ModelResponse(
            code=500,
            message=f"Failed to create model: {str(e)}",
            data=None
        )


@router.post("/update", response_model=ModelResponse)
def update_model(request: ModelRequest, authorization: Optional[str] = Header(None)):
    try:
        model_data = request.model_dump()
        # Split model_name
        model_repo, model_name = split_repo_name(model_data["model_name"])
        # Ensure model_repo is empty string instead of null
        model_data["model_repo"] = model_repo if model_repo else ""
        model_data["model_name"] = model_name

        # Use non-empty status value
        model_data["connect_status"] = model_data.get("connect_status") or ModelConnectStatusEnum.NOT_DETECTED.value

        # Check if model exists
        existing_model = get_model_by_name(model_name, model_repo)
        if not existing_model:
            return ModelResponse(
                code=404,
                message=f"Model not found: {add_repo_to_name(model_repo, model_name)}",
                data=None
            )

        # If display name is provided and different from existing, check for duplicates
        if model_data.get("display_name") and model_data["display_name"] != existing_model.get("display_name"):
            existing_model_by_display = get_model_by_display_name(model_data["display_name"])
            if existing_model_by_display and existing_model_by_display["model_id"] != existing_model["model_id"]:
                return ModelResponse(
                    code=409,
                    message=f"Display name {model_data['display_name']} is already in use, please choose another display name",
                    data=None
                )

        # Update model record
        update_model_record(existing_model["model_id"], model_data)
        return ModelResponse(
            code=200,
            message=f"Model {add_repo_to_name(model_repo, model_name)} updated successfully",
            data={"model_name": add_repo_to_name(model_repo, model_name)}
        )
    except Exception as e:
        return ModelResponse(
            code=500,
            message=f"Failed to update model: {str(e)}",
            data=None
        )


@router.post("/delete", response_model=ModelResponse)
async def delete_model(model_name: str = Body(..., embed=True), authorization: Optional[str] = Header(None)):
    """
    Soft delete the specified model
    If the model is an embedding or multi_embedding type, both types will be deleted

    Args:
        model_name: Model name to delete. Includes model_repo, e.g.: openai/gpt-3.5-turbo
        authorization: Authorization header
    """
    try:
        # Split model_name
        model_repo, name = split_repo_name(model_name)
        # Ensure model_repo is empty string instead of null
        model_repo = model_repo if model_repo else ""
        
        # Find all models with this name and repo (sometimes can find both embedding and multi_embedding models with same repo/name)
        all_models = get_model_records({'model_name': name, 'model_repo': model_repo})
        
        if not all_models:
            return ModelResponse(
                code=404,
                message=f"Model not found: {model_name}",
                data=None
            )

        deleted_types = []
        
        # Delete all matching models (could be both embedding and multi_embedding types)
        for model in all_models:
            delete_model_record(model["model_id"])
            deleted_types.append(model.get("model_type", "unknown"))
        
        return ModelResponse(
            code=200,
            message=f"Successfully deleted model(s) in types: {', '.join(deleted_types)}",
            data={"model_name": model_name}
        )
    except Exception as e:
        return ModelResponse(
            code=500,
            message=f"Failed to delete model: {str(e)}",
            data=None
        )


@router.get("/list", response_model=ModelResponse)
async def get_model_list():
    """
    Get detailed information for all models
    """
    try:
        records = get_model_records()

        result = []
        # Use add_repo_to_name method for each record to add repo prefix to model_name
        for record in records:
            record["model_name"] = add_repo_to_name(
                model_repo=record["model_repo"],
                model_name=record["model_name"]
            )
            # Handle connect_status, use default value "Not Detected" if empty
            record["connect_status"] = ModelConnectStatusEnum.get_value(record.get("connect_status"))
            result.append(record)

        return ModelResponse(
            code=200,
            message="Successfully retrieved model list",
            data=result
        )
    except Exception as e:
        return ModelResponse(
            code=500,
            message=f"Failed to retrieve model list: {str(e)}",
            data=[]
        )


@router.get("/healthcheck", response_model=ModelResponse)
async def check_model_healthcheck(
        model_name: str = Query(..., description="Model name to check")
):
    return await check_model_connectivity(model_name)


@router.get("/get_connect_status", response_model=ModelResponse)
async def get_model_connect_status(
        model_name: str = Query(..., description="Model name")
):
    """
    Query model connection status directly from database

    Args:
        model_name: Model name to query, including repository info, e.g. openai/gpt-3.5-turbo

    Returns:
        ModelResponse: Response containing model connection status
    """
    try:
        # Split model_name
        repo, name = split_repo_name(model_name)
        # Ensure repo is empty string instead of null
        repo = repo if repo else ""

        # Query model information
        model = get_model_by_name(name, repo)
        if not model:
            return ModelResponse(
                code=404,
                message=f"Model not found: {model_name}",
                data={"connect_status": ""}
            )

        # Get connection status
        connect_status = model.get("connect_status", "")
        connect_status = ModelConnectStatusEnum.get_value(connect_status)

        return ModelResponse(
            code=200,
            message=f"Successfully retrieved connection status for model {model_name}",
            data={
                "model_name": model_name,
                "connect_status": connect_status
            }
        )
    except Exception as e:
        return ModelResponse(
            code=500,
            message=f"Failed to retrieve model connection status: {str(e)}",
            data={"connect_status": ModelConnectStatusEnum.NOT_DETECTED.value}
        )


@router.post("/update_connect_status", response_model=ModelResponse)
async def update_model_connect_status(
        model_name: str = Body(..., embed=True),
        connect_status: str = Body(..., embed=True),
        authorization: Optional[str] = Header(None)
):
    """
    Update model connection status

    Args:
        model_name: Model name, including repository info, e.g. openai/gpt-3.5-turbo
        connect_status: New connection status
        authorization: Authorization header
    """
    try:
        # Split model_name
        repo, name = split_repo_name(model_name)
        # Ensure repo is empty string instead of null
        repo = repo if repo else ""

        # Query model information
        model = get_model_by_name(name, repo)
        if not model:
            return ModelResponse(
                code=404,
                message=f"Model not found: {model_name}",
                data={"connect_status": ""}
            )

        # Update connection status
        update_data = {"connect_status": connect_status}
        update_model_record(model["model_id"], update_data)

        return ModelResponse(
            code=200,
            message=f"Successfully updated connection status for model {model_name}",
            data={
                "model_name": model_name,
                "connect_status": connect_status
            }
        )
    except Exception as e:
        return ModelResponse(
            code=500,
            message=f"Failed to update model connection status: {str(e)}",
            data={"connect_status": ModelConnectStatusEnum.NOT_DETECTED.value}
        )

