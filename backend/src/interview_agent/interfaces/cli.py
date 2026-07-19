from __future__ import annotations

import os
import logging
from pathlib import Path
from time import perf_counter

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from interview_agent.core.agent_loop import AgentLoop
from interview_agent.core.config import InterviewConfig
from interview_agent.domain.billing import DEFAULT_CHAT_MODEL
from interview_agent.infrastructure.conversation_store import ConversationStore
from interview_agent.infrastructure.codex_config import CodexModelConfig, load_codex_model_config
from interview_agent.infrastructure.model_runtime import (
    is_openai_compatible_provider,
    is_supported_native_provider,
    resolve_model_runtime,
)
from interview_agent.embeddings.embedding import (
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_EMBEDDING_SERVICE_URL,
    DEFAULT_LOCAL_EMBEDDING_MODEL,
    EmbeddingConfig,
    create_embedding_client,
)
from interview_agent.rag.knowledge_base import MarkdownKnowledgeBase
from interview_agent.rag.rag_index import RagIndexer
from interview_agent.infrastructure.settings import load_settings
from interview_agent.interfaces.terminal import (
    TerminalCommandKind,
    help_text,
    parse_terminal_command,
    render_web_search_results,
    render_search_results,
)
from interview_agent.infrastructure.web_search import WebSearchClient
from interview_agent.rag.vector_store import VectorStoreConfig, create_vector_store

app = typer.Typer(help="Run a LangChain-powered interview agent.")
console = Console()
load_dotenv()
settings = load_settings()


def load_config(config_path: Path | None) -> InterviewConfig:
    if config_path is None:
        return InterviewConfig()
    return InterviewConfig.from_json_file(config_path)


def default_index_path() -> Path:
    return settings.rag_index_path


def default_vector_path() -> Path:
    return settings.rag_vector_path


def default_memory_path() -> Path:
    return settings.memory_path


def default_vector_store_metadata_path() -> Path:
    return settings.vector_store_metadata_path


def load_vector_metadata(vector_path: Path | None = None) -> dict:
    path = vector_path or default_vector_path()
    if not path.exists():
        return {}
    try:
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {
        "vector_store": payload.get("vector_store", "json"),
        "embedding_provider": payload.get("embedding_provider", "openai"),
        "embedding_model": payload.get("embedding_model"),
        "chunk_count": payload.get("chunk_count"),
    }


def save_vector_store_metadata(metadata: dict) -> None:
    import json

    path = default_vector_store_metadata_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def load_vector_store_metadata() -> dict:
    import json

    path = default_vector_store_metadata_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_embedding_client_for_existing_vectors(vector_path: Path | None = None):
    path = vector_path or default_vector_path()
    metadata = load_vector_store_metadata() or load_vector_metadata(path)
    if not metadata:
        return None

    provider = metadata.get("embedding_provider", "openai")
    model = metadata.get("embedding_model") or (
        DEFAULT_LOCAL_EMBEDDING_MODEL if provider == "local" else DEFAULT_EMBEDDING_MODEL
    )
    try:
        if provider == "service":
            return create_embedding_client(
                EmbeddingConfig(
                    provider="service",
                    model=model,
                    batch_size=64,
                    service_url=metadata.get("embedding_service_url")
                    or os.getenv("EMBEDDING_SERVICE_URL")
                    or DEFAULT_EMBEDDING_SERVICE_URL,
                )
            )
        if provider == "local":
            return create_embedding_client(
                EmbeddingConfig(
                    provider="local",
                    model=model,
                    batch_size=64,
                    local_files_only=True,
                )
            )

        codex_model_config = load_codex_model_config(Path.cwd())
        if not codex_model_config.api_key:
            return None
        return create_embedding_client(
            EmbeddingConfig(
                provider="openai",
                model=model,
                base_url=codex_model_config.base_url,
                api_key=codex_model_config.api_key,
            )
        )
    except Exception as exc:
        console.print(
            "[yellow]向量检索模型加载失败，已回退为 BM25。"
            f"原因：{exc.__class__.__name__}: {exc}[/yellow]"
        )
        return None


