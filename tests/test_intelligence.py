"""Unit tests for the Phase 3 code intelligence layer."""

from __future__ import annotations

from analyzer import Confidence, identify_project, scan_repository
from analyzer.intelligence import analyze_intelligence
from analyzer.intelligence.authentication import detect_authentication
from analyzer.intelligence.configuration import detect_configuration
from analyzer.intelligence.database import detect_database_models
from analyzer.intelligence.entrypoints import detect_entry_points
from analyzer.intelligence.importance import rank_important_files
from analyzer.intelligence.imports import analyze_imports, detect_circular_imports
from analyzer.intelligence.modules import analyze_modules
from analyzer.intelligence.relationships import build_module_dependencies
from analyzer.intelligence.routes import detect_routes


def write_files(root, files: dict[str, str]) -> None:
    """Materialise a fake repository from a ``{relative path: content}`` map."""
    for relative_path, content in files.items():
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def build(root, files: dict[str, str]):
    """Scan + identify a fixture repository (frameworks/env come from Phase 2)."""
    write_files(root, files)
    return identify_project(scan_repository(root))


def names(items) -> set[str]:
    return {item.name for item in items}


# --- entry points -------------------------------------------------


def test_fastapi_entry_point(tmp_path):
    project = build(
        tmp_path,
        {
            "requirements.txt": "fastapi\nuvicorn\n",
            "main.py": (
                "from fastapi import FastAPI\n"
                "import uvicorn\n"
                "app = FastAPI()\n"
                "app.include_router(None)\n"
                "if __name__ == '__main__':\n"
                "    uvicorn.run(app)\n"
            ),
        },
    )
    entry_points = detect_entry_points(project)
    kinds = {ep.kind for ep in entry_points}
    assert "fastapi_app" in kinds
    assert "script" in kinds
    fastapi_ep = next(ep for ep in entry_points if ep.kind == "fastapi_app")
    assert fastapi_ep.symbol == "app"
    assert any("uvicorn.run" in line for line in fastapi_ep.evidence)
    assert any("include_router" in line for line in fastapi_ep.evidence)


def test_flask_entry_point(tmp_path):
    project = build(
        tmp_path, {"app.py": "from flask import Flask\napp = Flask(__name__)\n"}
    )
    entry_points = detect_entry_points(project)
    assert len(entry_points) == 1
    assert entry_points[0].kind == "flask_app"
    assert entry_points[0].symbol == "app"


def test_django_manage_entry_point(tmp_path):
    project = build(tmp_path, {"manage.py": "#!/usr/bin/env python\n"})
    entry_points = detect_entry_points(project)
    assert len(entry_points) == 1
    assert entry_points[0].kind == "django_manage"


def test_cli_main_guard_entry_point(tmp_path):
    project = build(
        tmp_path,
        {"run.py": "def main():\n    pass\n\nif __name__ == '__main__':\n    main()\n"},
    )
    entry_points = detect_entry_points(project)
    assert len(entry_points) == 1
    assert entry_points[0].kind == "script"
    assert entry_points[0].confidence is Confidence.HIGH


def test_no_entry_point_for_plain_library_file(tmp_path):
    project = build(tmp_path, {"utils.py": "def helper():\n    return 1\n"})
    assert detect_entry_points(project) == ()


def test_no_entry_point_from_filename_alone(tmp_path):
    # main.py with no __main__ guard and no app object is not a guess.
    project = build(tmp_path, {"main.py": "x = 1\n"})
    assert detect_entry_points(project) == ()


# --- imports -------------------------------------------------


def test_internal_vs_external_imports(tmp_path):
    project = build(
        tmp_path,
        {
            "app.py": "import os\nimport helpers\n",
            "helpers.py": "x = 1\n",
        },
    )
    imports = analyze_imports(project)
    internal = [edge for edge in imports if edge.is_internal]
    external = [edge for edge in imports if not edge.is_internal]
    assert len(internal) == 1
    assert str(internal[0].resolved_file) == "helpers.py"
    assert len(external) == 1
    assert external[0].module == "os"


