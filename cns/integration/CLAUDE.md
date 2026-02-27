# cns/integration/

Event bus and dependency wiring. Connects CNS to the rest of MIRA.

## Files

- `event_bus.py` — Synchronous pub/sub. Subscribers register by event class name string. `publish()` calls all callbacks immediately, swallows exceptions (logs them). Use `subscribe(EventClassName, callback)` and `publish(event_instance)`.
- `factory.py` — `CNSIntegrationFactory` wires the entire CNS dependency graph in `create_orchestrator()`. Enforces initialization order: embedding model → event bus → working memory + trinkets → tool repo → ephemeral tool cleanup subscription → LLM provider → repositories → memory services → session cache → collapse handler → peripheral services. Trinkets self-register via constructor. Convenience function: `create_cns_orchestrator()`.

## Patterns to Follow

### Adding Event Subscribers
- Subscribe in `__init__` or during factory initialization: `event_bus.subscribe('EventClassName', self._handler_method)`.
- Event type is a string matching the class name exactly.
- Handlers must be synchronous. For async work, spawn a thread with `contextvars.copy_context()`.
- Non-critical handlers must catch their own exceptions (event bus logs but doesn't propagate).

### Adding New Services to the Factory
- Add a `_get_*()` or `_initialize_*()` method to `CNSIntegrationFactory`.
- Lazy-init: check `if self._service is None` before creating.
- Wire it in `create_orchestrator()` at the correct point in the dependency order.
- If it subscribes to events, pass the event_bus to its constructor.

### Adding New Trinkets
- Trinkets self-register: constructor takes `(event_bus, working_memory)` and calls `working_memory.register_trinket(self)`.
- Instantiate the trinket in `_get_working_memory()` (or after tool_repo if it depends on tools).
- No factory registration needed beyond the constructor call.