def load_vector_store_for_run(vector_path: Path | None = None):
    metadata = load_vector_store_metadata()
    provider = metadata.get("vector_store") or "json"
    if provider == "qdrant":
        try:
            return create_vector_store(
                VectorStoreConfig(
                    provider="qdrant",
                    collection_name=metadata.get("collection_name", settings.qdrant_collection),
                    url=metadata.get("url"),
                    api_key=os.getenv("QDRANT_API_KEY"),
                )
            )
        except Exception as exc:
            console.print(
                "[yellow]Qdrant 向量库连接失败，已回退本地 JSON/BM25。"
                f"原因：{exc.__class__.__name__}: {exc}[/yellow]"
            )
    path = vector_path or default_vector_path()
    if not path.exists():
        return None
    return create_vector_store(VectorStoreConfig(provider="json", path=path))


def default_knowledge_roots(primary: Path) -> list[Path]:
    roots = [primary]
    github_ai = Path("knowledge_base/github-ai-knowledge")
    if github_ai.exists():
        roots.append(github_ai)
    return roots


def load_knowledge_base(
    path: Path | None,
    index_path: Path | None = None,
    vector_path: Path | None = None,
    embedding_client=None,
    vector_store=None,
) -> MarkdownKnowledgeBase | None:
    kb_path = path or settings.knowledge_base_path
    if not kb_path.exists():
        return None
    return MarkdownKnowledgeBase(
        kb_path,
        index_path=index_path or default_index_path(),
        vector_path=vector_path or default_vector_path(),
        embedding_client=embedding_client,
        vector_store=vector_store,
    )


def print_result(result) -> None:
    console.print(Panel(result.message, title="面试官"))
    if result.guardrail_findings:
        messages = "；".join(finding.message for finding in result.guardrail_findings)
        console.print(f"[yellow]Harness 护栏：{messages}[/yellow]")
    if result.fallback_used:
        console.print("[yellow]模型调用失败，已使用 Harness 降级回复。[/yellow]")


def handle_terminal_command(
    command,
    loop: AgentLoop,
    kb: MarkdownKnowledgeBase | None,
    web_search: WebSearchClient | None,
):
    if command.kind == TerminalCommandKind.HELP:
        console.print(Panel(help_text(), title="帮助"))
        return None
    if command.kind == TerminalCommandKind.KB_SEARCH:
        with console.status("[bold cyan]正在检索本地知识库...[/bold cyan]", spinner="dots"):
            search_result = render_search_results(kb, command.payload)
        console.print(Panel(search_result, title="知识库搜索"))
        return None
    if command.kind == TerminalCommandKind.WEB_SEARCH:
        with console.status("[bold cyan]正在联网搜索...[/bold cyan]", spinner="dots"):
            context = (
                web_search.context_for(command.payload)
                if web_search
                else "未启用联网搜索，请使用 --web-search。"
            )
        console.print(Panel(render_web_search_results(context, command.payload), title="联网搜索"))
        return None
    if command.kind == TerminalCommandKind.TRANSCRIPT:
        transcript = loop.state.transcript() or "暂无面试记录。"
        console.print(Panel(transcript, title="面试记录"))
        return None
    if command.kind == TerminalCommandKind.QUIT:
        console.print("[green]已结束当前面试。[/green]")
        raise typer.Exit()
    with console.status("[bold cyan]正在分析回答、检索知识库并生成追问...[/bold cyan]", spinner="dots"):
        return loop.step(command.payload)


def persist_result(
    store: ConversationStore | None,
    config: InterviewConfig,
    result,
    event_type: str,
) -> None:
    if store is None:
        return
    store.record_event(
        event_type,
        {
            "message": result.message,
            "advanced": result.advanced,
            "fallback_used": result.fallback_used,
            "stage": result.state.stage.value,
        },
    )
    store.save_state(config, result.state)