def test_nested_package_relative_imports(tmp_path):
    project = build(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/sub/__init__.py": "",
            "pkg/sub/mod.py": "from .. import top\nfrom . import sibling\n",
            "pkg/top.py": "x = 1\n",
            "pkg/sub/sibling.py": "y = 1\n",
        },
    )
    imports = analyze_imports(project)
    mod_imports = [e for e in imports if str(e.file) == "pkg/sub/mod.py"]
    resolved = {str(e.resolved_file) for e in mod_imports if e.resolved_file}
    assert "pkg/top.py" in resolved
    assert "pkg/sub/sibling.py" in resolved


def test_from_package_import_submodule_resolves_to_submodule_not_init(tmp_path):
    # Regression: `from pkg import sibling` must resolve to pkg/sibling.py,
    # not pkg/__init__.py — resolving to __init__.py fabricates cycles that
    # don't exist at runtime (D-021).
    project = build(
        tmp_path,
        {
            "pkg/__init__.py": "from pkg.sibling import thing\n",
            "pkg/sibling.py": "from pkg import helper\nthing = 1\n",
            "pkg/helper.py": "helper = 1\n",
        },
    )
    imports = analyze_imports(project)
    sibling_imports = [e for e in imports if str(e.file) == "pkg/sibling.py"]
    resolved = {str(e.resolved_file) for e in sibling_imports if e.resolved_file}
    assert resolved == {"pkg/helper.py"}
    assert detect_circular_imports(imports) == ()


def test_circular_import_detected(tmp_path):
    project = build(
        tmp_path,
        {
            "a.py": "from b import thing\n",
            "b.py": "from a import other\n",
        },
    )
    imports = analyze_imports(project)
    cycles = detect_circular_imports(imports)
    assert len(cycles) == 1
    assert set(cycles[0]) == {"a.py", "b.py"}


def test_no_circular_import_for_acyclic_graph(tmp_path):
    project = build(
        tmp_path,
        {"a.py": "from b import thing\n", "b.py": "x = 1\n"},
    )
    assert detect_circular_imports(analyze_imports(project)) == ()


def test_unresolvable_relative_import_beyond_top_level(tmp_path):
    project = build(tmp_path, {"mod.py": "from .. import thing\n"})
    imports = analyze_imports(project)
    assert imports[0].is_internal is False
    assert imports[0].resolved_file is None


# --- modules -------------------------------------------------


def test_module_metadata_extraction(tmp_path):
    project = build(
        tmp_path,
        {
            "sample.py": (
                "MAX_RETRIES = 3\n\n"
                "class Widget:\n    pass\n\n"
                "def build():\n    pass\n\n"
                "async def fetch():\n    pass\n\n"
                "def _private():\n    pass\n"
            )
        },
    )
    modules = analyze_modules(project)
    assert len(modules) == 1
    module = modules[0]
    assert module.classes == ("Widget",)
    assert module.functions == ("_private", "build")
    assert module.async_functions == ("fetch",)
    assert module.constants == ("MAX_RETRIES",)
    assert "_private" not in module.exports
    assert set(module.exports) == {"MAX_RETRIES", "Widget", "build", "fetch"}


def test_module_respects_dunder_all(tmp_path):
    project = build(
        tmp_path,
        {
            "sample.py": (
                "__all__ = ['build']\n\n"
                "def build():\n    pass\n\n"
                "def helper():\n    pass\n"
            )
        },
    )
    module = analyze_modules(project)[0]
    assert module.exports == ("build",)


# --- routes -------------------------------------------------


def test_fastapi_routes(tmp_path):
    project = build(
        tmp_path,
        {
            "requirements.txt": "fastapi\n",
            "main.py": (
                "from fastapi import FastAPI\napp = FastAPI()\n\n"
                "@app.get('/users')\ndef list_users():\n    pass\n\n"
                "@app.post('/login')\nasync def login():\n    pass\n"
            ),
        },
    )
    routes = detect_routes(project)
    assert len(routes) == 2
    assert {(r.method, r.path, r.framework) for r in routes} == {
        ("GET", "/users", "FastAPI"),
        ("POST", "/login", "FastAPI"),
    }


