"""Mirror of the TypeScript test suite — all Appendix B cases + edge cases."""
import math
import pytest
from terse import parse, serialize, parse_document, serialize_document, TerseError


# ─── Primitives ───────────────────────────────────────────────────────────────

class TestPrimitivesRparse:
    def test_null(self):            assert parse("~") is None
    def test_true(self):            assert parse("T") is True
    def test_false(self):           assert parse("F") is False
    def test_zero(self):            assert parse("0") == 0
    def test_int(self):             assert parse("42") == 42
    def test_neg_int(self):         assert parse("-1") == -1
    def test_float(self):           assert parse("3.14") == pytest.approx(3.14)
    def test_scientific(self):      assert parse("1e3") == 1000
    def test_scientific_small(self):assert parse("1.5e-10") == pytest.approx(1.5e-10)
    def test_safe_id(self):         assert parse("hello") == "hello"
    def test_domain(self):          assert parse("api.example.com") == "api.example.com"
    def test_path(self):            assert parse("/usr/local/bin") == "/usr/local/bin"
    def test_semver(self):          assert parse("v2.1.0") == "v2.1.0"
    def test_email(self):           assert parse("alice@co.com") == "alice@co.com"
    def test_quoted(self):          assert parse('"hello world"') == "hello world"
    def test_literal_T(self):       assert parse('"T"') == "T"
    def test_literal_F(self):       assert parse('"F"') == "F"
    def test_literal_tilde(self):   assert parse('"~"') == "~"
    def test_escape_newline(self):  assert parse('"a\\nb"') == "a\nb"
    def test_escape_tab(self):      assert parse('"a\\tb"') == "a\tb"
    def test_escape_backslash(self):assert parse('"a\\\\b"') == "a\\b"
    def test_escape_unicode(self):  assert parse('"\\u0041"') == "A"


class TestPrimitivesSerialize:
    def test_null(self):            assert serialize(None) == "~"
    def test_true(self):            assert serialize(True) == "T"
    def test_false(self):           assert serialize(False) == "F"
    def test_zero(self):            assert serialize(0) == "0"
    def test_int(self):             assert serialize(42) == "42"
    def test_neg(self):             assert serialize(-1) == "-1"
    def test_float(self):           assert serialize(3.14) == "3.14"
    def test_safe_str(self):        assert serialize("hello") == "hello"
    def test_str_T(self):           assert serialize("T") == '"T"'
    def test_str_F(self):           assert serialize("F") == '"F"'
    def test_str_tilde(self):       assert serialize("~") == '"~"'
    def test_str_space(self):       assert serialize("hello world") == '"hello world"'
    def test_str_1e3(self):         assert serialize("1e3") == '"1e3"'
    def test_inf_throws(self):
        with pytest.raises(TerseError):
            serialize(float("inf"))
    def test_nan_throws(self):
        with pytest.raises(TerseError):
            serialize(float("nan"))


class TestPrimitivesRoundTrip:
    @pytest.mark.parametrize("v", [
        None, True, False, 0, 42, -1, 3.14,
        "hello", "T", "F", "~", "hello world", "1e3",
    ])
    def test_round_trip(self, v):
        assert parse(serialize(v)) == v


# ─── Objects ──────────────────────────────────────────────────────────────────

class TestObjects:
    def test_empty(self):           assert parse("{}") == {}
    def test_single(self):          assert parse("{a:1}") == {"a": 1}
    def test_two_entries(self):     assert parse("{name:Alice age:30}") == {"name": "Alice", "age": 30}
    def test_nested(self):          assert parse("{a:{b:1}}") == {"a": {"b": 1}}
    def test_block(self):
        assert parse("{\n  name: Alice\n  age: 30\n}") == {"name": "Alice", "age": 30}
    def test_mixed_primitives(self):
        assert parse("{a:~ b:T c:F d:42 e:hello}") == {
            "a": None, "b": True, "c": False, "d": 42, "e": "hello"}
    def test_quoted_key(self):      assert parse('{"my key":1}') == {"my key": 1}
    def test_duplicate_key_raises(self):
        with pytest.raises(TerseError) as ei:
            parse("{a:1 a:2}")
        assert ei.value.code == "DUPLICATE_KEY"


