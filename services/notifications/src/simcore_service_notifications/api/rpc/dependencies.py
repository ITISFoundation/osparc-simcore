from functools import partial
from typing import Any

from common_library.json_serialization import json_dumps
from fastapi import FastAPI
from jinja2 import Environment, PackageLoader, select_autoescape

from ...clients.celery import get_task_manager
from ...core.settings import ApplicationSettings
from ...renderers import JinjaRenderer, Renderer
from ...repositories.product import ProductRepository
from ...repositories.template import FileTemplateRepository, TemplateRepository
from ...services import MessageService, TemplateService

_json_dumps_indented = partial(json_dumps, indent=2)


def get_jinja_env(**kwargs: Any) -> Environment:
    env = Environment(
        loader=PackageLoader("simcore_service_notifications", "templates"),
        autoescape=select_autoescape(["html", "xml", "j2"]),
        extensions=["jinja2.ext.i18n"],
        **kwargs,
    )
    env.globals["dumps"] = _json_dumps_indented
    # Install no-op translations as a safe default so templates that use
    # {{ _('text') }} or {% trans %} work even before locale-specific
    # .mo files are deployed.
    import gettext as _gettext  # noqa: PLC0415

    env.install_gettext_translations(_gettext.NullTranslations(), newstyle=True)  # type: ignore[attr-defined]
    return env


# Repositories


def get_product_repository(app: FastAPI) -> ProductRepository:
    return ProductRepository(engine=app.state.engine)


def get_template_repository(env: Environment | None = None) -> TemplateRepository:
    return FileTemplateRepository(env if env is not None else get_jinja_env())


# Services


def get_renderer(template_repository: TemplateRepository | None = None) -> Renderer:
    return JinjaRenderer(template_repository if template_repository is not None else get_template_repository())


def get_template_service(
    app: FastAPI,
    template_repository: TemplateRepository | None = None,
    renderer: Renderer | None = None,
) -> TemplateService:
    repo = template_repository if template_repository is not None else get_template_repository()
    rend = renderer if renderer is not None else get_renderer(repo)
    product_repo = get_product_repository(app)
    return TemplateService(repo, rend, product_repo)


def get_message_service(
    app: FastAPI,
    template_service: TemplateService | None = None,
) -> MessageService:
    settings: ApplicationSettings = app.state.settings

    return MessageService(
        template_service if template_service is not None else get_template_service(app),
        get_product_repository(app),
        get_task_manager(app),
        settings,
    )