def test_flask_routes_with_methods_kwarg(tmp_path):
    project = build(
        tmp_path,
        {
            "requirements.txt": "flask\n",
            "app.py": (
                "from flask import Flask\napp = Flask(__name__)\n\n"
                "@app.route('/orders/<id>', methods=['DELETE'])\n"
                "def delete_order(id):\n    pass\n\n"
                "@app.route('/health')\ndef health():\n    pass\n"
            ),
        },
    )
    routes = detect_routes(project)
    assert {(r.method, r.path) for r in routes} == {
        ("DELETE", "/orders/<id>"),
        ("GET", "/health"),
    }
    assert all(r.framework == "Flask" for r in routes)


def test_django_routes_only_from_urls_py(tmp_path):
    project = build(
        tmp_path,
        {
            "urls.py": (
                "from django.urls import path\nfrom . import views\n\n"
                "urlpatterns = [path('users/', views.list_users)]\n"
            ),
            "not_urls.py": "path('/fake', None)\n",
        },
    )
    routes = detect_routes(project)
    assert len(routes) == 1
    assert routes[0].path == "users/"
    assert routes[0].framework == "Django"
    assert routes[0].method == "ANY"
    assert "list_users" in routes[0].handler


def test_no_routes_on_plain_repo(tmp_path):
    project = build(tmp_path, {"utils.py": "def helper():\n    pass\n"})
    assert detect_routes(project) == ()


# --- database -------------------------------------------------


def test_sqlalchemy_model_detected(tmp_path):
    project = build(
        tmp_path,
        {
            "models.py": (
                "from sqlalchemy.orm import declarative_base\n"
                "from sqlalchemy import Column, Integer, String\n\n"
                "Base = declarative_base()\n\n"
                "class User(Base):\n"
                "    __tablename__ = 'users'\n"
                "    id = Column(Integer, primary_key=True)\n"
                "    name = Column(String)\n"
            )
        },
    )
    models = detect_database_models(project)
    assert len(models) == 1
    assert models[0].name == "User"
    assert models[0].orm == "SQLAlchemy"
    assert models[0].table_name == "users"
    assert set(models[0].fields) == {"id", "name"}


def test_sqlalchemy_2x_mapped_style(tmp_path):
    project = build(
        tmp_path,
        {
            "models.py": (
                "from sqlalchemy.orm import Mapped, DeclarativeBase\n\n"
                "class Base(DeclarativeBase):\n    pass\n\n"
                "class User(Base):\n"
                "    __tablename__ = 'users'\n"
                "    id: Mapped[int]\n"
            )
        },
    )
    models = detect_database_models(project)
    user_model = next(m for m in models if m.name == "User")
    assert "id" in user_model.fields


def test_pydantic_model_detected(tmp_path):
    project = build(
        tmp_path,
        {
            "schemas.py": (
                "from pydantic import BaseModel\n\n"
                "class UserSchema(BaseModel):\n"
                "    id: int\n"
                "    name: str\n"
            )
        },
    )
    models = detect_database_models(project)
    assert len(models) == 1
    assert models[0].orm == "Pydantic"
    assert set(models[0].fields) == {"id", "name"}


def test_django_model_detected(tmp_path):
    project = build(
        tmp_path,
        {
            "models.py": (
                "from django.db import models\n\n"
                "class Order(models.Model):\n"
                "    total = models.IntegerField()\n"
                "    customer = models.ForeignKey(\n"
                "        'Customer', on_delete=models.CASCADE\n"
                "    )\n"
            )
        },
    )
    models = detect_database_models(project)
    assert len(models) == 1
    assert models[0].orm == "Django ORM"
    assert set(models[0].fields) == {"total", "customer"}


def test_flask_sqlalchemy_db_model_detected(tmp_path):
    project = build(
        tmp_path,
        {
            "models.py": (
                "from app import db\n\n"
                "class Note(db.Model):\n"
                "    id = db.Column(db.Integer, primary_key=True)\n"
            )
        },
    )
    models = detect_database_models(project)
    assert len(models) == 1
    assert models[0].orm == "SQLAlchemy"


