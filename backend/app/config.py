"""
配置管理
统一从项目根目录的 .env 文件加载配置
"""

import os
from dotenv import load_dotenv

# 加载项目根目录的 .env 文件
# 路径: MiroFish/.env (相对于 backend/app/config.py)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    # 如果根目录没有 .env，尝试加载环境变量（用于生产环境）
    load_dotenv(override=True)


class Config:
    """Flask配置类"""
    
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY', 'mirofish-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # JSON配置 - 禁用ASCII转义，让中文直接显示（而不是 \uXXXX 格式）
    JSON_AS_ASCII = False
    
    # LLM配置（统一使用OpenAI格式）
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')
    
    # Zep配置
    ZEP_API_KEY = os.environ.get('ZEP_API_KEY')
    
    # 文件上传配置
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}
    
    # 文本处理配置
    DEFAULT_CHUNK_SIZE = 500  # 默认切块大小
    DEFAULT_CHUNK_OVERLAP = 50  # 默认重叠大小
    
    # OASIS模拟配置
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')
    
    # OASIS平台可用动作配置
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]
    
    # Report Agent配置
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))

    # ----- API auth (Cognito + DynamoDB ownership) -----
    # Set AUTH_ENABLED=true to require Authorization: Bearer <JWT> on /api/* and enforce DynamoDB ownership.
    AUTH_ENABLED = os.environ.get('AUTH_ENABLED', 'false').lower() == 'true'
    COGNITO_REGION = os.environ.get('COGNITO_REGION') or os.environ.get('AWS_REGION', 'us-east-1')
    COGNITO_USER_POOL_ID = os.environ.get('COGNITO_USER_POOL_ID', '')
    COGNITO_APP_CLIENT_ID = os.environ.get('COGNITO_APP_CLIENT_ID', '')
    COGNITO_JWKS_CACHE_SECONDS = int(os.environ.get('COGNITO_JWKS_CACHE_SECONDS', '3600'))
    AWS_REGION = os.environ.get('AWS_REGION', '') or COGNITO_REGION
    # Optional: LocalStack / custom endpoint
    AWS_DYNAMODB_ENDPOINT_URL = (os.environ.get('AWS_DYNAMODB_ENDPOINT_URL') or '').strip() or None
    AUTH_DYNAMODB_TABLE_NAME = os.environ.get('AUTH_DYNAMODB_TABLE_NAME', '')
    # Partition key attribute for lookups (override per resource if your table uses different key names).
    AUTH_DYNAMODB_PK_ATTRIBUTE = os.environ.get('AUTH_DYNAMODB_PK_ATTRIBUTE', 'id')
    AUTH_DYNAMODB_USER_SUB_ATTRIBUTE = os.environ.get('AUTH_DYNAMODB_USER_SUB_ATTRIBUTE', 'userSub')
    AUTH_DYNAMODB_SIMULATION_PK_ATTRIBUTE = os.environ.get('AUTH_DYNAMODB_SIMULATION_PK_ATTRIBUTE', '')
    AUTH_DYNAMODB_PROJECT_PK_ATTRIBUTE = os.environ.get('AUTH_DYNAMODB_PROJECT_PK_ATTRIBUTE', '')
    AUTH_DYNAMODB_GRAPH_PK_ATTRIBUTE = os.environ.get('AUTH_DYNAMODB_GRAPH_PK_ATTRIBUTE', '')

    # 可选：任务与模拟运行状态快照表（多进程/多实例时与本地文件一并写入，供其他实例读取）
    # 表结构：PK id (String)，属性 entity_type (TASK|RUN)、payload (JSON 字符串)、updated_at
    DYNAMODB_APP_STATE_TABLE_NAME = (
        os.environ.get('DYNAMODB_APP_STATE_TABLE_NAME') or ""
    ).strip() or None

    # ----- Distributed execution (multi-host) -----
    # When enabled, API can enqueue simulation-start jobs to SQS and workers execute them.
    DISTRIBUTED_EXECUTION_ENABLED = os.environ.get(
        'DISTRIBUTED_EXECUTION_ENABLED', 'false'
    ).lower() == 'true'
    # Workers set this true to consume queue messages and launch local subprocesses.
    SIMULATION_WORKER_MODE = os.environ.get(
        'SIMULATION_WORKER_MODE', 'false'
    ).lower() == 'true'
    # Shared artifact storage for simulation files (state/config/profiles/run_state).
    S3_SIMULATION_BUCKET = (os.environ.get('S3_SIMULATION_BUCKET') or '').strip() or None
    S3_SIMULATION_PREFIX = (os.environ.get('S3_SIMULATION_PREFIX') or 'simulations').strip()
    # SQS queue URL for simulation start jobs.
    SQS_SIMULATION_START_QUEUE_URL = (
        os.environ.get('SQS_SIMULATION_START_QUEUE_URL') or ""
    ).strip() or None
    # Worker polling interval for SQS long-poll loop.
    SIMULATION_WORKER_POLL_SECONDS = int(
        os.environ.get('SIMULATION_WORKER_POLL_SECONDS', '5')
    )

    # CORS：生产环境设置 CORS_ALLOWED_ORIGINS（逗号分隔），勿用 *。留空则仍为 *（便于本地开发）
    # 例：https://app.vercel.app,http://localhost:3000
    _cors_raw = (os.environ.get('CORS_ALLOWED_ORIGINS') or '').strip()
    if _cors_raw:
        CORS_ORIGINS = [o.strip() for o in _cors_raw.split(',') if o.strip()]
    else:
        CORS_ORIGINS = '*'
    # fetch(..., credentials: 'include') 或 Cookie 跨站时需要；且浏览器禁止 * + credentials 组合
    CORS_SUPPORTS_CREDENTIALS = os.environ.get(
        'CORS_SUPPORTS_CREDENTIALS', 'false'
    ).lower() == 'true'
    
    @classmethod
    def validate(cls):
        """验证必要配置"""
        errors = []
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY 未配置")
        if not cls.ZEP_API_KEY:
            errors.append("ZEP_API_KEY 未配置")
        if cls.AUTH_ENABLED:
            if not cls.COGNITO_USER_POOL_ID:
                errors.append("AUTH_ENABLED 为 true 时需要 COGNITO_USER_POOL_ID")
            if not cls.COGNITO_APP_CLIENT_ID:
                errors.append("AUTH_ENABLED 为 true 时需要 COGNITO_APP_CLIENT_ID")
            if not cls.AUTH_DYNAMODB_TABLE_NAME:
                errors.append("AUTH_ENABLED 为 true 时需要 AUTH_DYNAMODB_TABLE_NAME")
            if not cls.AUTH_DYNAMODB_PK_ATTRIBUTE:
                errors.append("AUTH_ENABLED 为 true 时需要 AUTH_DYNAMODB_PK_ATTRIBUTE")
        if cls.CORS_SUPPORTS_CREDENTIALS and cls.CORS_ORIGINS == '*':
            errors.append(
                "CORS_SUPPORTS_CREDENTIALS=true 时必须设置 CORS_ALLOWED_ORIGINS（不能使用通配符 *）"
            )
        return errors

