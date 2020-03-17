#
#
# TODO: create tests based in the openapi-specs ??
# TODO: create client from openapi-specs
#
import sys
from pathlib import Path
from typing import Set

import attr
import black
from change_case import ChangeCase
from jinja2 import Environment, FileSystemLoader

# directories
current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

package_dir = (
    current_dir / ".." / "src" / "simcore_service_api_gateway"
).resolve()


# formatter
black_mode = black.FileMode()




def render_to_file(filepath, template, content):
    with open(filepath, "wt") as fh:
        code = template.render(**content)
        formatted_code = black.format_str(code, mode=black_mode)
        fh.write(formatted_code)
    return filepath


def as_class_name(name):
    cc = ChangeCase.snake_to_camel(name)
    cc = cc[0].upper() + cc[1:]
    return cc


# templates
template_env = Environment(
    autoescape=False, loader=FileSystemLoader(current_dir / "templates")
)
template_env.globals.update({"len": len, "cls_name": as_class_name})

template_std_endpoints = template_env.get_template(
    "resource_standard_methods.py.jinja2"
)
template_custom_endpoints = template_env.get_template(
    "resource_custom_methods.py.jinja2"
)
template_cruds = template_env.get_template("cruds.py.jinja2")

template_orm = template_env.get_template("orm.py.jinja2")



@attr.s(auto_attribs=True)
class Generator:
    generated: Set[Path] = set()

    def _render_to_file(self, filepath, template, content):
        filepath = render_to_file(filepath, template, content)
        self.generated.add(filepath)

    def create_resource(self, resource_name):
        rn = resource_name.lower()

        content = {"rn": rn, "rnp": rn + "s", "rncc": as_class_name(resource_name)}

        self._render_to_file(
            package_dir / "endpoints" / f"{rn}_std.py", template_std_endpoints, content,
        )

        self._render_to_file(
            package_dir / "store" / f"crud_{rn}.py", template_cruds, content,
        )

        self._render_to_file(
            package_dir / "orm" / f"orm_{rn}.py", template_orm, content,
        )

    def dump(self):
        pass

    def clean(self):
        while self.generated:
            fp: Path = self.generated.pop()
            fp.unlink()


if __name__ == "__main__":
    g = Generator()
    g.create_resource("nice_resource")
