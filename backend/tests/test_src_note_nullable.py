"""
SRC-assign request schemas must tolerate a null `src_note`.

The frontend sends `src_note: <note>?.trim() || null`, i.e. **null** for an empty note (which
operators usually leave blank). When the schema typed it as a bare `str`, Pydantic rejected null
with a 422 whose `detail` is an ARRAY of error objects; the frontend then did
`toast.error(e.response.data.detail)`, handing react-hot-toast an object → React #31 ("Objects are
not valid as a React child") → and because <Toaster> lives OUTSIDE the route ErrorBoundary, the
whole SPA unmounted → blank page (SBI Kiosk → All Entries → Assign SRC).

These pin that every product's single- and bulk-assign SRC schema accepts a null/omitted note (the
endpoint coalesces None → ""). The systemic frontend half is in utils/api.js: the axios error
interceptor flattens any non-string `detail` to a string, so a 422 can never blank the app again.
"""
import pytest
from routes.sbi_kiosk import SBISRCIn
from routes.evalue import EvalueSRCIn, EvalueBulkSRCIn
from routes.bbps import BbpsSRCIn, BbpsBulkSRCIn


@pytest.mark.parametrize("note", [None, "", "  ", "a real note"])
def test_sbi_src_schema_tolerates_note(note):
    m = SBISRCIn(process="p02", result_id="x", src_code="UNCLAIMED", src_note=note)
    assert m.src_code == "UNCLAIMED"          # no ValidationError, whatever the note


def test_sbi_src_note_omitted_defaults_blank():
    assert SBISRCIn(process="p02", result_id="x", src_code="UNCLAIMED").src_note == ""


@pytest.mark.parametrize("note", [None, ""])
def test_evalue_src_schemas_accept_null_note(note):
    assert EvalueSRCIn(id="x", side="bank", src_code="UNCLAIMED", src_note=note).src_code == "UNCLAIMED"
    assert EvalueBulkSRCIn(ids=["x"], side="bank", src_code="UNCLAIMED", src_note=note).src_code == "UNCLAIMED"


@pytest.mark.parametrize("note", [None, ""])
def test_bbps_src_schemas_accept_null_note(note):
    assert BbpsSRCIn(id="x", side="internal", src_code="UNCLAIMED", src_note=note).src_code == "UNCLAIMED"
    assert BbpsBulkSRCIn(ids=["x"], side="internal", src_code="UNCLAIMED", src_note=note).src_code == "UNCLAIMED"
