import dataclasses
import os
import sys
from typing import Any, Callable, Iterable, Mapping, Sequence


class ArgumentParser:
    def parse(self, argument):
        return argument

    def flag_type(self):
        return "string"


class ArgumentSerializer:
    def serialize(self, value):
        return str(value)


@dataclasses.dataclass(frozen=True)
class _FlagDef:
    name: str
    default: Any
    parser: Callable[[Any], Any]
    help: str
    required: bool = False


def _parse_bool(value: str) -> bool:
    v = value.strip().lower()
    if v in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "f", "no", "n", "off"}:
        return False
    raise ValueError(f"Invalid boolean value: {value!r}")


class FlagValues:
    def __init__(self):
        self._defs: dict[str, _FlagDef] = {}
        self._values: dict[str, Any] = {}
        self._parsed: bool = False

    def _define(self, name: str, default: Any, parser: Callable[[Any], Any], help: str):
        if name in self._defs:
            existing = self._defs[name]
            if existing.default != default:
                raise ValueError(f"Flag {name!r} already defined with different default.")
            return
        self._defs[name] = _FlagDef(name=name, default=default, parser=parser, help=help)

    def _mark_required(self, name: str):
        if name not in self._defs:
            raise ValueError(f"Unknown flag: {name!r}")
        d = self._defs[name]
        self._defs[name] = dataclasses.replace(d, required=True)

    def set_default(self, name: str, default: Any):
        if name not in self._defs:
            raise ValueError(f"Unknown flag: {name!r}")
        d = self._defs[name]
        self._defs[name] = dataclasses.replace(d, default=default)

    def __getattr__(self, name: str):
        if name in self._values:
            return self._values[name]
        if name in self._defs:
            return self._defs[name].default
        raise AttributeError(name)

    def __getitem__(self, name: str):
        return getattr(self, name)

    def __contains__(self, name: str):
        return name in self._defs

    def is_parsed(self) -> bool:
        return self._parsed

    def parse(self, argv: Sequence[str]) -> list[str]:
        if argv is None:
            argv = sys.argv
        if not argv:
            argv = [""]

        remaining = [argv[0]]
        i = 1
        while i < len(argv):
            token = argv[i]
            if token == "--":
                remaining.extend(argv[i + 1 :])
                break
            if not token.startswith("--"):
                remaining.append(token)
                i += 1
                continue

            key = token[2:]
            value: Any | None = None

            if "=" in key:
                key, value = key.split("=", 1)

            if key.startswith("no") and key[2:] in self._defs and self._defs[key[2:]].parser is _parse_bool:
                self._values[key[2:]] = False
                i += 1
                continue

            if key not in self._defs:
                raise ValueError(f"Unknown flag: --{key}")

            flag_def = self._defs[key]
            if flag_def.parser is _parse_bool:
                if value is None:
                    self._values[key] = True
                    i += 1
                    continue
                self._values[key] = _parse_bool(str(value))
                i += 1
                continue

            if value is None:
                if i + 1 >= len(argv):
                    raise ValueError(f"Missing value for --{key}")
                value = argv[i + 1]
                i += 2
            else:
                i += 1

            self._values[key] = flag_def.parser(value)

        missing = [n for n, d in self._defs.items() if d.required and n not in self._values]
        if missing:
            raise ValueError(f"Missing required flags: {', '.join('--' + m for m in missing)}")

        self._parsed = True
        return remaining

    def __call__(self, argv: Sequence[str]) -> list[str]:
        return self.parse(argv)


FLAGS = FlagValues()


def disclaim_key_flags():
    return None


def mark_flag_as_required(name: str):
    FLAGS._mark_required(name)


def DEFINE_bool(name: str, default: bool, help: str, **_kwargs):
    FLAGS._define(name, default, _parse_bool, help)


def DEFINE_integer(name: str, default: int | None, help: str, **_kwargs):
    def parser(v):
        if v is None:
            return None
        return int(v)

    FLAGS._define(name, default, parser, help)


def DEFINE_float(name: str, default: float | None, help: str, **_kwargs):
    def parser(v):
        if v is None:
            return None
        return float(v)

    FLAGS._define(name, default, parser, help)


def DEFINE_string(name: str, default: str | None, help: str, **_kwargs):
    def parser(v):
        if v is None:
            return None
        return str(v)

    FLAGS._define(name, default, parser, help)


def DEFINE_enum(name: str, default: str | None, enum_values: Iterable[str], help: str, **_kwargs):
    values = set(enum_values)

    def parser(v):
        if v is None:
            return None
        s = str(v)
        if s not in values:
            raise ValueError(f"Invalid value for --{name}: {s!r}. Allowed: {sorted(values)!r}")
        return s

    FLAGS._define(name, default, parser, help)


def DEFINE_list(name: str, default: Sequence[str] | str | None, help: str, **_kwargs):
    def parser(v):
        if v is None:
            return None
        if isinstance(v, (list, tuple)):
            return list(v)
        s = str(v)
        if not s:
            return []
        return s.split(",")

    normalized_default = default
    if isinstance(default, str):
        normalized_default = parser(default)
    FLAGS._define(name, normalized_default, parser, help)


def DEFINE(parser: ArgumentParser, name: str, default: Any, help: str, flag_values: FlagValues = FLAGS,
           serializer: ArgumentSerializer | None = None, **_kwargs):
    del serializer
    normalized_default = default
    if default is not None:
        normalized_default = parser.parse(default)
    flag_values._define(name, normalized_default, parser.parse, help)
