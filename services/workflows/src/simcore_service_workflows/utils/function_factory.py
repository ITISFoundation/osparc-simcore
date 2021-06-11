"""
ORIGINALLY from https://gist.github.com/dhagrow/d3414e3c6ae25dfa606238355aea2ca5

Python is a dynamic language, and it is relatively easy to dynamically create
and modify things such as classes and objects. Functions, however, are quite
challenging to create dynamicallcallback.
One area where we might want to do this is in an RPC library, where a function
defined on a server needs to be available remotely on a client.
The naive solution is to simply pass arguments to a generic function that
accepts `*args` and `**kwargs`. A lot of information is lost with this approach,
however, in particular the number of arguments taken. Used in an RPC
implementation, this also delays any error feedback until after the arguments
have reached the server.
If you search online, most practical solutions involve `exec()`. This is
generally the approach chosen by many Python RPC libraries. This is, of course,
a very insecure solution, one that opens any program up to malicious code
execution.
This experiment creates a real function at the highest layer available: the AST.
There are several challenges to this approach. The most significant is that on
the AST layer, function arguments must be defined according to their type. This
greatly limits the flexibility allowed when defining a function with Python
syntax.
This experiment has a few requirements that introduce (and relieve) additional
 challenges:
- Must return a representative function signature to the Python interpreter
- Must allow serialization to JSON and/or MsgPack
"""

from __future__ import print_function

import ast
import collections
import numbers
import sys
import types


def _create_function_v1(name, signature, callback):
    """Dynamically creates a function that wraps a call to *callback*, based
    on the provided *signature*.
    Note that only default arguments with a value of `None` are supported. Any
    other value will raise a `TypeError`.
    """
    # utils to set default values when creating a ast objects
    Loc = lambda cls, **kw: cls(annotation=None, lineno=1, col_offset=0, **kw)
    Name = lambda id, ctx=None: Loc(ast.Name, id=id, ctx=ctx or ast.Load())

    # vars for the callback call
    call_args = []
    call_keywords = []
    call_starargs = None  # PY2
    call_kwargs = None  # PY2

    # vars for the generated function signature
    func_args = []
    func_defaults = []
    vararg = None
    kwarg = None

    # vars for the args with default values
    defaults = []

    # assign args based on *signature*
    for param in viewvalues(signature.parameters):
        if param.default is not param.empty:
            if isinstance(param.default, type(None)):
                # `ast.NameConstant` is used in PY3, but both support `ast.Name`
                func_defaults.append(Name("None"))
            elif isinstance(param.default, bool):
                # `ast.NameConstant` is used in PY3, but both support `ast.Name`
                func_defaults.append(Name(str(param.default)))
            elif isinstance(param.default, numbers.Number):
                func_defaults.append(Loc(ast.Num, n=param.default))
            elif isinstance(param.default, str):
                func_defaults.append(Loc(ast.Str, s=param.default))
            elif isinstance(param.default, bytes):
                func_defaults.append(Loc(ast.Bytes, s=param.default))
            elif isinstance(param.default, list):
                func_defaults.append(Loc(ast.List, elts=param.default, ctx=ast.Load()))
            elif isinstance(param.default, tuple):
                func_defaults.append(
                    Loc(ast.Tuple, elts=list(param.default), ctx=ast.Load())
                )
            elif isinstance(param.default, dict):
                func_defaults.append(
                    Loc(
                        ast.Dict,
                        keys=list(viewkeys(param.default)),
                        values=list(viewvalues(param.default)),
                    )
                )
            else:
                err = "unsupported default argument type: {}"
                raise TypeError(err.format(type(param.default)))
            defaults.append(param.default)
            # func_defaults.append(Name('None'))
            # defaults.append(None)

        if param.kind in {param.POSITIONAL_ONLY, param.POSITIONAL_OR_KEYWORD}:
            call_args.append(Name(param.name))
            func_args.append(Loc(ast.arg, arg=param.name))
        elif param.kind == param.VAR_POSITIONAL:
            call_args.append(Loc(ast.Starred, value=Name(param.name), ctx=ast.Load()))
            vararg = Loc(ast.arg, arg=param.name)

        elif param.kind == param.KEYWORD_ONLY:
            err = "TODO: KEYWORD_ONLY param support, param: {}"
            raise TypeError(err.format(param.name))
        elif param.kind == param.VAR_KEYWORD:
            call_keywords.append(Loc(ast.keyword, arg=None, value=Name(param.name)))
            kwarg = Loc(ast.arg, arg=param.name)

    # generate the ast for the *callback* call
    call_ast = Loc(
        ast.Call,
        func=Name(callback.__name__),
        args=call_args,
        keywords=call_keywords,
        starargs=call_starargs,
        kwargs=call_kwargs,
    )

    # generate the function ast
    func_ast = Loc(
        ast.FunctionDef,
        name=to_func_name(name),
        args=ast.arguments(
            args=func_args,
            vararg=vararg,
            defaults=func_defaults,
            kwarg=kwarg,
            kwonlyargs=[],
            kw_defaults=[],
        ),
        body=[Loc(ast.Return, value=call_ast)],
        decorator_list=[],
        returns=None,
    )

    # compile the ast and get the function code
    mod_ast = ast.Module(body=[func_ast])
    module_code = compile(mod_ast, "<generated-ast>", "exec")
    func_code = [c for c in module_code.co_consts if isinstance(c, types.CodeType)][0]

    # return the generated function
    return types.FunctionType(
        func_code, {callback.__name__: callback}, argdefs=tuple(defaults)
    )


##
## support functions
##


def viewitems(obj):
    return getattr(obj, "viewitems", obj.items)()


def viewkeys(obj):
    return getattr(obj, "viewkeys", obj.keys)()


def viewvalues(obj):
    return getattr(obj, "viewvalues", obj.values)()


def to_func_name(name):
    # func.__name__ must be bytes in Python2
    return to_unicode(name) if PY3 else to_bytes(name)


def to_bytes(s, encoding="utf8"):
    if isinstance(s, bytes):
        pass
    elif isinstance(s, str):
        s = s.encode(encoding)
    return s


def to_unicode(s, encoding="utf8"):
    if isinstance(s, bytes):
        s = s.decode(encoding)
    elif isinstance(s, str):
        pass
    elif isinstance(s, dict):
        s = {to_unicode(k): to_unicode(v) for k, v in viewitems(s)}
    elif isinstance(s, collections.Iterable):
        s = [to_unicode(x, encoding) for x in s]
    return s


def _create_function_v2(name, args, callback):

    y_code = types.CodeType(
        args,
        callback.func_code.co_nlocals,
        callback.func_code.co_stacksize,
        callback.func_code.co_flags,
        callback.func_code.co_code,
        callback.func_code.co_consts,
        callback.func_code.co_names,
        callback.func_code.co_varnames,
        callback.func_code.co_filename,
        name,
        callback.func_code.co_firstlineno,
        callback.func_code.co_lnotab,
    )

    return types.FunctionType(y_code, callback.func_globals, name)


create_function = _create_function_v1
