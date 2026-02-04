load("@my_deps//:requirements.bzl", "requirement")
load("//pysc2:build_defs.bzl", "pytype_library")

package(default_visibility = ["//visibility:public"])

licenses(["notice"])

py_library(
    name = "dummy_observation",
    srcs = ["dummy_observation.py"],
    srcs_version = "PY3",
    deps = [
        requirement("numpy"),
        "//pysc2/lib:features",
        "@s2client_proto//s2clientprotocol:sc2api_py_pb2",
    ],
)

py_test(
    name = "test_dummy_observation",
    size = "small",
    srcs = ["test_dummy_observation.py"],
    legacy_create_init = False,
    python_version = "PY3",
    srcs_version = "PY3",
    deps = [
        ":dummy_observation",
        "@absl_py//absl/testing:absltest",
        "@absl_py//absl/testing:parameterized",
        requirement("numpy"),
        "//pysc2/lib:actions",
        "//pysc2/lib:features",
        "//pysc2/lib:point",
        "//pysc2/lib:units",
        "@s2client_proto//s2clientprotocol:sc2api_py_pb2",
    ],
)

py_test(
    name = "test_debug",
    size = "enormous",
    srcs = ["test_debug.py"],
    legacy_create_init = False,
    python_version = "PY3",
    srcs_version = "PY3",
    deps = [
        "//pysc2/lib:units",
        "//pysc2/maps",
        "//pysc2/run_configs",
        "@absl_py//absl/testing:absltest",
        "@s2client_proto//s2clientprotocol:sc2api_py_pb2",
    ],
)

py_test(
    name = "test_easy_scripted",
    size = "enormous",
    srcs = ["test_easy_scripted.py"],
    legacy_create_init = False,
    python_version = "PY3",
    srcs_version = "PY3",
    deps = [
        ":utils",
        "//pysc2/agents:scripted_agent",
        "//pysc2/env:run_loop",
        "//pysc2/env:sc2_env",
        "@absl_py//absl/testing:absltest",
    ],
)

py_test(
    name = "test_actions",
    size = "enormous",
    srcs = ["test_actions.py"],
    legacy_create_init = False,
    python_version = "PY3",
    srcs_version = "PY3",
    deps = [
        ":utils",
        "//pysc2/lib:actions",
        "//pysc2/lib:units",
        "@absl_py//absl/testing:absltest",
    ],
)

py_test(
    name = "test_obs",
    size = "enormous",
    srcs = ["test_obs.py"],
    legacy_create_init = False,
    python_version = "PY3",
    shard_count = 5,
    srcs_version = "PY3",
    deps = [
        ":utils",
        "//pysc2/lib:actions",
        "//pysc2/lib:buffs",
        "//pysc2/lib:features",
        "//pysc2/lib:units",
        "@absl_py//absl/testing:absltest",
        "@s2client_proto//s2clientprotocol:debug_py_pb2",
        "@s2client_proto//s2clientprotocol:raw_py_pb2",
    ],
)

py_test(
    name = "test_host_remote_agent",
    size = "enormous",
    srcs = ["test_host_remote_agent.py"],
    legacy_create_init = False,
    python_version = "PY3",
    srcs_version = "PY3",
    deps = [
        ":utils",
        "//pysc2/env:host_remote_agent",
        "//pysc2/lib:remote_controller",
        "//pysc2/lib:run_parallel",
        "@absl_py//absl/testing:absltest",
        "@s2client_proto//s2clientprotocol:sc2api_py_pb2",
    ],
)

py_test(
    name = "test_multi_player",
    size = "enormous",
    srcs = ["test_multi_player.py"],
    legacy_create_init = False,
    python_version = "PY3",
    srcs_version = "PY3",
    deps = [
        ":utils",
        "//pysc2/lib:point",
        "//pysc2/lib:portspicker",
        "//pysc2/lib:run_parallel",
        "//pysc2/maps",
        "//pysc2/run_configs",
        "@absl_py//absl/logging",
        "@absl_py//absl/testing:absltest",
        "@s2client_proto//s2clientprotocol:common_py_pb2",
        "@s2client_proto//s2clientprotocol:sc2api_py_pb2",
    ],
)

py_test(
    name = "test_multi_player_env",
    size = "enormous",
    srcs = ["test_multi_player_env.py"],
    legacy_create_init = False,
    python_version = "PY3",
    shard_count = 3,
    srcs_version = "PY3",
    deps = [
        ":utils",
        "//pysc2/agents:no_op_agent",
        "//pysc2/agents:random_agent",
        "//pysc2/env:run_loop",
        "//pysc2/env:sc2_env",
        "@absl_py//absl/testing:absltest",
        "@absl_py//absl/testing:parameterized",
        "@s2client_proto//s2clientprotocol:common_py_pb2",
        "@s2client_proto//s2clientprotocol:sc2api_py_pb2",
    ],
)

py_test(
    name = "test_observer",
    size = "enormous",
    srcs = ["test_observer.py"],
    legacy_create_init = False,
    python_version = "PY3",
    srcs_version = "PY3",
    deps = [
        ":utils",
        "//pysc2/maps",
        "//pysc2/run_configs",
        "@absl_py//absl/testing:absltest",
        "@s2client_proto//s2clientprotocol:sc2api_py_pb2",
    ],
)

