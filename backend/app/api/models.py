"""
Model Management API Endpoints
List models, check status, trigger hot-swaps, view history.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends

from app.core.ml.model_registry import LiveModelRegistry, get_model_registry
from app.schemas.model import (
    ModelListResponse,
    ModelSummary,
    ModelStatusResponse,
    SwapEventResponse,
    SwapHistoryResponse,
    SwapRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/list", response_model=ModelListResponse)
async def list_models(
    registry: LiveModelRegistry = Depends(get_model_registry),
):
    """List all registered models with their versions."""
    models_dict = registry.list_models()
    models = [
        ModelSummary(name=name, **info) for name, info in models_dict.items()
    ]
    return ModelListResponse(models=models)


@router.get("/status", response_model=ModelStatusResponse)
async def get_model_status(
    registry: LiveModelRegistry = Depends(get_model_registry),
):
    """Get currently active model versions."""
    return ModelStatusResponse(active_models=registry.get_status())


@router.post("/{model_name}/activate", response_model=SwapEventResponse)
async def activate_model_version(
    model_name: str,
    request: SwapRequest,
    registry: LiveModelRegistry = Depends(get_model_registry),
):
    """Hot-swap a model to a new version.

    The new model loads in the background. Existing requests continue
    with the current version until the swap completes.
    """
    try:
        event = registry.hot_swap(model_name, request.version)
        return SwapEventResponse(
            model_name=event.model_name,
            from_version=event.from_version,
            to_version=event.to_version,
            timestamp=event.timestamp,
            status=event.status,
            error=event.error,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:  # pragma: no cover — defensive catch for unexpected errors
        logger.error(f"Error activating model: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Swap failed: {str(e)}")


@router.get("/history", response_model=SwapHistoryResponse)
async def get_swap_history(
    registry: LiveModelRegistry = Depends(get_model_registry),
):
    """Get the history of model swap events."""
    events = registry.get_swap_history()
    return SwapHistoryResponse(
        history=[
            SwapEventResponse(
                model_name=e.model_name,
                from_version=e.from_version,
                to_version=e.to_version,
                timestamp=e.timestamp,
                status=e.status,
                error=e.error,
            )
            for e in events
        ]
    )
