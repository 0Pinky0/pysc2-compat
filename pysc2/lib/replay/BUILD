load("@my_deps//:requirements.bzl", "requirement")
load("//pysc2:build_defs.bzl", "pytype_strict_library")

package(default_visibility = ["//visibility:public"])

licenses(["notice"])

pytype_strict_library(
    name = "replay_converter",
    srcs = ["replay_converter.py"],
    srcs_version = "PY3",
    deps = [
        ":replay_observation_stream",
        ":sc2_replay",
        ":sc2_replay_utils",
        requirement("numpy"),
        "//pysc2/env/converter",
        "//pysc2/env/converter:derive_interface_options",
        "//pysc2/env/converter/proto:converter_py_pb2",
        requirement("dm-tree"),
        "@s2client_proto//s2clientprotocol:sc2api_py_pb2",
    ],
)

pytype_strict_library(
    name = "replay_observation_stream",
    srcs = ["replay_observation_stream.py"],
    srcs_version = "PY3",
    deps = [
        "@absl_py//absl/logging",
        requirement("mpyq"),
        "//pysc2/run_configs",
        "@s2client_proto//s2clientprotocol:sc2api_py_pb2",
    ],
)

pytype_strict_library(
    name = "sc2_replay",
    srcs = ["sc2_replay.py"],
    srcs_version = "PY3",
    deps = [
        requirement("mpyq"),
        "@s2protocol_archive//:versions",
        requirement("dm-tree"),
    ],
)

pytype_strict_library(
    name = "sc2_replay_utils",
    srcs = ["sc2_replay_utils.py"],
    srcs_version = "PY3",
    deps = [":sc2_replay"],
)
