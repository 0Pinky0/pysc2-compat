load("@my_deps//:requirements.bzl", "requirement")
load("//pysc2:build_defs.bzl", "pytype_library")

package(default_visibility = ["//visibility:public"])

licenses(["notice"])

py_test(
    name = "test_named_array",
    size = "small",
    srcs = ["test_named_array.py"],
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
    name = "test_features",
    size = "small",
    srcs = ["test_features.py"],
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
    name = "test_image_differencer",
    srcs = ["test_image_differencer.py"],
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
    name = "test_np_util",
    srcs = ["test_np_util.py"],
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
    name = "test_portspicker",
    size = "small",
    srcs = ["test_portspicker.py"],
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
    name = "test_proto_diff",
    srcs = ["test_proto_diff.py"],
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
    name = "test_run_parallel",
    size = "small",
    srcs = ["test_run_parallel.py"],
    legacy_create_init = False,
    python_version = "PY3",
    srcs_version = "PY3",
    deps = [
        ":run_parallel",
        "@absl_py//absl/testing:absltest",
    ],
)

py_test(
    name = "test_point",
    srcs = ["test_point.py"],
    legacy_create_init = False,
    python_version = "PY3",
    srcs_version = "PY3",
    deps = [
        ":point",
        "@absl_py//absl/testing:absltest",
    ],
)

py_test(
    name = "test_stopwatch",
    srcs = ["test_stopwatch.py"],
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
