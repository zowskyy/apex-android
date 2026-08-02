"""JNI name mangling.

Implements the JNI specification's mapping from a Java class/method pair to the
exported C symbol name, including the escape rules and the overload-resolving
long form. Escapes are applied in specification order: the underscore escape
must run before the package separator becomes an underscore, otherwise the
generated separator would be escaped a second time.
"""

from __future__ import annotations


def mangle(value: str) -> str:
    """Apply JNI escaping to one name component.

    ``_`` becomes ``_1``, ``;`` becomes ``_2``, ``[`` becomes ``_3``, the
    package separator becomes ``_``, and any character outside the ASCII
    alphanumeric range becomes ``_0`` followed by four lowercase hex digits.
    """
    out: list[str] = []
    for char in value:
        if char == "_":
            out.append("_1")
        elif char == ";":
            out.append("_2")
        elif char == "[":
            out.append("_3")
        elif char in ("/", "."):
            out.append("_")
        elif char.isascii() and char.isalnum():
            out.append(char)
        else:
            out.append(f"_0{ord(char):04x}")
    return "".join(out)


def jni_short_name(class_name: str, method_name: str) -> str:
    """``Java_<mangled class>_<mangled method>`` (no overload suffix)."""
    return f"Java_{mangle(class_name)}_{mangle(method_name)}"


def argument_descriptors(descriptor: str) -> str:
    """Extract the argument portion of a JVM method descriptor."""
    if not descriptor.startswith("("):
        return ""
    end = descriptor.find(")")
    if end == -1:
        return ""
    return descriptor[1:end]


def jni_long_name(class_name: str, method_name: str, descriptor: str) -> str:
    """Overload-qualified form: short name, ``__``, then mangled arguments."""
    return f"{jni_short_name(class_name, method_name)}__{mangle(argument_descriptors(descriptor))}"


def candidate_symbols(class_name: str, method_name: str, descriptor: str) -> list[str]:
    """Both symbol spellings a native method may be exported under."""
    short = jni_short_name(class_name, method_name)
    long_form = jni_long_name(class_name, method_name, descriptor)
    return [short, long_form] if long_form != short else [short]