class TestDocumentAPI:
    def test_top_level_primitives(self):
        assert parse_document("total: 5\npage: 1\nactive: T\n") == {
            "total": 5, "page": 1, "active": True}
    def test_inline_nested(self):
        assert parse_document('author: {name:Alice email:"alice@co.com"}\n') == {
            "author": {"name": "Alice", "email": "alice@co.com"}}
    def test_doc_round_trip(self):
        obj = {"name": "my-app", "private": True, "port": 3000}
        assert parse_document(serialize_document(obj)) == obj
    def test_doc_duplicate_raises(self):
        with pytest.raises(TerseError):
            parse_document("a: 1\na: 2\n")


# ─── Arrays ───────────────────────────────────────────────────────────────────

class TestArrays:
    def test_empty(self):           assert parse("[]") == []
    def test_ints(self):            assert parse("[1 2 3]") == [1, 2, 3]
    def test_bools_null(self):      assert parse("[T F ~]") == [True, False, None]
    def test_strings(self):         assert parse("[hello world]") == ["hello", "world"]
    def test_mixed(self):           assert parse("[1 hello T ~]") == [1, "hello", True, None]
    def test_nested(self):          assert parse("[[1 2] [3 4]]") == [[1, 2], [3, 4]]
    def test_block(self):
        assert parse("[\n  1\n  hello\n  T\n  ~\n]") == [1, "hello", True, None]
    def test_serialize_empty(self): assert serialize([]) == "[]"
    def test_serialize_inline(self):assert serialize([1, 2, 3]) == "[1 2 3 ]"

    @pytest.mark.parametrize("arr", [
        [], [1, 2, 3], [True, False, None], ["hello", "world"],
        [1, "hello", True, None], [[1, 2], [3, 4]],
    ])
    def test_round_trip(self, arr):
        assert parse(serialize(arr)) == arr


# ─── Schema Arrays ────────────────────────────────────────────────────────────

B2_SRC = """\
total: 5
page: 1
data:
  #[id name email role active score]
  1 "Ana Lima" ana@co.com admin T 98.5
  2 "Bruno Melo" bruno@co.com editor T 87.2
  3 "Carla Neves" carla@co.com viewer F 72.0
"""

B2_OBJ = {
    "total": 5, "page": 1,
    "data": [
        {"id": 1, "name": "Ana Lima",    "email": "ana@co.com",    "role": "admin",  "active": True,  "score": 98.5},
        {"id": 2, "name": "Bruno Melo",  "email": "bruno@co.com",  "role": "editor", "active": True,  "score": 87.2},
        {"id": 3, "name": "Carla Neves", "email": "carla@co.com",  "role": "viewer", "active": False, "score": 72.0},
    ],
}


