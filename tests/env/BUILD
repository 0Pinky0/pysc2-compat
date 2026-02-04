load("@my_deps//:requirements.bzl", "requirement")
load("//pysc2:build_defs.bzl", "pytype_library")

package(default_visibility = ["//visibility:public"])

licenses(["notice"])

pytype_library(
    name = "mock_sc2_env",
    srcs = ["mock_sc2_env.py"],
    srcs_version = "PY3",
    deps = [
        ":environment",
        ":sc2_env",
        requirement("numpy"),
        "//pysc2/lib:features",
        "//pysc2/lib:units",
        "//pysc2/tests:dummy_observation",
        "@s2client_proto//s2clientprotocol:common_py_pb2",
        "@s2client_proto//s2clientprotocol:raw_py_pb2",
        "@s2client_proto//s2clientprotocol:sc2api_py_pb2",
    ],
)

py_test(
    name = "test_converted_env",
    srcs = ["test_converted_env.py"],
    legacy_create_init = False,
    deps = [
        ":converted_env",
        "@absl_py//absl/testing:absltest",
        "@dm_env_archive//:dm_env",
        "@dm_env_archive//:test_utils",
        requirement("numpy"),
        "//pysc2/env:mock_sc2_env",
        "//pysc2/env:sc2_env",
        "//pysc2/env/converter",
        "//pysc2/env/converter/proto:converter_py_pb2",
        "//pysc2/lib:features",
        "@s2client_proto//s2clientprotocol:common_py_pb2",
        "@s2client_proto//s2clientprotocol:sc2api_py_pb2",
    ],
)

py_test(
    name = "test_sc2_env",
    size = "small",
    srcs = ["test_sc2_env.py"],
    legacy_create_init = False,
    python_version = "PY3",
    srcs_version = "PY3",
    deps = [
        ":sc2_env",
        "@absl_py//absl/testing:absltest",
        "@absl_py//absl/testing:parameterized",
    ],
)

py_test(
    name = "test_mock_sc2_env",
    size = "small",
    srcs = ["test_mock_sc2_env.py"],
    legacy_create_init = False,
    python_version = "PY3",
    srcs_version = "PY3",
    deps = [
        ":enums",
        ":environment",
        ":mock_sc2_env",
        ":sc2_env",
        "@absl_py//absl/testing:absltest",
        requirement("mock"),
        requirement("numpy"),
        "//pysc2/lib:features",
    ],
)

py_test(
    name = "test_mock_sc2_env_comparison",
    size = "large",
    srcs = ["test_mock_sc2_env_comparison.py"],
    legacy_create_init = False,
    python_version = "PY3",
    srcs_version = "PY3",
    deps = [
        ":mock_sc2_env",
        ":sc2_env",
        "@absl_py//absl/testing:absltest",
    ],
)

py_test(
    name = "test_converter",
    srcs = ["test_converter.py"],
    legacy_create_init = False,
    deps = [
        ":converter",
        "@absl_py//absl/testing:absltest",
        "@absl_py//absl/testing:parameterized",
        requirement("numpy"),
        "//pysc2/env/converter/proto:converter_py_pb2",
        "@s2client_proto//s2clientprotocol:common_py_pb2",
        "@s2client_proto//s2clientprotocol:raw_py_pb2",
        "@s2client_proto//s2clientprotocol:sc2api_py_pb2",
        "@s2client_proto//s2clientprotocol:spatial_py_pb2",
    ],
)

pytype_library(
    name = "__init__",
    srcs = ["__init__.py"],
    srcs_version = "PY3",
)