@app.command()
def run(
    config: Path | None = typer.Option(None, "--config", "-c", help="Path to interview JSON config."),
    knowledge_base: Path | None = typer.Option(
        None,
        "--knowledge-base",
        "-k",
        help="Path to a Markdown knowledge base directory.",
    ),
    offline: bool = typer.Option(False, "--offline", help="Use deterministic local responses."),
    model: str | None = typer.Option(None, "--model", help="OpenAI chat model for LangChain."),
    use_codex_config: bool = typer.Option(
        True,
        "--use-codex-config/--no-use-codex-config",
        help="Read model defaults from Codex config.toml when available.",
    ),
    web_search_enabled: bool = typer.Option(
        False,
        "--web-search/--no-web-search",
        help="Automatically add web search context to harness prompts.",
    ),
    save_conversation: bool = typer.Option(
        True,
        "--save-conversation/--no-save-conversation",
        help="Persist interview transcript and reusable memory snippets.",
    ),
) -> None:
    """Start an interactive interview session."""

    started_at = perf_counter()
    console.print("[bold cyan]正在启动面试 Agent...[/bold cyan]")
    with console.status("[bold cyan]加载环境变量和面试配置...[/bold cyan]", spinner="dots"):
        from interview_agent.core.harness import LangChainInterviewHarness, ScriptedInterviewHarness

        load_dotenv()
        interview_config = load_config(config)
        conversation_store = ConversationStore() if save_conversation else None
        codex_model_config = load_codex_model_config(Path.cwd()) if use_codex_config else None

    with console.status("[bold cyan]连接 EmbeddingService / 向量库...[/bold cyan]", spinner="dots"):
        embedding_client = load_embedding_client_for_existing_vectors(default_vector_path())
        vector_store = load_vector_store_for_run(default_vector_path())

    with console.status("[bold cyan]加载知识库索引...[/bold cyan]", spinner="dots"):
        resolved_model = (
            model
            or (codex_model_config.model if codex_model_config else None)
            or os.getenv("OPENAI_MODEL")
            or DEFAULT_CHAT_MODEL
        )
        kb = load_knowledge_base(
            knowledge_base,
            embedding_client=embedding_client,
            vector_store=vector_store,
        )
        web_search = WebSearchClient() if web_search_enabled else None
    if kb:
        console.print(
            f"[green]已配置知识库：[/green] {kb.root} "
            f"({kb.estimated_file_count()} 个 Markdown 文件，检索模式：{kb.retrieval_mode})"
        )
    else:
        console.print("[yellow]未加载知识库。[/yellow]")

    runtime = resolve_model_runtime(
        resolved_model,
        codex_config=codex_model_config or CodexModelConfig(),
    )
    supported = is_openai_compatible_provider(runtime.provider) or is_supported_native_provider(runtime.provider)
    if offline or not runtime.api_key or not supported:
        harness = ScriptedInterviewHarness(interview_config, knowledge_base=kb)
        console.print("[yellow]正在使用离线脚本 harness。[/yellow]")
    else:
        console.print(f"[green]使用模型：[/green] {resolved_model}")
        console.print(f"[green]使用 provider：[/green] {runtime.provider}")
        try:
            harness = LangChainInterviewHarness(
                interview_config,
                knowledge_base=kb,
                web_search=web_search,
                model=runtime.model,
                provider=runtime.provider,
                base_url=runtime.base_url,
                api_key=runtime.api_key,
                wire_api=runtime.wire_api,
            )
        except RuntimeError as exc:
            harness = ScriptedInterviewHarness(interview_config, knowledge_base=kb)
            console.print(f"[yellow]{exc} 已降级到离线脚本 harness。[/yellow]")

    loop = AgentLoop(interview_config, harness)
    console.print(f"[dim]启动准备完成，用时 {perf_counter() - started_at:.1f}s。[/dim]")
    with console.status("[bold cyan]正在生成第一题...[/bold cyan]", spinner="dots"):
        result = loop.start()
    print_result(result)
    persist_result(conversation_store, interview_config, result, "start")
    if web_search_enabled:
        hint = "RAG 会自动使用本地知识库；联网搜索也会自动注入上下文。"
    else:
        hint = "RAG 会自动使用本地知识库；联网搜索默认关闭，可用 --web-search 开启。"
    console.print(f"[dim]提示：{hint} 输入 /help 查看命令。[/dim]")

    while not result.state.completed:
        response = typer.prompt("候选人")
        command = parse_terminal_command(response)
        next_result = handle_terminal_command(command, loop, kb, web_search)
        if next_result is None:
            continue
        result = next_result
        print_result(result)
        persist_result(conversation_store, interview_config, result, "turn")

    console.print("[green]面试完成。[/green]")
    if conversation_store:
        console.print(f"[green]面试记录已保存：[/green] {conversation_store.markdown_path}")
        console.print(f"[green]可检索记忆已保存：[/green] {conversation_store.memory_path}")