py_test(
    name = "test_protocol_error",
    size = "enormous",
    srcs = ["test_protocol_error.py"],
    legacy_create_init = False,
    python_version = "PY3",
    srcs_version = "PY3",
    deps = [
        ":utils",
        "//pysc2/lib:protocol",
        "//pysc2/lib:remote_controller",
        "//pysc2/maps",
        "//pysc2/run_configs",
        "@absl_py//absl/testing:absltest",
        "@s2client_proto//s2clientprotocol:common_py_pb2",
        "@s2client_proto//s2clientprotocol:sc2api_py_pb2",
    ],
)

py_test(
    name = "test_random_agent",
    size = "enormous",
    srcs = ["test_random_agent.py"],
    legacy_create_init = False,
    python_version = "PY3",
    shard_count = 3,
    srcs_version = "PY3",
    deps = [
        ":utils",
        "//pysc2/agents:random_agent",
        "//pysc2/env:run_loop",
        "//pysc2/env:sc2_env",
        "@absl_py//absl/testing:absltest",
        "@absl_py//absl/testing:parameterized",
    ],
)

py_test(
    name = "test_obs_spec",
    size = "enormous",
    srcs = ["test_obs_spec.py"],
    legacy_create_init = False,
    python_version = "PY3",
    srcs_version = "PY3",
    deps = [
        ":utils",
        "//pysc2/agents:random_agent",
        "//pysc2/env:sc2_env",
        "@absl_py//absl/testing:absltest",
    ],
)

py_test(
    name = "test_render",
    size = "enormous",
    srcs = ["test_render.py"],
    legacy_create_init = False,
    python_version = "PY3",
    srcs_version = "PY3",
    deps = [
        ":utils",
        "@absl_py//absl/testing:absltest",
        requirement("numpy"),
        "//pysc2/lib:features",
        "//pysc2/maps",
        "//pysc2/run_configs",
        "@s2client_proto//s2clientprotocol:sc2api_py_pb2",
    ],
)

py_test(
    name = "test_ping",
    size = "enormous",
    srcs = ["test_ping.py"],
    legacy_create_init = False,
    python_version = "PY3",
    srcs_version = "PY3",
    deps = [
        ":utils",
        "//pysc2/lib:stopwatch",
        "//pysc2/run_configs",
        "@absl_py//absl/testing:absltest",
    ],
)

py_test(
    name = "test_general_actions",
    size = "enormous",
    srcs = ["test_general_actions.py"],
    legacy_create_init = False,
    python_version = "PY3",
    srcs_version = "PY3",
    deps = [
        ":utils",
        "//pysc2/lib:actions",
        "//pysc2/maps",
        "//pysc2/run_configs",
        "@absl_py//absl/testing:absltest",
        "@s2client_proto//s2clientprotocol:sc2api_py_pb2",
    ],
)

py_test(
    name = "test_replay_obs",
    size = "enormous",
    srcs = ["test_replay_obs.py"],
    legacy_create_init = False,
    python_version = "PY3",
    srcs_version = "PY3",
    deps = [
        ":utils",
        "//pysc2/lib:actions",
        "//pysc2/lib:features",
        "//pysc2/lib:point",
        "//pysc2/lib:renderer_ascii",
        "//pysc2/lib:units",
        "//pysc2/maps",
        "//pysc2/run_configs",
        "@absl_py//absl/testing:absltest",
        "@s2client_proto//s2clientprotocol:sc2api_py_pb2",
    ],
)

py_test(
    name = "test_step_mul_override",
    size = "enormous",
    srcs = ["test_step_mul_override.py"],
    legacy_create_init = False,
    python_version = "PY3",
    srcs_version = "PY3",
    deps = [
        ":utils",
        "//pysc2/env:sc2_env",
        "//pysc2/lib:actions",
        "@absl_py//absl/testing:absltest",
    ],
)

pytype_library(
    name = "utils",
    testonly = 1,
    srcs = ["utils.py"],
    srcs_version = "PY3",
    deps = [
        "//pysc2/lib:actions",
        "//pysc2/lib:features",
        "//pysc2/lib:point",
        "//pysc2/lib:portspicker",
        "//pysc2/lib:run_parallel",
        "//pysc2/lib:stopwatch",
        "//pysc2/maps",
        "//pysc2/run_configs",
        "@absl_py//absl/logging",
        "@absl_py//absl/testing:absltest",
        "@s2client_proto//s2clientprotocol:common_py_pb2",
        "@s2client_proto//s2clientprotocol:debug_py_pb2",
        "@s2client_proto//s2clientprotocol:error_py_pb2",
        "@s2client_proto//s2clientprotocol:raw_py_pb2",
        "@s2client_proto//s2clientprotocol:sc2api_py_pb2",
    ],
)

py_test(
    name = "test_versions",
    size = "enormous",
    srcs = ["test_versions.py"],
    legacy_create_init = False,
    python_version = "PY3",
    srcs_version = "PY3",
    deps = [
        "//pysc2/maps",
        "//pysc2/run_configs",
        "@absl_py//absl/logging",
        "@absl_py//absl/testing:absltest",
        "@s2client_proto//s2clientprotocol:common_py_pb2",
        "@s2client_proto//s2clientprotocol:sc2api_py_pb2",
    ],
)

pytype_library(
    name = "__init__",
    srcs = ["__init__.py"],
    srcs_version = "PY3",
)
