import os
from fastapi import APIRouter
import requests
from services.config_service import config_service
from services.db_service import db_service

#services
from services.files_service import download_file
from services.websocket_service import broadcast_init_done

router = APIRouter(prefix="/api")

# @router.get("/workspace_list")
# async def workspace_list():
#     return [{"name": entry.name, "is_dir": entry.is_dir(), "path": str(entry)} for entry in Path(WORKSPACE_ROOT).iterdir()]

async def initialize():
    # await initialize_mcp()
    await broadcast_init_done()

@router.get("/workspace_download")
async def workspace_download(path: str):
    return download_file(path)

def get_ollama_model_list():
    base_url = config_service.get_config().get('ollama', {}).get(
        'url', os.getenv('OLLAMA_HOST', 'http://localhost:11434'))
    try:
        response = requests.get(f'{base_url}/api/tags', timeout=5)
        response.raise_for_status()
        data = response.json()
        return [model['name'] for model in data.get('models', [])]
    except requests.RequestException as e:
        print(f"Error querying Ollama: {e}")
        return []


@router.get("/list_models")
async def get_models():
    config = config_service.get_config()
    res = []
    ollama_models = get_ollama_model_list()
    ollama_url = config_service.get_config().get('ollama', {}).get(
        'url', os.getenv('OLLAMA_HOST', 'http://localhost:11434'))
    print('👇ollama_models', ollama_models)
    for ollama_model in ollama_models:
        res.append({
            'provider': 'ollama',
            'model': ollama_model,
            'url': ollama_url,
            'type': 'text'
        })
    for provider in config.keys():
        models = config[provider].get('models', {})
        for model_name in models:
            if provider == 'ollama':
                continue
            if provider not in ['comfyui', 'midjourney'] and config[provider].get('api_key', '') == '':
                continue
            model = models[model_name]
            res.append({
                'provider': provider,
                'model': model_name,
                'url': config[provider].get('url', ''),
                'type': model.get('type', 'text')
            })
    return res


@router.get("/list_chat_sessions")
async def list_chat_sessions():
    return await db_service.list_sessions()


@router.get("/chat_session/{session_id}")
async def get_chat_session(session_id: str):
    return await db_service.get_chat_history(session_id)
