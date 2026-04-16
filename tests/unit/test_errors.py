from __future__ import annotations

import openagents.errors as errors_pkg
import openagents.errors.exceptions as errors_mod


def test_openagents_error_with_context_returns_typed_instance():
    err_type = getattr(errors_mod, "MaxStepsExceeded")
    err = err_type("tool call limit").with_context(
        agent_id="assistant",
        session_id="demo",
        run_id="run-1",
    )

    assert isinstance(err, errors_mod.OpenAgentsError)
    assert err.agent_id == "assistant"
    assert err.session_id == "demo"
    assert err.run_id == "run-1"


def test_new_error_types_are_importable_from_package_surface():
    config_load_error = getattr(errors_pkg, "ConfigLoadError")
    plugin_capability_error = getattr(errors_pkg, "PluginCapabilityError")
    agent_not_found_error = getattr(errors_mod, "AgentNotFoundError")

    assert issubclass(config_load_error, errors_mod.OpenAgentsError)
    assert issubclass(plugin_capability_error, errors_mod.OpenAgentsError)
    assert issubclass(agent_not_found_error, errors_mod.OpenAgentsError)
