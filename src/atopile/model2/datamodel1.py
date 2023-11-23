"""
This datamodel represents the code in a clean, simple and traversable way,
but doesn't resolve names of things.
In building this datamodel, we check for name collisions, but we don't resolve them yet.
"""
import enum
import itertools
import logging
from typing import Any, Iterable, Optional, Mapping

from antlr4 import ParserRuleContext
from attrs import define, field

from atopile.model2 import errors
from atopile.parser.AtopileParser import AtopileParser as ap
from atopile.parser.AtopileParserVisitor import AtopileParserVisitor

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


class Ref(tuple[str | int]):
    """Shell class to provide basic utils for a reference."""

    @classmethod
    def from_one(cls, name: str | int) -> "Ref":
        """Return a Ref with a single item."""
        return cls((name,))


class KeyOptItem(tuple[Ref, Any]):
    """A class representing anf optionally-named thing."""
    @property
    def ref(self) -> Optional[Ref]:
        """Return the name of this item, if it has one."""
        return self[0]

    @property
    def value(self) -> Any:
        """Return the value of this item."""
        return self[1]

    @classmethod
    def from_kv(cls, key: Optional[Ref], value: Any) -> "KeyOptItem":
        """Return a KeyOptItem with a single item."""
        return KeyOptItem((key, value))


class KeyOptMap(tuple[KeyOptItem]):
    """A class representing a set of optionally-named things."""
    def get_named_items(self) -> Mapping[str, Any]:
        """Return all the named items in this set, ignoring the unnamed ones."""
        return dict(filter(lambda x: x.ref is not None, self))

    def get_unnamed_items(self) -> Iterable[Any]:
        """Return an interable of all the unnamed items in this set."""
        return map(lambda x: x.value, filter(lambda x: x.ref is None, self))

    def keys(self) -> Iterable[Ref]:
        """Return an iterable of all the names in this set."""
        return map(lambda x: x.ref, filter(lambda x: x.ref is not None, self))

    def values(self) -> Iterable[Any]:
        """Return an iterable of all the values in this set."""
        return map(lambda x: x.value, self)

    @classmethod
    def from_item(cls, item: KeyOptItem) -> "KeyOptMap":
        """Return a KeyOptMap with a single item."""
        return KeyOptMap((item,))

    @classmethod
    def from_kv(cls, key: Optional[Ref], value: Any) -> "KeyOptMap":
        """Return a KeyOptMap with a single item."""
        return cls.from_item(KeyOptItem.from_kv(key, value))


@define
class Base:
    """Base class for all objects in the datamodel."""
    # this is optional only because it makes testing convenient
    src_ctx: ParserRuleContext = field(default=None, kw_only=True, eq=False)


@define
class Link(Base):
    """Represent a connection between two connectable things."""
    source: Ref
    target: Ref


@define
class Replace(Base):
    """Represent a replacement of one object with another."""
    original: Ref
    replacement: Ref


@define
class Import(Base):
    """Represent an import statement."""
    what: Ref
    from_: str


@define
class Object(Base):
    """Represent a container class."""
    supers: tuple[Ref]
    locals_: KeyOptMap
    name_bindings: Mapping[str, Any]


# these are the build-in superclasses that have special meaning to the compiler
MODULE = (Ref.from_one("module"),)
COMPONENT = MODULE + (Ref.from_one("component"),)

PIN = (Ref.from_one("pin"),)
SIGNAL = (Ref.from_one("signal"),)
INTERFACE = (Ref.from_one("interface"),)


## Builder

class _Sentinel(enum.Enum):
    NOTHING = enum.auto()


NOTHING = _Sentinel.NOTHING


