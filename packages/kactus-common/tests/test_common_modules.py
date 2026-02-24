"""Tests for new kactus-common modules: exceptions, schemas, logging, oltp, events."""

import pytest


class TestExceptions:
    """Verify KactusException hierarchy and behaviour."""

    def test_base_exception(self):
        from kactus_common.exceptions import KactusException
        exc = KactusException("something went wrong", code="TEST", tip="Try again")
        assert exc.message == "something went wrong"
        assert exc.code == "TEST"
        assert exc.tip == "Try again"
        assert exc.data is None

    def test_to_dict(self):
        from kactus_common.exceptions import KactusException
        exc = KactusException("fail", code="ERR", data={"id": 1})
        d = exc.to_dict()
        assert d["code"] == "ERR"
        assert d["message"] == "fail"
        assert d["data"] == {"id": 1}
        assert "tip" not in d  # None values omitted

    def test_subclass_default_codes(self):
        from kactus_common.exceptions import (
            InvalidArgumentError, NotFoundError,
            ConfigurationError, DatabaseError, DataSourceError,
        )
        assert InvalidArgumentError().code == "INVALID_ARGUMENT"
        assert NotFoundError().code == "NOT_FOUND"
        assert ConfigurationError().code == "CONFIGURATION_ERROR"
        assert DatabaseError().code == "DATABASE_ERROR"
        assert DataSourceError().code == "DATA_SOURCE_ERROR"

    def test_subclass_custom_message(self):
        from kactus_common.exceptions import NotFoundError
        exc = NotFoundError("User not found", tip="Check user ID")
        assert exc.message == "User not found"
        assert exc.tip == "Check user ID"
        assert exc.code == "NOT_FOUND"

    def test_subclass_override_code(self):
        from kactus_common.exceptions import DatabaseError
        exc = DatabaseError("conn failed", code="PG_CONN_FAIL")
        assert exc.code == "PG_CONN_FAIL"

    def test_is_exception(self):
        from kactus_common.exceptions import KactusException, NotFoundError
        assert issubclass(NotFoundError, KactusException)
        assert issubclass(NotFoundError, Exception)

    def test_install_exception_handlers(self):
        from kactus_common.exceptions import install_exception_handlers
        from fastapi import FastAPI
        app = FastAPI()
        install_exception_handlers(app)
        # Should have registered a handler (no error)
        assert app.exception_handlers is not None


class TestSchemas:
    """Verify shared Pydantic schemas."""

    def test_response_model(self):
        from kactus_common.schemas import ResponseModel
        resp = ResponseModel(data={"key": "val"})
        assert resp.code == "0"
        assert resp.msg == "success"
        assert resp.data == {"key": "val"}

    def test_pagination(self):
        from kactus_common.schemas import Pagination
        p = Pagination(total=100, items=["a", "b"])
        assert p.total == 100
        assert len(p.items) == 2

    def test_base_schema_strips_whitespace(self):
        from kactus_common.schemas import BaseSchema

        class MySchema(BaseSchema):
            name: str

        s = MySchema(name="  hello  ")
        assert s.name == "hello"

    def test_base_schema_empty_string_to_none(self):
        from kactus_common.schemas import BaseSchema

        class MySchema(BaseSchema):
            age: int | None = None

        s = MySchema(age="")
        assert s.age is None

    def test_base_schema_keeps_empty_string_for_str_fields(self):
        from kactus_common.schemas import BaseSchema

        class MySchema(BaseSchema):
            name: str

        s = MySchema(name="")
        assert s.name == ""


class TestLogging:
    """Verify logging configuration."""

    def test_configure_logging_no_error(self):
        from kactus_common.logging import configure_logging
        configure_logging(level="DEBUG", log_file=None)

    def test_configure_logging_with_file(self, tmp_path):
        from kactus_common.logging import configure_logging
        log_file = tmp_path / "test.log"
        configure_logging(level="INFO", log_file=str(log_file))


class TestOLTP:
    """Verify OLTP database module imports."""

    def test_import_session_manager(self):
        from kactus_common.database.oltp import DatabaseSessionManager
        assert DatabaseSessionManager is not None

    def test_session_manager_init(self):
        from kactus_common.database.oltp import DatabaseSessionManager
        db = DatabaseSessionManager("sqlite+aiosqlite:///test.db")
        assert db._database_url == "sqlite+aiosqlite:///test.db"

    def test_import_models(self):
        from kactus_common.database.oltp.models import (
            Base, ModelMixin, AuditMixin, AuditCreatorMixin,
            LogicalDeleteMixin, ExecutionMixin,
            utcnow, resolve_table_name,
        )
        assert Base is not None
        assert ModelMixin is not None

    def test_resolve_table_name(self):
        from kactus_common.database.oltp.models import resolve_table_name
        assert resolve_table_name("UserProfile") == "user_profiles"

    def test_import_types(self):
        from kactus_common.database.oltp.types import (
            DateTimeTzAware, UnsignedBigInt, UUIDList,
            MutableList, MutableDict, PydanticJSONDict, PydanticJSONList,
        )
        assert DateTimeTzAware is not None

    def test_snowflake_id(self):
        from kactus_common.database.oltp.snowflake_id import next_id
        id1 = next_id()
        id2 = next_id()
        assert isinstance(id1, int)
        assert id1 != id2

    def test_convert_to_async_url(self):
        from kactus_common.database.oltp.session import convert_to_async_url
        assert convert_to_async_url("postgresql://host/db") == "postgresql+asyncpg://host/db"
        assert convert_to_async_url("mysql://host/db") == "mysql+asyncmy://host/db"
        assert convert_to_async_url("sqlite:///test.db") == "sqlite:///test.db"


class TestEvents:
    """Verify events module imports."""

    def test_import_events(self):
        from kactus_common.events import (
            dispatch_event, register_handler,
            BaseEventName, BaseEventPayload,
            CompositeDispatcher,
        )
        assert dispatch_event is not None
        assert register_handler is not None

    def test_import_backends(self):
        from kactus_common.events.backends.blinker import BlinkerDispatcher
        from kactus_common.events.backends.composite import CompositeDispatcher
        from kactus_common.events.backends.fastapi_events import FastAPIEventsDispatcher
        assert BlinkerDispatcher is not None
        assert CompositeDispatcher is not None
        assert FastAPIEventsDispatcher is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
