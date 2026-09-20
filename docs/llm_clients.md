# LLM Client Factory & Provider Capabilities

To maintain multi-cloud and provider-agnostic agility, TradingAgents implements a decoupled **LLM Client Factory** coupled with a declarative **Capabilities Registry** that resolves API and model-specific quirks transparently.

---

## 🏭 Lazy-Import Factory Design

Located in `tradingagents/llm_clients/factory.py`, the core entry point is `create_llm_client`. Rather than importing heavyweight dependencies (e.g., `langchain_google_genai`, `langchain_anthropic`, `boto3`) at module load time, all provider-specific SDK imports are deferred:

```python
def create_llm_client(provider: str, model: str, base_url: str = None, **kwargs):
    # Imports are executed lazily inside the factory to maintain a fast CLI
    # startup time and prevent crashes on environments where some SDKs are uninstalled.
    if provider == "openai":
        from .openai_client import OpenAIClient
        return OpenAIClient(model=model, base_url=base_url, **kwargs)
    elif provider == "anthropic":
        from .anthropic_client import AnthropicClient
        return AnthropicClient(model=model, **kwargs)
    elif provider == "google":
        from .google_client import GoogleClient
        return GoogleClient(model=model, **kwargs)
    # ...
```

---

## 🛠️ Declarative Model Capabilities Registry

Different LLM providers and models present divergent behaviors for structured outputs, JSON validation, and tool routing. Rather than hardcoding `if model == "..."` branching ladders inside client code, TradingAgents delegates these differences to a centralized, declarative schema in `tradingagents/llm_clients/capabilities.py`.

### 1. `ModelCapabilities` Schema
The `ModelCapabilities` dataclass defines what an OpenAI-compatible model accepts at the API level:

```python
@dataclass(frozen=True)
class ModelCapabilities:
    supports_tool_choice: bool
    supports_json_mode: bool
    supports_json_schema: bool
    preferred_structured_method: StructuredMethod
    requires_reasoning_content_roundtrip: bool = False
    requires_reasoning_split: bool = False
```

### 2. Provider Quirk Resolutions

*   **DeepSeek Thinking Models (`deepseek-reasoner` / `deepseek-v4-*`):**
    *   **Quirk:** DeepSeek's reasoning models accept the `tools` array but 400-error if the `tool_choice` parameter is specified (which LangChain's default implementation injects). Furthermore, they require assistant-turn `reasoning_content` to be echoed back in subsequent conversation turn payloads.
    *   **Resolution:** Maps `supports_tool_choice = False` (which suppresses the parameter while still offering tools) and `requires_reasoning_content_roundtrip = True` to enable clean continuation.
*   **MiniMax Thinking Models (`MiniMax-M2.7` / `MiniMax-M2.5`):**
    *   **Quirk:** MiniMax's reasoning models restrict `tool_choice` to a flat enum `{"none", "auto"}`. Passing a standard LangChain tool-spec dictionary triggers a 400-error. Non-reasoning models reject `reasoning_split` configurations.
    *   **Resolution:** Maps `supports_tool_choice = False` and `requires_reasoning_split = True` so the client can automatically split the `<think>` blocks into `reasoning_details` instead of polluting the primary `content` buffer.

---

## 🧠 Reasoning Model Support & Configurations

TradingAgents native provider clients implement next-generation reasoning configuration wrappers:

1.  **Anthropic Client (`AnthropicClient`):**
    *   Integrates thinking configurations (`thinking_effort` and budget parameters).
    *   Handles Claude 3.7 Sonnet reasoning modes, directing reasoning budgets to native thinking blocks.
2.  **Google Client (`GoogleClient`):**
    *   Maps Gemini thinking/reasoning parameters (`thinking_config`) natively within the `langchain_google_genai` interface.
3.  **OpenAI Client (`OpenAIClient`):**
    *   Maps reasoning efforts (e.g. `reasoning_effort="high"` or `"medium"`) for OpenAI o-series models (`o1`, `o3-mini`).
