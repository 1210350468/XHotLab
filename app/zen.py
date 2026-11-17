import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx
import keyring

from .config import ROOT

MODEL_URL = 'https://opencode.ai/inference/v1/models'
GATEWAYS = {
    'payg': 'https://opencode.ai/inference/openai/v1/chat/completions',
    'go': 'https://opencode.ai/inference/go/openai/v1/chat/completions',
}
KEYRING_SERVICE = 'XHotLab OpenCode Console'
KEYRING_NAME = 'personal'
CATALOG_FILE = ROOT / 'data' / 'zen_models.json'
SETTINGS_FILE = ROOT / 'data' / 'zen_settings.json'
DEFAULTS = {
    'plan': 'payg',
    'compose_model': 'glm-5.3-flash',
    'chat_model': 'glm-5.3-flash',
    'compose_effort': 'low',
    'chat_effort': 'low',
}


def get_api_key() -> str:
    return keyring.get_password(KEYRING_SERVICE, KEYRING_NAME) or ''


def save_api_key(value: str) -> None:
    value = value.strip()
    if not value.startswith('oc_sk_') or len(value) < 28:
        raise ValueError('需要有效的 OpenCode Console API Key')
    keyring.set_password(KEYRING_SERVICE, KEYRING_NAME, value)


def settings() -> dict:
    if SETTINGS_FILE.exists():
        saved = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
    else:
        saved = {}
    return {**DEFAULTS, **saved, 'key_configured': bool(get_api_key())}


def update_settings(values: dict) -> dict:
    current = settings()
    new = {key: current[key] for key in DEFAULTS}
    new.update(values)
    if new['plan'] not in GATEWAYS:
        raise ValueError('OpenCode 使用模式只能选择 payg 或 go')
    if not all(isinstance(new[key], str) and new[key].strip()
               for key in ('chat_model', 'compose_model')):
        raise ValueError('请指定有效的聊天模型和写稿模型')
    for key in ('chat_effort', 'compose_effort'):
        if new[key] not in ('none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max'):
            raise ValueError('思考强度参数无效')
    if not CATALOG_FILE.exists():
        raise ValueError('请先导入 OpenCode 官方模型目录')
    models = {model['id']: model for model in json.loads(CATALOG_FILE.read_text(encoding='utf-8'))['models']}
    for role in ('chat', 'compose'):
        model_id = new[role + '_model']
        if model_id not in models:
            raise ValueError(f'{role} 选择的模型不在官方目录中')
        if models[model_id]['free_restricted']:
            raise ValueError(f'{model_id} 只能在 OpenCode 内使用')
        effort = new[role + '_effort']
        if effort != 'none' and effort not in models[model_id]['efforts']:
            raise ValueError(f'{model_id} 不支持思考强度 {effort}')
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(new, ensure_ascii=False, indent=2), encoding='utf-8')
    return settings()


def _normalize_model(item: dict) -> dict:
    capabilities = item.get('capabilities') or {}
    reasoning = capabilities.get('reasoning') or {}
    if not isinstance(reasoning, dict):
        reasoning = {'supported': bool(reasoning)}
    efforts = reasoning.get('effort') or []
    cost = (item.get('cost') or {}).get('text') or {}
    input_cost = (cost.get('input') or {}).get('price')
    output_cost = (cost.get('output') or {}).get('price')
    api_families = list((item.get('api') or {}).keys())
    free = (input_cost == 0 and output_cost == 0)
    return {
        'id': item['id'],
        'name': item.get('name') or item['id'],
        'family': item.get('family') or '',
        'description': item.get('description') or '',
        'context': (item.get('limit') or {}).get('context'),
        'output_limit': (item.get('limit') or {}).get('output'),
        'input_price': input_cost,
        'output_price': output_cost,
        'reasoning': bool(reasoning.get('supported')),
        'efforts': efforts,
        'temperature': bool(capabilities.get('temperature')),
        'native_api': api_families[0] if api_families else '',
        'free_restricted': free,
    }


async def refresh_catalog() -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(MODEL_URL)
        response.raise_for_status()
    payload = response.json()
    models = [_normalize_model(value) for value in payload['data']]
    if not models:
        raise ValueError('OpenCode 返回了空模型列表')
    result = {
        'models': sorted(models, key=lambda model: model['name'].casefold()),
        'total': len(models),
        'updated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'source': MODEL_URL,
    }
    CATALOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


async def catalog() -> dict:
    if not CATALOG_FILE.exists():
        return await refresh_catalog()
    return json.loads(CATALOG_FILE.read_text(encoding='utf-8'))


async def get_model(model_id: str) -> dict:
    listing = await catalog()
    for model in listing['models']:
        if model['id'] == model_id:
            return model
    raise ValueError('选择的模型不在 OpenCode 当前模型列表中，请刷新模型列表')


async def complete(messages: list[dict], model_id: str | None = None,
                   effort: str | None = None, session_id: str | None = None,
                   max_tokens: int | None = None) -> dict:
    options = settings()
    key = get_api_key()
    if not key:
        raise ValueError('请在「Zen 设置」中连接 OpenCode Console API Key')
    model_id = model_id or options['chat_model']
    model = await get_model(model_id)
    if model['free_restricted']:
        raise ValueError('此免费模型只能在 OpenCode 内使用，请选择有 API 价格的模型')
    effort = effort or 'none'
    if effort != 'none' and effort not in model['efforts']:
        raise ValueError(f'模型 {model_id} 的思考强度支持范围：{model["efforts"]}')
    payload = {'model': model_id, 'messages': messages, 'stream': False}
    if max_tokens is not None:
        payload['max_tokens'] = max_tokens
    if effort != 'none':
        payload['reasoning_effort'] = effort
    headers = {
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json',
        'x-opencode-session': session_id or f'ses_{uuid4().hex}',
    }
    async with httpx.AsyncClient(timeout=100) as client:
        response = await client.post(GATEWAYS[options['plan']], headers=headers, json=payload)
        response.raise_for_status()
    data = response.json()
    content = data['choices'][0]['message']['content']
    if not isinstance(content, str) or not content.strip():
        raise ValueError('模型返回的正文为空')
    usage = data.get('usage') or {}
    return {
        'text': content.strip(),
        'model': data.get('model') or model_id,
        'usage': {
            'input_tokens': usage.get('prompt_tokens', 0),
            'output_tokens': usage.get('completion_tokens', 0),
            'cost_usd': usage.get('cost'),
            'billing_source': (usage.get('opencode') or {}).get('billing_source'),
        },
    }


async def check_connection() -> dict:
    options = settings()
    result = await complete(
        [{'role': 'user', 'content': 'Reply with exactly: OK'}],
        options['compose_model'],
        options['compose_effort'],
        max_tokens=80,
    )
    return {'ok': True, **result}