class Dizzy(AtopileParserVisitor):
    """
    Dizzy is responsible for mixing cement, sand, aggregate, and water to create concrete.
    Ref.: https://www.youtube.com/watch?v=drBge9JyloA
    """

    def __init__(
        self,
        src_path: str,
    ) -> None:
        self.src_path = src_path
        super().__init__()

    def defaultResult(self):
        return NOTHING

    def visit_iterable_helper(
        self, children: Iterable
    ) -> KeyOptMap:
        """
        Visit multiple children and return a tuple of their results,
        discard any results that are NOTHING and flattening the children's results.
        It is assumed the children are returning their own OptionallyNamedItems.
        """
        results = (self.visit(child) for child in children)
        return KeyOptMap(itertools.chain(*filter(lambda x: x is not NOTHING, results)))

    def visitSimple_stmt(self, ctx: ap.Simple_stmtContext) -> _Sentinel | KeyOptItem:
        """
        This is practically here as a development shim to assert the result is as intended
        """
        result = self.visitChildren(ctx)
        if result is not NOTHING:
            assert isinstance(result, KeyOptMap)
            if len(result) > 0:
                assert isinstance(result[0], KeyOptItem)
                if result[0].ref is not None:
                    assert isinstance(result[0].ref, Ref)
                assert len(result[0]) == 2
        return result

    def visitStmt(self, ctx: ap.StmtContext) -> KeyOptMap:
        """
        Ensure consistency of return type
        """
        if ctx.simple_stmts():
            value = self.visitSimple_stmts(ctx.simple_stmts())
        elif ctx.compound_stmt():
            value = KeyOptMap((self.visit(ctx.compound_stmt()),))
        else:
            raise errors.AtoError("Unexpected statement type")
        return value

    def visitSimple_stmts(
        self, ctx: ap.Simple_stmtsContext
    ) -> KeyOptMap:
        return self.visit_iterable_helper(ctx.simple_stmt())

    def visitTotally_an_integer(self, ctx: ap.Totally_an_integerContext) -> int:
        text = ctx.getText()
        try:
            return int(text)
        except ValueError as ex:
            raise errors.AtoTypeError(f"Expected an integer, but got {text}") from ex

    def visitFile_input(self, ctx: ap.File_inputContext) -> Object:
        locals_ = self.visit_iterable_helper(ctx.stmt())

        return Object(
            locals_=locals_,
            name_bindings = locals_.get_named_items(),
            supers=MODULE,
            src_ctx=ctx,
        )

    def visitBlocktype(self, ctx: ap.BlocktypeContext) -> tuple[Ref]:
        block_type_name = ctx.getText()
        match block_type_name:
            case "module":
                return MODULE
            case "component":
                return COMPONENT
            case "interface":
                return INTERFACE
            case _:
                raise errors.AtoError(f"Unknown block type '{block_type_name}'")

    def visit_ref_helper(
        self,
        ctx: ap.NameContext
        | ap.AttrContext
        | ap.Name_or_attrContext
        | ap.Totally_an_integerContext,
    ) -> Ref:
        """
        Visit any referencey thing and ensure it's returned as a reference
        """
        if isinstance(
            ctx,
            (ap.NameContext, ap.Totally_an_integerContext, ap.Numerical_pin_refContext),
        ):
            return Ref.from_one(str(self.visit(ctx)))
        if isinstance(ctx, (ap.AttrContext, ap.Name_or_attrContext)):
            return Ref(map(str, self.visit(ctx)),)
        raise errors.AtoError(f"Unknown reference type: {type(ctx)}")

    def visitName(self, ctx: ap.NameContext) -> str | int:
        """
        If this is an int, convert it to one (for pins), else return the name as a string.
        """
        try:
            return int(ctx.getText())
        except ValueError:
            return ctx.getText()

    def visitAttr(self, ctx: ap.AttrContext) -> Ref:
        return Ref(self.visitName(name) for name in ctx.name())  # Comprehension

    def visitName_or_attr(self, ctx: ap.Name_or_attrContext) -> Ref:
        if ctx.name():
            name = self.visitName(ctx.name())
            return Ref.from_one(name)
        elif ctx.attr():
            return self.visitAttr(ctx.attr())

        raise errors.AtoError("Expected a name or attribute")

    def visitBlock(self, ctx) -> KeyOptMap:
        if ctx.simple_stmts():
            return self.visitSimple_stmts(ctx.simple_stmts())
        elif ctx.stmt():
            return self.visit_iterable_helper(ctx.stmt())
        else:
            raise errors.AtoError("Unexpected block type")

    def visitBlockdef(self, ctx: ap.BlockdefContext) -> KeyOptItem:
        block_returns = self.visitBlock(ctx.block())

        if ctx.FROM():
            if not ctx.name_or_attr():
                raise errors.AtoError("Expected a name or attribute after 'from'")
            block_supers = (self.visit_ref_helper(ctx.name_or_attr()),)
        else:
            block_supers = self.visitBlocktype(ctx.blocktype())

        return KeyOptItem.from_kv(
            self.visit_ref_helper(ctx.name()),
            Object(
                supers=block_supers,
                locals_=block_returns,
                name_bindings=block_returns.get_named_items(),
                src_ctx=ctx,
            ),
        )

    def visitPindef_stmt(
        self, ctx: ap.Pindef_stmtContext
    ) -> KeyOptMap:
        ref = self.visit_ref_helper(ctx.totally_an_integer() or ctx.name())

        if not ref:
            raise errors.AtoError("Pins must have a name")

        # TODO: reimplement this error handling at the above level
        created_pin = Object(
            supers=PIN,
            locals_=KeyOptMap(),
            name_bindings={},
            src_ctx=ctx,
        )

        return KeyOptMap.from_kv(ref, created_pin)

    def visitSignaldef_stmt(
        self, ctx: ap.Signaldef_stmtContext
    ) -> KeyOptMap:
        name = self.visit_ref_helper(ctx.name())

        # TODO: provide context of where this error was found within the file
        if not name:
            raise errors.AtoError("Signals must have a name")

        created_signal = Object(
            supers=SIGNAL,
            locals_=KeyOptMap(),
            name_bindings={},
            src_ctx=ctx,
        )
        # TODO: reimplement this error handling at the above level
        # if name in self.scope:
        #     raise errors.AtoNameConflictError(
        #         f"Cannot redefine '{name}' in the same scope"
        #     )
        return KeyOptMap.from_kv(name, created_signal)

    # Import statements have no ref
    def visitImport_stmt(self, ctx: ap.Import_stmtContext) -> KeyOptMap:
        from_file: str = self.visitString(ctx.string())
        imported_element = self.visit_ref_helper(ctx.name_or_attr())

        if not from_file:
            raise errors.AtoError("Expected a 'from <file-path>' after 'import'")
        if not imported_element:
            raise errors.AtoError(
                "Expected a name or attribute to import after 'import'"
            )

        if imported_element == "*":
            # import everything
            raise NotImplementedError("import *")

        import_ = Import(
            what=imported_element,
            from_=from_file,
            src_ctx=ctx,
        )

        return KeyOptMap.from_kv(imported_element, import_)

    # if a signal or a pin def statement are executed during a connection, it is returned as well
    def visitConnectable(
        self, ctx: ap.ConnectableContext
    ) -> tuple[Ref, Optional[KeyOptItem]]:
        if ctx.name_or_attr():
            # Returns a tuple
            return self.visit_ref_helper(ctx.name_or_attr()), None
        elif ctx.numerical_pin_ref():
            return self.visit_ref_helper(ctx.numerical_pin_ref()), None
        elif ctx.pindef_stmt() or ctx.signaldef_stmt():
            connectable: KeyOptMap = self.visitChildren(ctx)
            # return the object's ref and the created object itself
            return connectable[0][0], connectable[0]
        else:
            raise ValueError("Unexpected context in visitConnectable")

    def visitConnect_stmt(
        self, ctx: ap.Connect_stmtContext
    ) -> KeyOptMap:
        """
        Connect interfaces together
        """
        source_name, source = self.visitConnectable(ctx.connectable(0))
        target_name, target = self.visitConnectable(ctx.connectable(1))

        returns = [
            KeyOptItem.from_kv(
                None,
                Link(source_name, target_name, src_ctx=ctx),
            )
        ]

        # If the connect statement is also used to instantiate
        # an element, add it to the return tuple
        if source:
            returns.append(source)

        if target:
            returns.append(target)

        return KeyOptMap(returns)

    def visitNew_stmt(self, ctx: ap.New_stmtContext) -> Object:
        class_to_init = self.visit_ref_helper(ctx.name_or_attr())

        return Object(
            supers=(class_to_init,),
            locals_=KeyOptMap(),
            name_bindings={},
            src_ctx=ctx,
        )

    def visitString(self, ctx: ap.StringContext) -> str:
        return ctx.getText().strip("\"'")

    def visitBoolean_(self, ctx: ap.Boolean_Context) -> bool:
        return ctx.getText().lower() == "true"

    def visitAssignable(
        self, ctx: ap.AssignableContext
    ) -> KeyOptItem | int | float | str:
        """Yield something we can place in a set of locals."""
        if ctx.name_or_attr():
            raise errors.AtoError(
                "Cannot directly reference another object like this. Use 'new' instead."
            )

        if ctx.new_stmt():
            return self.visit(ctx.new_stmt())

        if ctx.NUMBER():
            value = float(ctx.NUMBER().getText())
            return int(value) if value.is_integer() else value

        if ctx.string():
            return self.visitString(ctx)

        if ctx.boolean_():
            return self.visitBoolean_(ctx.boolean_())

        raise errors.AtoError("Unexpected assignable type")

    def visitAssign_stmt(self, ctx: ap.Assign_stmtContext) -> KeyOptMap:
        assigned_value_name = self.visitName_or_attr(ctx.name_or_attr())
        assigned_value = self.visitAssignable(ctx.assignable())

        return KeyOptMap.from_kv(assigned_value_name, assigned_value)

    def visitRetype_stmt(
        self, ctx: ap.Retype_stmtContext
    ) -> KeyOptMap:
        """
        This statement type will replace an existing block with a new one of a subclassed type

        Since there's no way to delete elements, we can be sure that the subclass is
        a superset of the superclass (confusing linguistically, makes sense logically)
        """
        original_name = self.visit_ref_helper(ctx.name_or_attr(0))
        replaced_name = self.visit_ref_helper(ctx.name_or_attr(1))

        replace = Replace(
            src_ctx=ctx,
            original=original_name,
            replacement=replaced_name,
        )

        return KeyOptMap.from_kv(None, replace)