@app.command()
def demo() -> None:
    """Run a deterministic non-interactive demo."""

    from interview_agent.core.harness import ScriptedInterviewHarness

    config = InterviewConfig()
    kb = load_knowledge_base(None)
    loop = AgentLoop(config, ScriptedInterviewHarness(config, knowledge_base=kb))
    result = loop.start()
    print_result(result)

    sample_answers = [
        "我做过一个文档处理服务，通过定位数据库热点把 p95 延迟降了下来。",
        "主要取舍是缓存新鲜度和请求延迟之间的平衡。",
        "我会围绕幂等性、可观测性和灰度发布来设计。",
    ]
    for answer in sample_answers:
        if result.state.completed:
            break
        console.print(Panel(answer, title="候选人"))
        result = loop.step(answer)
        print_result(result)


@app.command()
def index(
    knowledge_base: Path | None = typer.Option(
        None,
        "--knowledge-base",
        "-k",
        help="Path to a Markdown knowledge base directory.",
    ),
    output: Path = typer.Option(
        default_index_path(),
        "--output",
        "-o",
        help="Path to write the persistent RAG index.",
    ),
    chunk_size: int = typer.Option(1800, "--chunk-size", help="Chunk size in characters."),
    embeddings: bool = typer.Option(
        False,
        "--embeddings/--no-embeddings",
        help="Build embedding vectors for hybrid retrieval.",
    ),
    embedding_model: str = typer.Option(
        settings.embedding_model,
        "--embedding-model",
        help="Embedding model for vector retrieval.",
    ),
    embedding_provider: str = typer.Option(
        settings.embedding_provider,
        "--embedding-provider",
        help="Embedding provider: local or openai.",
    ),
    embedding_device: str | None = typer.Option(
        None,
        "--embedding-device",
        help="Optional local embedding device, e.g. cpu, mps, cuda.",
    ),
    embedding_download: bool = typer.Option(
        False,
        "--embedding-download/--no-embedding-download",
        help="Allow local embedding model download during indexing.",
    ),
    vector_store_provider: str = typer.Option(
        settings.vector_store,
        "--vector-store",
        help="Vector store backend: json or qdrant.",
    ),
    qdrant_url: str = typer.Option(
        settings.qdrant_url,
        "--qdrant-url",
        help="Qdrant service URL.",
    ),
    qdrant_collection: str = typer.Option(
        settings.qdrant_collection,
        "--qdrant-collection",
        help="Qdrant collection name.",
    ),
    include_memory: bool = typer.Option(
        True,
        "--include-memory/--no-include-memory",
        help="Include saved interview conversation memory in the RAG index.",
    ),
) -> None:
    """Build a persistent local RAG index for faster, more stable retrieval."""

    kb_path = knowledge_base or settings.knowledge_base_path
    if not kb_path.exists():
        raise typer.BadParameter(f"知识库目录不存在：{kb_path}")

    roots = default_knowledge_roots(kb_path)
    memory_path = default_memory_path()
    if include_memory and memory_path.exists():
        roots.append(memory_path)

    started_at = perf_counter()
    console.print(f"[dim]正在构建 RAG 索引：{', '.join(str(root) for root in roots)}[/dim]")
    embedding_client = None
    vector_path = None
    vector_store = None
    if embeddings:
        try:
            if embedding_provider not in {"local", "service", "openai"}:
                raise typer.BadParameter("--embedding-provider 仅支持 local、service 或 openai。")
            if embedding_provider == "openai":
                codex_model_config = load_codex_model_config(Path.cwd())
                if not codex_model_config.api_key:
                    raise typer.BadParameter("OpenAI embedding 需要 GATEWAY_API_KEY 或 OPENAI_API_KEY。")
                embedding_client = create_embedding_client(
                    EmbeddingConfig(
                        provider="openai",
                        model=embedding_model,
                        base_url=codex_model_config.base_url,
                        api_key=codex_model_config.api_key,
                    )
                )
            elif embedding_provider == "service":
                embedding_client = create_embedding_client(
                    EmbeddingConfig(
                        provider="service",
                        model=embedding_model,
                        batch_size=64,
                        service_url=os.getenv("EMBEDDING_SERVICE_URL")
                        or settings.embedding_service_url,
                    )
                )
            else:
                embedding_client = create_embedding_client(
                    EmbeddingConfig(
                        provider="local",
                        model=embedding_model,
                        batch_size=64,
                        device=embedding_device,
                        local_files_only=not embedding_download,
                    )
                )
        except typer.BadParameter:
            raise
        except Exception as exc:
            console.print(
                "[yellow]向量模型初始化失败，已回退为仅构建 BM25 索引。"
                f"原因：{exc.__class__.__name__}: {exc}[/yellow]"
            )
        vector_path = default_vector_path()
        if embedding_client:
            if vector_store_provider not in {"json", "qdrant"}:
                raise typer.BadParameter("--vector-store 仅支持 json 或 qdrant。")
            vector_store = create_vector_store(
                VectorStoreConfig(
                    provider=vector_store_provider,
                    path=vector_path,
                    collection_name=qdrant_collection,
                    url=qdrant_url,
                    recreate_collection=True,
                )
            )
            console.print(
                f"[dim]将构建向量索引：{vector_store_provider} "
                f"({embedding_provider}:{embedding_model})[/dim]"
            )

    vector_built = False
    try:
        payload = RagIndexer(
            roots,
            output,
            chunk_size=chunk_size,
            vector_path=vector_path,
            embedding_client=embedding_client,
            vector_store=vector_store,
        ).build()
        vector_built = bool(embeddings and vector_store and vector_store.is_available())
    except Exception as exc:
        if not embeddings:
            raise
        console.print(
            "[yellow]向量索引构建失败，已回退为仅构建 BM25 索引。"
            f"原因：{exc.__class__.__name__}: {exc}[/yellow]"
        )
        payload = RagIndexer(roots, output, chunk_size=chunk_size).build()
    console.print(
        f"[green]索引构建完成：[/green] {output} "
        f"({payload['chunk_count']} chunks，用时 {perf_counter() - started_at:.1f}s)"
    )
    if vector_built and vector_store:
        metadata = {
            **vector_store.metadata,
            "embedding_provider": getattr(embedding_client.config, "provider", "openai"),
            "embedding_model": embedding_client.config.model,
        }
        if getattr(embedding_client.config, "provider", None) == "service":
            metadata["embedding_service_url"] = embedding_client.config.service_url
        save_vector_store_metadata(metadata)
        console.print(f"[green]向量索引构建完成：[/green] {metadata}")


