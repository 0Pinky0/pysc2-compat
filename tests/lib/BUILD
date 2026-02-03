load("@my_deps//:requirements.bzl", "requirement")
load("//pysc2:build_defs.bzl", "pytype_library")

package(default_visibility = ["//visibility:public"])

licenses(["notice"])

py_test(
    name = "named_array_test",
    size = "small",
    srcs = ["named_array_test.py"],
    legacy_create_init = False,
    python_version = "PY3",
    srcs_version = "PY3",
    deps = [
        ":named_array",
        "@absl_py//absl/testing:absltest",
        "@absl_py//absl/testing:parameterized",
        requirement("numpy"),
    ],
)

py_test(
    name = "features_test",
    size = "small",
    srcs = ["features_test.py"],
    legacy_create_init = False,
    python_version = "PY3",
    srcs_version = "PY3",
    deps = [
        ":actions",
        ":features",
        ":point",
        "@absl_py//absl/testing:absltest",
        "@absl_py//absl/testing:parameterized",
        requirement("numpy"),
        "@s2client_proto//s2clientprotocol:sc2api_py_pb2",
    ],
)

py_test(
    name = "image_differencer_test",
    srcs = ["image_differencer_test.py"],
    legacy_create_init = False,
    python_version = "PY3",
    srcs_version = "PY3",
    deps = [
        ":image_differencer",
        ":proto_diff",
        "@absl_py//absl/testing:absltest",
        requirement("numpy"),
        "@s2client_proto//s2clientprotocol:common_py_pb2",
    ],
)

py_test(
    name = "np_util_test",
    srcs = ["np_util_test.py"],
    legacy_create_init = False,
    python_version = "PY3",
    srcs_version = "PY3",
    deps = [
        ":np_util",
        "@absl_py//absl/testing:absltest",
        "@absl_py//absl/testing:parameterized",
        requirement("numpy"),
    ],
)

py_test(
    name = "portspicker_test",
    size = "small",
    srcs = ["portspicker_test.py"],
    legacy_create_init = False,
    python_version = "PY3",
    srcs_version = "PY3",
    deps = [
        ":portspicker",
        "@absl_py//absl/testing:absltest",
        "@absl_py//absl/testing:parameterized",
    ],
)

py_test(
    name = "proto_diff_test",
    srcs = ["proto_diff_test.py"],
    legacy_create_init = False,
    python_version = "PY3",
    srcs_version = "PY3",
    deps = [
        ":proto_diff",
        "@absl_py//absl/testing:absltest",
        "@s2client_proto//s2clientprotocol:sc2api_py_pb2",
        "@s2client_proto//s2clientprotocol:score_py_pb2",
    ],
)

py_test(
    name = "run_parallel_test",
    size = "small",
    srcs = ["run_parallel_test.py"],
    legacy_create_init = False,
    python_version = "PY3",
    srcs_version = "PY3",
    deps = [
        ":run_parallel",
        "@absl_py//absl/testing:absltest",
    ],
)

py_test(
    name = "point_test",
    srcs = ["point_test.py"],
    legacy_create_init = False,
    python_version = "PY3",
    srcs_version = "PY3",
    deps = [
        ":point",
        "@absl_py//absl/testing:absltest",
    ],
)

py_test(
    name = "stopwatch_test",
    srcs = ["stopwatch_test.py"],
    legacy_create_init = False,
    python_version = "PY3",
    srcs_version = "PY3",
    deps = [
        ":stopwatch",
        "@absl_py//absl/testing:absltest",
        requirement("mock"),
    ],
)

pytype_library(
    name = "__init__",
    srcs = ["__init__.py"],
    srcs_version = "PY3",
)