def test_bare_unqualified_model_base_not_classified(tmp_path):
    # A class named Model with no recognisable qualifier is genuinely
    # ambiguous — never guess.
    project = build(
        tmp_path,
        {"thing.py": "class Model:\n    pass\n\nclass Foo(Model):\n    pass\n"},
    )
    assert detect_database_models(project) == ()


def test_no_database_models_on_plain_dataclass(tmp_path):
    project = build(
        tmp_path,
        {
            "note.py": (
                "from dataclasses import dataclass\n\n"
                "@dataclass\nclass Note:\n    id: int\n"
            )
        },
    )
    assert detect_database_models(project) == ()


# --- authentication -------------------------------------------------


def test_jwt_detected_via_import(tmp_path):
    project = build(
        tmp_path,
        {
            "auth.py": (
                "import jwt\n\n"
                "def encode(payload):\n"
                "    return jwt.encode(payload, 'secret')\n"
            )
        },
    )
    detections = detect_authentication(project)
    assert names(detections) == {"JWT"}


def test_oauth_and_depends_detected(tmp_path):
    project = build(
        tmp_path,
        {
            "requirements.txt": "fastapi\n",
            "auth.py": (
                "from fastapi import Depends\n"
                "from fastapi.security import OAuth2PasswordBearer\n\n"
                "oauth2_scheme = OAuth2PasswordBearer(tokenUrl='token')\n\n"
                "def get_current_user(token: str = Depends(oauth2_scheme)):\n    pass\n"
            ),
        },
    )
    detections = detect_authentication(project)
    assert names(detections) == {"OAuth", "FastAPI Depends()"}


def test_api_key_detected(tmp_path):
    project = build(
        tmp_path,
        {
            "security.py": (
                "from fastapi.security import APIKeyHeader\n\n"
                "api_key_scheme = APIKeyHeader(name='X-API-Key')\n"
            )
        },
    )
    assert names(detect_authentication(project)) == {"API Keys"}


def test_session_authentication_detected(tmp_path):
    project = build(tmp_path, {"app.py": "import flask_login\n"})
    assert names(detect_authentication(project)) == {"Session Authentication"}


def test_authentication_middleware_detected(tmp_path):
    project = build(
        tmp_path,
        {
            "main.py": (
                "from starlette.middleware.authentication import (\n"
                "    AuthenticationMiddleware,\n"
                ")\n\n"
                "app.add_middleware(AuthenticationMiddleware)\n"
            )
        },
    )
    assert names(detect_authentication(project)) == {"Authentication middleware"}


def test_no_authentication_on_plain_app(tmp_path):
    project = build(tmp_path, {"app.py": "def hello():\n    return 'hi'\n"})
    assert detect_authentication(project) == ()


# --- configuration -------------------------------------------------


def test_settings_module_detected_by_filename(tmp_path):
    project = build(tmp_path, {"settings.py": "DEBUG = True\n"})
    assert names(detect_configuration(project)) == {"Settings Module"}


def test_config_class_via_base_settings(tmp_path):
    project = build(
        tmp_path,
        {
            "config.py": (
                "from pydantic_settings import BaseSettings\n\n"
                "class Settings(BaseSettings):\n"
                "    debug: bool = False\n"
            )
        },
    )
    detections = {d.name: d for d in detect_configuration(project)}
    assert "Config Class" in detections
    assert "Settings Module" in detections  # filename convention too


def test_environment_loading_detected(tmp_path):
    project = build(
        tmp_path,
        {
            "app.py": (
                "import os\n"
                "port = os.getenv('PORT')\n"
                "debug = os.environ['DEBUG']\n"
            )
        },
    )
    assert names(detect_configuration(project)) == {"Environment Loading"}


def test_dotenv_usage_detected(tmp_path):
    project = build(
        tmp_path, {"app.py": "from dotenv import load_dotenv\nload_dotenv()\n"}
    )
    assert names(detect_configuration(project)) == {"dotenv usage"}


def test_no_configuration_on_plain_repo(tmp_path):
    project = build(tmp_path, {"utils.py": "def helper():\n    pass\n"})
    assert detect_configuration(project) == ()


# --- relationships / importance -------------------------------------------------


