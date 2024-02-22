#
# Drafted using ChatGPT and manually modified
#

import argparse
import importlib
import inspect
import pkgutil


def find_submodules(package):
    if isinstance(package, str):
        package = importlib.import_module(package)
    for _, modname, ispkg in pkgutil.walk_packages(
        package.__path__, package.__name__ + "."
    ):
        yield modname
        if ispkg:
            yield from find_submodules(modname)


def build_exception_tree(base_exception, root_module, tree=None, level=0):

    if tree is None:
        tree = {}
    for submodule_name in find_submodules(root_module):
        try:
            submodule = importlib.import_module(submodule_name)
        except ImportError:
            continue

        for name, obj in sorted(inspect.getmembers(submodule), key=lambda r: r[0]):
            if (
                inspect.isclass(obj)
                and issubclass(obj, base_exception)
                and obj is not base_exception
            ):
                parent = obj.__bases__[0].__name__  # Get immediate parent class name
                if parent not in tree:
                    tree[parent] = {"level": level, "children": []}
                tree.setdefault(obj.__name__, {"level": level + 1, "children": []})
                if obj.__name__ not in tree[parent]["children"]:
                    tree[parent]["children"].append(obj.__name__)

    return tree


def print_exception_tree(tree, parent=None, level=0):
    if parent is None:
        for parent, details in tree.items():
            if details["level"] == 0:
                print(parent)
                print_exception_tree(tree, parent, level=1)
    else:
        indent = " " * (level * 4)
        for child in tree[parent]["children"]:
            print(f"{indent}{child}")
            print_exception_tree(tree, child, level + 1)


def get_base_exception(dotted_path):
    *module_parts, exception_class_name = dotted_path.split(".")
    exception_module = importlib.import_module(".".join(module_parts))
    return getattr(exception_module, exception_class_name)


def main(package_name, exception_path):
    root_module = importlib.import_module(package_name)
    base_exception = get_base_exception(exception_path)
    exception_tree = build_exception_tree(base_exception, root_module)
    print_exception_tree(exception_tree)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Plot a tree of exceptions inherited from a base exception."
    )
    parser.add_argument(
        "package_name", help="The package name to search for exceptions."
    )
    parser.add_argument(
        "exception_path", help="The dotted path to the base exception class."
    )
    args = parser.parse_args()

    main(args.package_name, args.exception_path)
