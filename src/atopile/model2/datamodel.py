"""
This datamodel represents the code in a clean, simple and traversable way,
but doesn't resolve names of things.
In building this datamodel, we check for name collisions, but we don't resolve them yet.
"""
import logging
from functools import partial
from typing import Any, Mapping, Optional, Iterable, Type

from antlr4 import ParserRuleContext
from attrs import define, field, resolve_types

from .datatypes import KeyOptMap, Ref


log = logging.getLogger(__name__)
log.setLevel(logging.INFO)



@define
class Base:
    """Represent a base class for all things."""
    src_ctx: Optional[ParserRuleContext] = field(kw_only=True, default=None)

@define
class Link(Base):
    """Represent a connection between two connectable things."""
    source_ref: Ref
    target_ref: Ref
     #FIXME: what to do here


@define
class Replace(Base):
    """Represent a replacement of one object with another."""
    original_ref: Ref
    replacement_ref: Ref

    replacement_obj: Optional["Object"] = None


@define
class Import(Base):
    """Represent an import statement."""
    what_ref: Ref
    from_name: str

    what_obj: Optional["Object"] = None


@define
class Object(Base):
    """Represent a container class."""
    supers_refs: tuple[Ref]
    locals_: KeyOptMap

    # these are a shortcut to the named locals - they're the same thing
    # this is here purely for efficiency
    named_locals: Mapping[Ref, Any] = field(init=False)
    unnamed_locals: Iterable[Any] = field(init=False)
    locals_by_type: Mapping[Type, tuple[Ref, Any]] = field(init=False)

    # configured post-construction
    closure: Optional[tuple["Object"]] = None

    supers_objs: Optional[tuple["Object"]] = None
    supers_bfs: Optional[tuple["Object"]] = None

    def __attrs_post_init__(self) -> None:
        """Set up the shortcuts to locals."""
        self.named_locals = self.locals_.named_items()
        self.unnamed_locals = tuple(self.locals_.unnamed_items())  # cast to tuple because otherwise it's lazy
        self.locals_by_type = self.locals_.map_items_by_type((Link, Replace, Import, Object))


resolve_types(Link)
resolve_types(Replace)
resolve_types(Import)
resolve_types(Object)


# these are the build-in superclasses that have special meaning to the compiler
MODULE_REF = Ref.from_one("module")
COMPONENT_REF = Ref.from_one("component")
PIN_REF = Ref.from_one("pin")
SIGNAL_REF = Ref.from_one("signal")
INTERFACE_REF = Ref.from_one("interface")


root_object = partial(Object, supers_refs=(), locals_=KeyOptMap(()), closure=())
MODULE = root_object(),
COMPONENT = Object(supers_refs=(MODULE_REF,), locals_=KeyOptMap(()), closure=()),
PIN = root_object(),
SIGNAL = root_object(),
INTERFACE = root_object(),


BUILTINS = {
    MODULE_REF: MODULE,
    COMPONENT_REF: COMPONENT,
    PIN_REF: PIN,
    SIGNAL_REF: SIGNAL,
    INTERFACE_REF: INTERFACE,
}