def test_module_dependencies_built_from_internal_imports(tmp_path):
    project = build(
        tmp_path,
        {
            "auth.py": "from database import get_session\n",
            "database.py": "def get_session():\n    pass\n",
        },
    )
    imports = analyze_imports(project)
    deps = build_module_dependencies(imports)
    assert len(deps) == 1
    assert str(deps[0].source) == "auth.py"
    assert str(deps[0].target) == "database.py"


def test_important_files_ranks_entry_points_and_fan_in(tmp_path):
    project = build(
        tmp_path,
        {
            "main.py": "if __name__ == '__main__':\n    pass\n",
            "shared.py": "x = 1\n",
            "a.py": "import shared\n",
            "b.py": "import shared\n",
            "c.py": "import shared\n",
        },
    )
    intelligence = analyze_intelligence(project)
    ranked_files = [str(f.file) for f in intelligence.important_files]
    assert "main.py" in ranked_files
    assert "shared.py" in ranked_files
    # shared.py has higher fan-in than main.py's single entry-point signal
    # would need to beat, but both should be present and scored.
    scores = {str(f.file): f.score for f in intelligence.important_files}
    assert scores["shared.py"] >= 3


def test_important_file_surfaces_from_filename_convention_alone(tmp_path):
    project = build(
        tmp_path, {"config.py": "DEBUG = True\n", "unrelated.py": "y = 1\n"}
    )
    intelligence = analyze_intelligence(project)
    ranked_files = {str(f.file) for f in intelligence.important_files}
    assert "config.py" in ranked_files
    assert "unrelated.py" not in ranked_files


def test_rank_important_files_empty_when_no_signals(tmp_path):
    project = build(tmp_path, {"random_module.py": "y = 1\n"})
    assert (
        rank_important_files(
            python_files=project.files_with_extension(".py"),
            entry_points=(),
            module_dependencies=(),
            routes=(),
            database_models=(),
        )
        == ()
    )


# --- robustness -------------------------------------------------


def test_malformed_python_file_does_not_crash_analysis(tmp_path):
    project = build(
        tmp_path,
        {
            "broken.py": "def foo(:\n    this is not valid python\n",
            "fine.py": "def helper():\n    pass\n",
        },
    )
    intelligence = analyze_intelligence(project)
    # broken.py is skipped, fine.py is still analysed.
    assert {str(m.file) for m in intelligence.modules} == {"fine.py"}


def test_empty_repository_analyzed_without_error(tmp_path):
    project = build(tmp_path, {"README.md": "hi\n"})
    intelligence = analyze_intelligence(project)
    assert intelligence.entry_points == ()
    assert intelligence.modules == ()
    assert intelligence.imports == ()
    assert intelligence.circular_imports == ()
    assert intelligence.routes == ()
    assert intelligence.database_models == ()
    assert intelligence.authentication == ()
    assert intelligence.configuration == ()
    assert intelligence.module_dependencies == ()
    assert intelligence.important_files == ()


def test_django_project_end_to_end(tmp_path):
    project = build(
        tmp_path,
        {
            "manage.py": "#!/usr/bin/env python\n",
            "myapp/models.py": (
                "from django.db import models\n\n"
                "class Post(models.Model):\n"
                "    title = models.CharField(max_length=200)\n"
            ),
            "myapp/urls.py": (
                "from django.urls import path\nfrom . import views\n\n"
                "urlpatterns = [path('posts/', views.post_list)]\n"
            ),
        },
    )
    intelligence = analyze_intelligence(project)
    assert any(ep.kind == "django_manage" for ep in intelligence.entry_points)
    assert len(intelligence.database_models) == 1
    assert intelligence.database_models[0].orm == "Django ORM"
    assert len(intelligence.routes) == 1
    assert intelligence.routes[0].framework == "Django"


def test_analyze_intelligence_preserves_earlier_phase_results(tmp_path):
    write_files(tmp_path, {"main.py": "print(1)\n"})
    scanned = scan_repository(tmp_path)
    identified = identify_project(scanned)
    intelligence = analyze_intelligence(identified)
    assert intelligence.files == scanned.files
    assert intelligence.stats == scanned.stats
    assert intelligence.repository_type == identified.repository_type
