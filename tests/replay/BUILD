load("@my_deps//:requirements.bzl", "requirement")
load("//pysc2:build_defs.bzl", "pytype_strict_library")

package(default_visibility = ["//visibility:public"])

licenses(["notice"])

exports_files([
    "test_data/replay_0" + str(i) + ".SC2Replay"
    for i in range(1, 10)
])

exports_files([
    "test_data/replay_0" + str(i) + ".skips.txt"
    for i in range(1, 10)
])

py_test(
    name = "test_sc2_replay",
    srcs = ["test_sc2_replay.py"],
    data = ["//tests/replay:test_data/replay_01.SC2Replay"],
    legacy_create_init = False,
    python_version = "PY3",
    srcs_version = "PY3",
    deps = [
        ":sc2_replay",
        "//pysc2/lib:gfile",
        "//pysc2/lib:resources",
        "@absl_py//absl/flags",
        "@absl_py//absl/testing:absltest",
    ],
)

py_test(
    name = "test_sc2_replay_utils",
    srcs = ["test_sc2_replay_utils.py"],
    data = [
        "//tests/replay:test_data/replay_0" + str(i) + ".SC2Replay"
        for i in range(1, 10)
    ] + [
        "//tests/replay:test_data/replay_0" + str(i) + ".skips.txt"
        for i in range(1, 10)
    ],
    legacy_create_init = False,
    python_version = "PY3",
    srcs_version = "PY3",
    deps = [
        ":sc2_replay",
        ":sc2_replay_utils",
        "//pysc2/lib:gfile",
        "//pysc2/lib:resources",
        "@absl_py//absl/flags",
        "@absl_py//absl/testing:absltest",
        "@absl_py//absl/testing:parameterized",
    ],
)

pytype_library(
    name = "__init__",
    srcs = ["__init__.py"],
    srcs_version = "PY3",
)