@app.command("embedding-service")
def embedding_service(
    host: str = typer.Option("127.0.0.1", "--host", help="Embedding service host."),
    port: int = typer.Option(8010, "--port", help="Embedding service port."),
    model: str = typer.Option(
        settings.embedding_model,
        "--model",
        help="Local SentenceTransformers embedding model.",
    ),
    batch_size: int = typer.Option(64, "--batch-size", help="Embedding batch size."),
    device: str | None = typer.Option(None, "--device", help="Optional device: cpu, mps, cuda."),
    embedding_download: bool = typer.Option(
        False,
        "--embedding-download/--no-embedding-download",
        help="Allow model download when service starts.",
    ),
) -> None:
    """Run a local HTTP EmbeddingService."""

    import uvicorn
    from interview_agent.embeddings.embedding_service import EmbeddingServiceSettings, create_app

    service_app = create_app(
        EmbeddingServiceSettings(
            model=model,
            batch_size=batch_size,
            device=device,
            local_files_only=not embedding_download,
        )
    )
    console.print(
        f"[green]EmbeddingService 启动中：[/green] http://{host}:{port} "
        f"({model})"
    )
    uvicorn.run(service_app, host=host, port=port)


@app.command()
def api(
    host: str = typer.Option("127.0.0.1", "--host", help="API host."),
    port: int = typer.Option(8020, "--port", help="API port."),
) -> None:
    """Run the local HTTP API for desktop clients."""

    import uvicorn
    from interview_agent.interfaces.api import create_app

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    logging.getLogger("interview_agent.api").setLevel(
        getattr(logging, settings.log_level.upper(), logging.INFO)
    )
    console.print(f"[green]Interview Agent API 启动中：[/green] http://{host}:{port}")
    console.print(f"[dim]PostgreSQL: {settings.database_url}[/dim]")
    console.print(
        f"[dim]ObjectStorage: {settings.object_storage_backend} "
        f"bucket={settings.object_storage_bucket} endpoint={settings.object_storage_endpoint}[/dim]"
    )
    uvicorn.run(create_app(), host=host, port=port, log_level=settings.log_level.lower(), access_log=True)