class TestSchemaArrays:
    def test_simple(self):
        assert parse("#[name age]\n  Alice 30\n  Bob 25") == [
            {"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]

    def test_null_in_row(self):
        assert parse("#[id role]\n  1 ~\n  2 admin") == [
            {"id": 1, "role": None}, {"id": 2, "role": "admin"}]

    def test_booleans(self):
        assert parse("#[name active]\n  Alice T\n  Bob F") == [
            {"name": "Alice", "active": True}, {"name": "Bob", "active": False}]

    def test_quoted_values(self):
        assert parse('#[id name]\n  1 "Ana Lima"\n  2 "Bruno Melo"') == [
            {"id": 1, "name": "Ana Lima"}, {"id": 2, "name": "Bruno Melo"}]

    def test_b2_document(self):
        assert parse_document(B2_SRC) == B2_OBJ

    def test_empty_rows(self):
        assert parse("#[name age]") == []

    def test_serialize_uses_schema_for_2plus(self):
        arr = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
        s = serialize(arr)
        assert "#[a b ]" in s
        assert parse(s) == arr

    def test_serialize_nulls_in_schema(self):
        arr = [{"id": 1, "role": None}, {"id": 2, "role": "admin"}]
        s = serialize(arr)
        assert "~" in s
        assert parse(s) == arr

    def test_no_schema_for_single_object(self):
        arr = [{"a": 1}]
        s = serialize(arr)
        assert "#[" not in s

    def test_no_schema_for_different_keys(self):
        arr = [{"a": 1}, {"b": 2}]
        s = serialize(arr)
        assert "#[" not in s

    def test_b2_round_trip(self):
        assert parse_document(serialize_document(B2_OBJ)) == B2_OBJ

    def test_schema_round_trip(self):
        arr = [
            {"name": "Alice", "score": 98.5, "active": True},
            {"name": "Bob",   "score": 87.2, "active": True},
            {"name": "Carol", "score": None, "active": False},
        ]
        assert parse(serialize(arr)) == arr


# ─── Edge cases ───────────────────────────────────────────────────────────────

B3_SRC = """\
orderId: ORD-88421
status: confirmed
customer: {id:1042 name:"Rafael Torres" email:"r@email.com"}
shipping:
  {
  address: "Rua das Flores, 123"
  city: "São Paulo"
  method: express
  estimatedDays: 2
  }
items:
  #[sku name qty unitPrice]
  PRD-001 "Notebook Pro 15" 1 4599.90
  PRD-002 "Mouse Wireless" 2 149.90
payment:
  {
  method: credit_card
  installments: 12
  total: 4924.70
  }
"""

B4_SRC = """\
flag: T
label: "T"
value: ~
literal: "~"
emptyObj: {}
emptyArr: []
"""


class TestEdgeCases:
    def test_b3_parse(self):
        r = parse_document(B3_SRC)
        assert r["orderId"] == "ORD-88421"
        assert r["customer"]["name"] == "Rafael Torres"  # type: ignore[index]
        assert r["shipping"]["city"] == "São Paulo"       # type: ignore[index]
        items = r["items"]
        assert len(items) == 2                             # type: ignore[arg-type]
        assert items[0]["sku"] == "PRD-001"               # type: ignore[index]
        assert r["payment"]["installments"] == 12          # type: ignore[index]

    def test_b4_parse(self):
        r = parse_document(B4_SRC)
        assert r["flag"] is True
        assert r["label"] == "T"
        assert r["value"] is None
        assert r["literal"] == "~"
        assert r["emptyObj"] == {}
        assert r["emptyArr"] == []

    def test_tabs_rejected(self):
        with pytest.raises(TerseError) as ei:
            parse("\ta:1")
        assert ei.value.code == "ILLEGAL_CHARACTER"

    def test_tab_inside_value_rejected(self):
        with pytest.raises(TerseError):
            parse("{a:\t1}")

    def test_1e3_is_number(self):
        assert parse("1e3") == 1000
        assert isinstance(parse("1e3"), (int, float))

    def test_1e3_quoted_is_string(self):
        assert parse('"1e3"') == "1e3"

    def test_64_nesting_ok(self):
        obj: dict = {"x": 1}
        for _ in range(62):
            obj = {"n": obj}
        assert parse(serialize(obj)) == obj

    def test_65_nesting_raises(self):
        obj: dict = {"x": 1}
        for _ in range(65):
            obj = {"n": obj}
        with pytest.raises(TerseError):
            serialize(obj)

    def test_duplicate_key_inline(self):
        with pytest.raises(TerseError) as ei:
            parse("{a:1 a:2}")
        assert ei.value.code == "DUPLICATE_KEY"

    def test_duplicate_key_document(self):
        with pytest.raises(TerseError):
            parse_document("a: 1\na: 2\n")

    def test_comment_ignored(self):
        assert parse_document("// comment\nname: Alice\n") == {"name": "Alice"}

    def test_crlf(self):
        assert parse("{\r\n  a: 1\r\n}") == {"a": 1}

    def test_safe_id_dot_start(self):     assert parse(".hidden") == ".hidden"
    def test_safe_id_slash_start(self):   assert parse("/usr/local") == "/usr/local"
    def test_safe_id_at(self):            assert parse("alice@co.com") == "alice@co.com"
    def test_safe_id_hyphen(self):        assert parse("my-value") == "my-value"

    def test_key_T_quoted_in_output(self):
        obj = {"T": "value"}
        s = serialize(obj)
        assert '"T"' in s
        assert parse(s) == obj

    def test_b1_round_trip(self):
        b1 = {
            "name": "my-app", "version": "2.1.0", "private": True,
            "author": {"name": "Alice", "email": "alice@co.com"},
            "scripts": {"dev": "vite", "build": "vite build", "test": "vitest"},
            "dependencies": {"react": "^18.2.0", "zustand": "^4.4.1"},
            "config": {"port": 3000, "debug": False, "logLevel": "warn",
                       "tags": ["web", "typescript", "spa"]},
        }
        assert parse(serialize(b1)) == b1
        assert parse_document(serialize_document(b1)) == b1
