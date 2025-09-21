import ctypes
from enum import Enum, IntEnum
import uuid
from comtypes import GUID
import datetime
import ctypes.wintypes as wt


class PROPERTYKEY(ctypes.Structure):

    _fields_ = [
        ("fmtid", GUID),
        ("pid", ctypes.c_ulong)
    ]

    def __hash__(self):
        return hash(f"{self.fmtid},{self.pid}")

    def __repr__(self):
        fmtid = self.fmtid
        pid = self.pid
        return f"{self.__class__.__name__}({fmtid=}, {pid=})"


class BLOB(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("pBlobData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


class CAUL(ctypes.Structure):
    _fields_ = [("cElems", ctypes.c_ulong), ("pElems", ctypes.POINTER(ctypes.c_ulong))]


class CAUI1(ctypes.Structure):
    _fields_ = [("cElems", ctypes.c_ulong), ("pElems", ctypes.POINTER(ctypes.c_ubyte))]


class CALPWSTR(ctypes.Structure):
    _fields_ = [("cElems", ctypes.c_ulong), ("pElems", ctypes.POINTER(ctypes.c_wchar_p))]


# PROPVARIANT
class PROPVARIANT_UNION(ctypes.Union):
    _fields_ = [
        ("cVal", ctypes.c_char),
        ("bVal", ctypes.c_ubyte),
        ("iVal", ctypes.c_short),
        ("uiVal", ctypes.c_ushort),
        ("lVal", ctypes.c_long),
        ("ulVal", ctypes.c_ulong),
        ("hVal", ctypes.c_longlong),
        ("uhVal", ctypes.c_uint64),
        ("fltVal", ctypes.c_float),
        ("dblVal", ctypes.c_double),
        ("boolVal", ctypes.c_short),          # VARIANT_BOOL (0 / -1)
        ("bstrVal", ctypes.c_wchar_p),        # VT_BSTR
        ("pszVal", ctypes.c_char_p),          # VT_LPSTR
        ("pwszVal", ctypes.c_wchar_p),        # VT_LPWSTR
        ("pclsidVal", ctypes.POINTER(GUID)),         # VT_CLSID
        ("filetime", wt.FILETIME),            # VT_FILETIME
        ("blob", BLOB),                       # <-- needed for VT_BLOB
        ("caul", CAUL),                       # VT_VECTOR|VT_UI4
        ("caui1", CAUI1),                     # VT_VECTOR|VT_UI1
        ("calpwstr", CALPWSTR),               # VT_VECTOR|VT_LPWSTR
    ]

# Full union is huge; we only implement what we need for LPWSTR (VT_LPWSTR = 31)
# class PROPVARIANT_UNION(ctypes.Union):
#     _fields_ = [
#         ("pwszVal", ctypes.c_wchar_p),
#         ("pszVal", ctypes.c_char_p),
#         ("ulVal", ctypes.c_ulong),
#         ("boolVal", ctypes.c_short),  # etc... (not exhaustive)
#     ]


# --- VARTYPEs you’ll likely see from IPropertyStore.GetValue ---

VARTYPE = ctypes.c_ushort


class VARTYPE(IntEnum):
    VT_EMPTY            = 0       # nothing
    VT_NULL             = 1
    VT_I2               = 2       # short
    VT_I4               = 3       # long
    VT_R4               = 4       # float
    VT_R8               = 5       # double
    VT_CY               = 6       # currency
    VT_DATE             = 7
    VT_BSTR             = 8       # OLE Automation string
    VT_DISPATCH         = 9
    VT_ERROR            = 10
    VT_BOOL             = 11      # VARIANT_BOOL (0 = False, -1 = True)
    VT_VARIANT          = 12      # VARIANT*
    VT_UNKNOWN          = 13      # IUnknown*
    VT_DECIMAL          = 14
    VT_I1               = 16      # char
    VT_UI1              = 17      # byte
    VT_UI2              = 18      # unsigned short
    VT_UI4              = 19      # unsigned long (DWORD)
    VT_I8               = 20      # long long
    VT_UI8              = 21      # unsigned long long
    VT_INT              = 22
    VT_UINT             = 23
    VT_VOID             = 24
    VT_HRESULT          = 25
    VT_PTR              = 26
    VT_SAFEARRAY        = 27
    VT_CARRAY           = 28
    VT_USERDEFINED      = 29
    VT_LPSTR            = 30      # ANSI string
    VT_LPWSTR           = 31      # wide string (very common for friendly name, device id)
    VT_RECORD           = 36
    VT_INT_PTR          = 37
    VT_UINT_PTR         = 38
    VT_FILETIME         = 64
    VT_BLOB             = 65
    VT_STREAM           = 66
    VT_STORAGE          = 67
    VT_STREAMED_OBJECT  = 68
    VT_STORED_OBJECT    = 69
    VT_BLOB_OBJECT      = 70
    VT_CF               = 71
    VT_CLSID            = 72      # GUID
    VT_VERSIONED_STREAM = 73

    VT_BSTR_BLOB        = 0x0FFF  # undocumented, internal
    VT_VECTOR           = 0x1000  # vector flag (combine with base type, e.g., VT_VECTOR|VT_LPWSTR)
    VT_ARRAY            = 0x2000
    VT_BYREF            = 0x4000
    VT_RESERVED         = 0x8000
    VT_ILLEGAL          = 0xFFFF
    VT_ILLEGALMASKED    = 0x0FFF
    VT_TYPEMASK         = 0x0FFF


class PROPVARIANT(ctypes.Structure):

    _fields_ = [
        ("vt", ctypes.c_ushort),
        ("wReserved1", ctypes.c_ubyte),
        ("wReserved2", ctypes.c_ubyte),
        ("wReserved3", ctypes.c_ubyte),
        ("_union", PROPVARIANT_UNION),
    ]

    def to_python(self):
        """
        Convert this PROPVARIANT into a Python value.
        Also clears it via PropVariantClear to free any allocated memory.
        """
        vt = self.vt
        try:
            # Empty / null
            if vt in (VARTYPE.VT_EMPTY, VARTYPE.VT_NULL):
                return None
            # Scalars
            if vt == VARTYPE.VT_BOOL:
                return bool(self._union.boolVal)
            if vt in (VARTYPE.VT_I1, VARTYPE.VT_UI1):
                return int(self._union.bVal)
            if vt in (VARTYPE.VT_I2,):
                return int(self._union.iVal)
            if vt in (VARTYPE.VT_UI2,):
                return int(self._union.uiVal)
            if vt in (VARTYPE.VT_I4,):
                return int(self._union.lVal)
            if vt in (VARTYPE.VT_UI4,):
                return int(self._union.ulVal)
            if vt in (VARTYPE.VT_I8,):
                return int(self._union.hVal)
            if vt in (VARTYPE.VT_UI8,):
                return int(self._union.uhVal)
            if vt == VARTYPE.VT_R4:
                return float(self._union.fltVal)
            if vt == VARTYPE.VT_R8:
                return float(self._union.dblVal)
            # Strings
            if vt == VARTYPE.VT_BSTR:
                p = self._union.bstrVal
                return None if not p else ctypes.wstring_at(p)
            if vt == VARTYPE.VT_LPSTR:
                p = self._union.pszVal
                return None if not p else ctypes.string_at(p).decode("mbcs", errors="replace")
            if vt == VARTYPE.VT_LPWSTR:
                p = self._union.pwszVal
                return None if not p else ctypes.wstring_at(p)
            # GUID
            if vt == VARTYPE.VT_CLSID:
                puuid = self._union.pclsidVal
                if not puuid:
                    return None
                g = puuid.contents
                # comtypes.GUID -> str -> uuid.UUID
                return uuid.UUID(str(g))
            # FILETIME -> datetime (UTC)
            if vt == VARTYPE.VT_FILETIME:
                ft = self._union.filetime
                # 100-ns intervals since Jan 1, 1601 (UTC)
                high = ft.dwHighDateTime << 32
                ticks = high | ft.dwLowDateTime
                if ticks == 0:
                    return None
                # Convert to seconds
                seconds, remainder = divmod(ticks - 116444736000000000, 10_000_000)
                micros = (remainder // 10)
                return datetime.datetime.utcfromtimestamp(seconds).replace(microsecond=micros)
            # BLOB -> bytes
            if vt == VARTYPE.VT_BLOB:
                b = self._union.blob
                if b.cbSize == 0 or not b.pBlobData:
                    return b""
                return bytes(bytearray(b.pBlobData[i] for i in range(b.cbSize)))
            # Vectors
            if vt & VARTYPE.VT_VECTOR:
                base = vt & ~VARTYPE.VT_VECTOR
                if base == VARTYPE.VT_UI1:     # bytes
                    arr = self._union.caui1
                    return bytes(arr.pElems[:arr.cElems]) if arr.cElems and arr.pElems else b""
                if base == VARTYPE.VT_UI4:     # list[int]
                    arr = self._union.caul
                    return list(arr.pElems[:arr.cElems]) if arr.cElems and arr.pElems else []
                if base == VARTYPE.VT_LPWSTR:  # list[str]
                    arr = self._union.calpwstr
                    if not arr.cElems or not arr.pElems:
                        return []
                    out = []
                    for i in range(arr.cElems):
                        p = arr.pElems[i]
                        out.append(None if not p else ctypes.wstring_at(p))
                    return out
                # You can add more: VT_I4, VT_UI2, etc., mirroring the CA* structs
                raise NotImplementedError(f"Vector base VARTYPE {base} not implemented")
            # Fallback for types we didn't wire yet
            raise NotImplementedError(f"Unhandled VARTYPE {vt}")
        finally:
            # Always free any memory inside the PROPVARIANT
            hr = ctypes.windll.ole32.PropVariantClear(ctypes.byref(self))
            # Common practice: ignore nonzero hr here, but you can log if needed


# ole32.PropVariantClear frees memory inside a PROPVARIANT
PropVariantClear = ctypes.windll.ole32.PropVariantClear
PropVariantClear.argtypes = [ctypes.POINTER(PROPVARIANT)]
PropVariantClear.restype  = ctypes.HRESULT