@app.command()
def doctor() -> None:
    """Check local production dependencies and RAG artifacts."""

    from interview_agent.infrastructure.doctor import run_doctor

    results = run_doctor(
        index_path=default_index_path(),
        vector_store_metadata_path=default_vector_store_metadata_path(),
        embedding_service_url=settings.embedding_service_url,
        qdrant_url=settings.qdrant_url,
        qdrant_collection=settings.qdrant_collection,
        settings=settings,
    )
    failed = False
    for result in results:
        status = "[green]OK[/green]" if result.ok else "[red]FAIL[/red]"
        console.print(f"{status} {result.name}: {result.message}")
        failed = failed or not result.ok
    if failed:
        raise typer.Exit(code=1)


@app.command("eval-rag")
def eval_rag(
    cases: Path = typer.Option(
        Path("backend/tests/fixtures/rag_eval_cases.json"),
        "--cases",
        help="Path to RAG evaluation cases JSON.",
    ),
    top_k: int = typer.Option(4, "--top-k", help="Number of retrieved chunks to evaluate."),
) -> None:
    """Run a lightweight RAG retrieval regression evaluation."""

    from interview_agent.rag.rag_eval import load_eval_cases, run_rag_eval

    embedding_client = load_embedding_client_for_existing_vectors(default_vector_path())
    vector_store = load_vector_store_for_run(default_vector_path())
    kb = load_knowledge_base(None, embedding_client=embedding_client, vector_store=vector_store)
    eval_cases = load_eval_cases(cases)
    results = run_rag_eval(kb, eval_cases, top_k=top_k)
    failed = False
    for result in results:
        status = "[green]PASS[/green]" if result.ok else "[red]FAIL[/red]"
        console.print(f"{status} {result.query}")
        if result.missing_sources:
            console.print(f"  missing sources: {', '.join(result.missing_sources)}")
        if result.missing_terms:
            console.print(f"  missing terms: {', '.join(result.missing_terms)}")
        failed = failed or not result.ok
    if failed:
        raise typer.Exit(code=1)
