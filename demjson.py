#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
r""" A JSON data encoder and decoder.

 This Python module implements the JSON (http://json.org/) data
 encoding format; a subset of ECMAScript (aka JavaScript) for encoding
 primitive data types (numbers, strings, booleans, lists, and
 associative arrays) in a language-neutral simple text-based syntax.
 
 It can encode or decode between JSON formatted strings and native
 Python data types.  Normally you would use the encode() and decode()
 functions defined by this module, but if you want more control over
 the processing you can use the JSON class.

 This implementation tries to be as completely cormforming to all
 intricacies of the standards as possible.  It can operate in strict
 mode (which only allows JSON-compliant syntax) or a non-strict mode
 (which allows much more of the whole ECMAScript permitted syntax).
 This includes complete support for Unicode strings (including
 surrogate-pairs for non-BMP characters), and all number formats
 including negative zero and IEEE 754 non-numbers such a NaN or
 Infinity.

 The JSON/ECMAScript to Python type mappings are:
    ---JSON---             ---Python---
    null                   None
    undefined              undefined  (note 1)
    Boolean (true,false)   bool  (True or False)
    Integer                int or long  (note 2)
    Float                  float
    String                 str or unicode  ( "..." or u"..." )
    Array [a, ...]         list  ( [...] )
    Object {a:b, ...}      dict  ( {...} )
    
    -- Note 1. an 'undefined' object is declared in this module which
       represents the native Python value for this type when in
       non-strict mode.

    -- Note 2. some ECMAScript integers may be up-converted to Python
       floats, such as 1e+40.  Also integer -0 is converted to
       float -0, so as to preserve the sign (which ECMAScript requires).

    -- Note 3. numbers requiring more significant digits than can be
       represented by the Python float type will be converted into a
       Python Decimal type, from the standard 'decimal' module.

 In addition, when operating in non-strict mode, several IEEE 754
 non-numbers are also handled, and are mapped to specific Python
 objects declared in this module:

     NaN (not a number)     nan    (float('nan'))
     Infinity, +Infinity    inf    (float('inf'))
     -Infinity              neginf (float('-inf'))

 When encoding Python objects into JSON, you may use types other than
 native lists or dictionaries, as long as they support the minimal
 interfaces required of all sequences or mappings.  This means you can
 use generators and iterators, tuples, UserDict subclasses, etc.

 To make it easier to produce JSON encoded representations of user
 defined classes, if the object has a method named json_equivalent(),
 then it will call that method and attempt to encode the object
 returned from it instead.  It will do this recursively as needed and
 before any attempt to encode the object using it's default
 strategies.  Note that any json_equivalent() method should return
 "equivalent" Python objects to be encoded, not an already-encoded
 JSON-formatted string.  There is no such aid provided to decode
 JSON back into user-defined classes as that would dramatically
 complicate the interface.
 
 When decoding strings with this module it may operate in either
 strict or non-strict mode.  The strict mode only allows syntax which
 is conforming to RFC 7158 (JSON), while the non-strict allows much
 more of the permissible ECMAScript syntax.

 The following are permitted when processing in NON-STRICT mode:

    * Unicode format control characters are allowed anywhere in the input.
    * All Unicode line terminator characters are recognized.
    * All Unicode white space characters are recognized.
    * The 'undefined' keyword is recognized.
    * Hexadecimal number literals are recognized (e.g., 0xA6, 0177).
    * String literals may use either single or double quote marks.
    * Strings may contain \x (hexadecimal) escape sequences, as well as the
      \v and \0 escape sequences.
    * Lists may have omitted (elided) elements, e.g., [,,,,,], with
      missing elements interpreted as 'undefined' values.
    * Object properties (dictionary keys) can be of any of the
      types: string literals, numbers, or identifiers (the later of
      which are treated as if they are string literals)---as permitted
      by ECMAScript.  JSON only permits strings literals as keys.

 Concerning non-strict and non-ECMAScript allowances:

    * Octal numbers: If you allow the 'octal_numbers' behavior (which
      is never enabled by default), then you can use octal integers
      and octal character escape sequences (per the ECMAScript
      standard Annex B.1.2).  This behavior is allowed, if enabled,
      because it was valid JavaScript at one time.

    * Multi-line string literals:  Strings which are more than one
      line long (contain embedded raw newline characters) are never
      permitted. This is neither valid JSON nor ECMAScript.  Some other
      JSON implementations may allow this, but this module considers
      that behavior to be a mistake.

 References:
    * JSON (JavaScript Object Notation)
      <http://json.org/>
    * RFC 7158. The application/json Media Type for JavaScript Object Notation (JSON)
      <http://www.ietf.org/rfc/rfc7158.txt>
    * ECMA-262 3rd edition (1999)
      <http://www.ecma-international.org/publications/files/ecma-st/ECMA-262.pdf>
    * IEEE 754-1985: Standard for Binary Floating-Point Arithmetic.
      <http://www.cs.berkeley.edu/~ejr/Projects/ieee754/>
    
"""

__author__ = "Deron Meranda <http://deron.meranda.us/>"
__date__ = "2014-04-13"
__version__ = "1.7"
__homepage__ = "http://deron.meranda.us/python/demjson/"
__credits__ = """Copyright (c) 2006-2014 Deron E. Meranda <http://deron.meranda.us/>

Licensed under GNU LGPL (GNU Lesser General Public License) version 3.0
or later.  See LICENSE.txt included with this software.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>
or <http://www.fsf.org/licensing/>.

"""

# ------------------------------
# useful global constants

content_type = 'application/json'
file_ext = 'json'

# ----------------------------------------------------------------------
# Decimal and float types.
#
# If a JSON number can not be stored in a Python float without loosing
# precision and the Python has the decimal type, then we will try to
# use decimal instead of float.  To make this determination we need to
# know the limits of the float type, but Python doesn't have an easy
# way to tell what the largest floating-point number it supports.  So,
# we detemine the precision and scale of the float type by testing it.

try:
    # decimal module was introduced in Python 2.4
    import decimal
except ImportError:
    decimal = None

def determine_float_precision():
    """Returns a tuple (significant_digits, max_exponent) for the float type.
    """
    import math
    # Just count the digits in pi.  The last two decimal digits
    # may only be partial digits, so discount for them.
    whole, frac = repr(math.pi).split('.')
    sigdigits = len(whole) + len(frac) - 2

    # This is a simple binary search.  We find the largest exponent
    # that the float() type can handle without going infinite or
    # raising errors.
    maxexp = None
    minv = 0; maxv = 1000
    while True:
        if minv+1 == maxv:
            maxexp = minv - 1
            break
        elif maxv < minv:
            maxexp = None
            break
        m = (minv + maxv) // 2
        try:
            f = repr(float( '1e+%d' % m ))
        except ValueError:
            f = None
        else:
            if not f or f[0] < '0' or f[0] > '9':
                f = None
        if not f:
            # infinite
            maxv = m
        else:
            minv = m
    return sigdigits, maxexp

float_sigdigits, float_maxexp = determine_float_precision()

# ----------------------------------------------------------------------
# The undefined value.
#
# ECMAScript has an undefined value (similar to yet distinct from null).
# Neither Python or strict JSON have support undefined, but to allow
# JavaScript behavior we must simulate it.

class _undefined_class(object):
    """Represents the ECMAScript 'undefined' value."""
    __slots__ = []
    def __repr__(self):
        return self.__module__ + '.undefined'
    def __str__(self):
        return 'undefined'
    def __nonzero__(self):
        return False
undefined = _undefined_class()
del _undefined_class


# ----------------------------------------------------------------------
# Non-Numbers: NaN, Infinity, -Infinity
#
# ECMAScript has official support for non-number floats, although
# strict JSON does not.  Python doesn't either.  So to support the
# full JavaScript behavior we must try to add them into Python, which
# is unfortunately a bit of black magic.  If our python implementation
# happens to be built on top of IEEE 754 we can probably trick python
# into using real floats.  Otherwise we must simulate it with classes.

def _nonnumber_float_constants():
    """Try to return the Nan, Infinity, and -Infinity float values.
    
    This is unnecessarily complex because there is no standard
    platform- independent way to do this in Python as the language
    (opposed to some implementation of it) doesn't discuss
    non-numbers.  We try various strategies from the best to the
    worst.
    
    If this Python interpreter uses the IEEE 754 floating point
    standard then the returned values will probably be real instances
    of the 'float' type.  Otherwise a custom class object is returned
    which will attempt to simulate the correct behavior as much as
    possible.

    """
    try:
        # First, try (mostly portable) float constructor.  Works under
        # Linux x86 (gcc) and some Unices.
        nan = float('nan')
        inf = float('inf')
        neginf = float('-inf')
    except ValueError:
        try:
            # Try the AIX (PowerPC) float constructors
            nan = float('NaNQ')
            inf = float('INF')
            neginf = float('-INF')
        except ValueError:
            try:
                # Next, try binary unpacking.  Should work under
                # platforms using IEEE 754 floating point.
                import struct, sys
                xnan = '7ff8000000000000'.decode('hex')  # Quiet NaN
                xinf = '7ff0000000000000'.decode('hex')
                xcheck = 'bdc145651592979d'.decode('hex') # -3.14159e-11
                # Could use float.__getformat__, but it is a new python feature,
                # so we use sys.byteorder.
                if sys.byteorder == 'big':
                    nan = struct.unpack('d', xnan)[0]
                    inf = struct.unpack('d', xinf)[0]
                    check = struct.unpack('d', xcheck)[0]
                else:
                    nan = struct.unpack('d', xnan[::-1])[0]
                    inf = struct.unpack('d', xinf[::-1])[0]
                    check = struct.unpack('d', xcheck[::-1])[0]
                neginf = - inf
                if check != -3.14159e-11:
                    raise ValueError('Unpacking raw IEEE 754 floats does not work')
            except (ValueError, TypeError):
                # Punt, make some fake classes to simulate.  These are
                # not perfect though.  For instance nan * 1.0 == nan,
                # as expected, but 1.0 * nan == 0.0, which is wrong.
                class nan(float):
                    """An approximation of the NaN (not a number) floating point number."""
                    def __repr__(self): return 'nan'
                    def __str__(self): return 'nan'
                    def __add__(self,x): return self
                    def __radd__(self,x): return self
                    def __sub__(self,x): return self
                    def __rsub__(self,x): return self
                    def __mul__(self,x): return self
                    def __rmul__(self,x): return self
                    def __div__(self,x): return self
                    def __rdiv__(self,x): return self
                    def __divmod__(self,x): return (self,self)
                    def __rdivmod__(self,x): return (self,self)
                    def __mod__(self,x): return self
                    def __rmod__(self,x): return self
                    def __pow__(self,exp): return self
                    def __rpow__(self,exp): return self
                    def __neg__(self): return self
                    def __pos__(self): return self
                    def __abs__(self): return self
                    def __lt__(self,x): return False
                    def __le__(self,x): return False
                    def __eq__(self,x): return False
                    def __neq__(self,x): return True
                    def __ge__(self,x): return False
                    def __gt__(self,x): return False
                    def __complex__(self,*a): raise NotImplementedError('NaN can not be converted to a complex')
                if decimal:
                    nan = decimal.Decimal('NaN')
                else:
                    nan = nan()
                class inf(float):
                    """An approximation of the +Infinity floating point number."""
                    def __repr__(self): return 'inf'
                    def __str__(self): return 'inf'
                    def __add__(self,x): return self
                    def __radd__(self,x): return self
                    def __sub__(self,x): return self
                    def __rsub__(self,x): return self
                    def __mul__(self,x):
                        if x is neginf or x < 0:
                            return neginf
                        elif x == 0:
                            return nan
                        else:
                            return self
                    def __rmul__(self,x): return self.__mul__(x)
                    def __div__(self,x):
                        if x == 0:
                            raise ZeroDivisionError('float division')
                        elif x < 0:
                            return neginf
                        else:
                            return self
                    def __rdiv__(self,x):
                        if x is inf or x is neginf or x is nan:
                            return nan
                        return 0.0
                    def __divmod__(self,x):
                        if x == 0:
                            raise ZeroDivisionError('float divmod()')
                        elif x < 0:
                            return (nan,nan)
                        else:
                            return (self,self)
                    def __rdivmod__(self,x):
                        if x is inf or x is neginf or x is nan:
                            return (nan, nan)
                        return (0.0, x)
                    def __mod__(self,x):
                        if x == 0:
                            raise ZeroDivisionError('float modulo')
                        else:
                            return nan
                    def __rmod__(self,x):
                        if x is inf or x is neginf or x is nan:
                            return nan
                        return x
                    def __pow__(self, exp):
                        if exp == 0:
                            return 1.0
                        else:
                            return self
                    def __rpow__(self, x):
                        if -1 < x < 1: return 0.0
                        elif x == 1.0: return 1.0
                        elif x is nan or x is neginf or x < 0:
                            return nan
                        else:
                            return self
                    def __neg__(self): return neginf
                    def __pos__(self): return self
                    def __abs__(self): return self
                    def __lt__(self,x): return False
                    def __le__(self,x):
                        if x is self:
                            return True
                        else:
                            return False
                    def __eq__(self,x):
                        if x is self:
                            return True
                        else:
                            return False
                    def __neq__(self,x):
                        if x is self:
                            return False
                        else:
                            return True
                    def __ge__(self,x): return True
                    def __gt__(self,x): return True
                    def __complex__(self,*a): raise NotImplementedError('Infinity can not be converted to a complex')
                if decimal:
                    inf = decimal.Decimal('Infinity')
                else:
                    inf = inf()
                class neginf(float):
                    """An approximation of the -Infinity floating point number."""
                    def __repr__(self): return '-inf'
                    def __str__(self): return '-inf'
                    def __add__(self,x): return self
                    def __radd__(self,x): return self
                    def __sub__(self,x): return self
                    def __rsub__(self,x): return self
                    def __mul__(self,x):
                        if x is self or x < 0:
                            return inf
                        elif x == 0:
                            return nan
                        else:
                            return self
                    def __rmul__(self,x): return self.__mul__(self)
                    def __div__(self,x):
                        if x == 0:
                            raise ZeroDivisionError('float division')
                        elif x < 0:
                            return inf
                        else:
                            return self
                    def __rdiv__(self,x):
                        if x is inf or x is neginf or x is nan:
                            return nan
                        return -0.0
                    def __divmod__(self,x):
                        if x == 0:
                            raise ZeroDivisionError('float divmod()')
                        elif x < 0:
                            return (nan,nan)
                        else:
                            return (self,self)
                    def __rdivmod__(self,x):
                        if x is inf or x is neginf or x is nan:
                            return (nan, nan)
                        return (-0.0, x)
                    def __mod__(self,x):
                        if x == 0:
                            raise ZeroDivisionError('float modulo')
                        else:
                            return nan
                    def __rmod__(self,x):
                        if x is inf or x is neginf or x is nan:
                            return nan
                        return x
                    def __pow__(self,exp):
                        if exp == 0:
                            return 1.0
                        else:
                            return self
                    def __rpow__(self, x):
                        if x is nan or x is inf or x is inf:
                            return nan
                        return 0.0
                    def __neg__(self): return inf
                    def __pos__(self): return self
                    def __abs__(self): return inf
                    def __lt__(self,x): return True
                    def __le__(self,x): return True
                    def __eq__(self,x):
                        if x is self:
                            return True
                        else:
                            return False
                    def __neq__(self,x):
                        if x is self:
                            return False
                        else:
                            return True
                    def __ge__(self,x):
                        if x is self:
                            return True
                        else:
                            return False
                    def __gt__(self,x): return False
                    def __complex__(self,*a): raise NotImplementedError('-Infinity can not be converted to a complex')
                if decimal:
                    neginf = decimal.Decimal('-Infinity')
                else:
                    neginf = neginf(0)
    return nan, inf, neginf

nan, inf, neginf = _nonnumber_float_constants()
del _nonnumber_float_constants


# ----------------------------------------------------------------------
# String processing helpers

def skipstringsafe( s, start=0, end=None ):
    i = start
    #if end is None:
    #    end = len(s)
    unsafe = helpers.unsafe_string_chars
    while i < end and s[i] not in unsafe:
        #c = s[i]
        #if c in unsafe_string_chars:
        #    break
        i += 1
    return i

def skipstringsafe_slow( s, start=0, end=None ):
    i = start
    if end is None:
        end = len(s)
    while i < end:
        c = s[i]
        if c == '"' or c == '\\' or ord(c) <= 0x1f:
            break
        i += 1
    return i

def extend_list_with_sep( orig_seq, extension_seq, sepchar='' ):
    if not sepchar:
        orig_seq.extend( extension_seq )
    else:
        for i, x in enumerate(extension_seq):
            if i > 0:
                orig_seq.append( sepchar )
            orig_seq.append( x )

def extend_and_flatten_list_with_sep( orig_seq, extension_seq, separator='' ):
    for i, part in enumerate(extension_seq):
        if i > 0 and separator:
            orig_seq.append( separator )
        orig_seq.extend( part )



# ----------------------------------------------------------------------
# Unicode UTF-32
# ----------------------------------------------------------------------

def _make_raw_bytes( byte_list ):
    """Takes a list of byte values (numbers) and returns a bytes (Python 3) or string (Python 2)
    """
    import sys
    if sys.version_info.major >= 3:
        b = bytes( byte_list )
    else:
        b = ''.join(chr(n) for n in byte_list)
    return b

import codecs

class utf32(codecs.CodecInfo):
    """Unicode UTF-32 and UCS4 encoding/decoding support.

    This is for older Pythons whch did not have UTF-32 codecs.

    JSON requires that all JSON implementations must support the
    UTF-32 encoding (as well as UTF-8 and UTF-16).  But earlier
    versions of Python did not provide a UTF-32 codec, so we must
    implement UTF-32 ourselves in case we need it.

    See http://en.wikipedia.org/wiki/UTF-32

    """
    BOM_UTF32_BE = _make_raw_bytes([ 0, 0, 0xFE, 0xFF ])  #'\x00\x00\xfe\xff'
    BOM_UTF32_LE = _make_raw_bytes([ 0xFF, 0xFE, 0, 0 ])  #'\xff\xfe\x00\x00'

    @staticmethod
    def lookup( name ):
        """A standard Python codec lookup function for UCS4/UTF32.

        If if recognizes an encoding name it returns a CodecInfo
        structure which contains the various encode and decoder
        functions to use.

        """
        ci = None
        name = name.upper()
        if name in ('UCS4BE','UCS-4BE','UCS-4-BE','UTF32BE','UTF-32BE','UTF-32-BE'):
            ci = codecs.CodecInfo( utf32.utf32be_encode, utf32.utf32be_decode, name='utf-32be')
        elif name in ('UCS4LE','UCS-4LE','UCS-4-LE','UTF32LE','UTF-32LE','UTF-32-LE'):
            ci = codecs.CodecInfo( utf32.utf32le_encode, utf32.utf32le_decode, name='utf-32le')
        elif name in ('UCS4','UCS-4','UTF32','UTF-32'):
            ci = codecs.CodecInfo( utf32.encode, utf32.decode, name='utf-32')
        return ci

    @staticmethod
    def encode( obj, errors='strict', endianness=None, include_bom=True ):
        """Encodes a Unicode string into a UTF-32 encoded byte string.

        Returns a tuple: (bytearry, num_chars)

        The errors argument should be one of 'strict', 'ignore', or 'replace'.

        The endianness should be one of:
            * 'B', '>', or 'big'     -- Big endian
            * 'L', '<', or 'little'  -- Little endien
            * None                   -- Default, from sys.byteorder

        If include_bom is true a Byte-Order Mark will be written to
        the beginning of the string, otherwise it will be omitted.

        """
        import sys, struct

        # Make a container that can store bytes
        if sys.version_info.major >= 3:
            f = bytearray()
            write = f.extend
            def tobytes():
                return bytes(f)
        else:
            try:
                import cStringIO as sio
            except ImportError:
                import StringIO as sio
            f = sio.StringIO()
            write = f.write
            tobytes = f.getvalue

        if not endianness:
            endianness = sys.byteorder

        if endianness.upper()[0] in ('B>'):
            big_endian = True
        elif endianness.upper()[0] in ('L<'):
            big_endian = False
        else:
            raise ValueError("Invalid endianness %r: expected 'big', 'little', or None" % endianness)

        pack = struct.pack
        packspec = '>L' if big_endian else '<L'

        num_chars = 0

        if include_bom:
            if big_endian:
                write( utf32.BOM_UTF32_BE )
            else:
                write( utf32.BOM_UTF32_LE )
            num_chars += 1

        for pos, c in enumerate(obj):
            n = ord(c)
            if 0xD800 <= n <= 0xDFFF: # surrogate codepoints are prohibited by UTF-32
                if errors == 'ignore':
                    pass
                elif errors == 'replace':
                    n = 0xFFFD
                else:
                    raise UnicodeEncodeError('utf32',obj,pos,pos+1,"surrogate code points from U+D800 to U+DFFF are not allowed")
            write( pack( packspec, n) )
            num_chars += 1

        return (tobytes(), num_chars)
        
    @staticmethod
    def utf32le_encode( obj, errors='strict', include_bom=False ):
        """Encodes a Unicode string into a UTF-32LE (little endian) encoded byte string."""
        return utf32.encode( obj, errors=errors, endianness='L', include_bom=include_bom )

    @staticmethod
    def utf32be_encode( obj, errors='strict', include_bom=False ):
        """Encodes a Unicode string into a UTF-32BE (big endian) encoded byte string."""
        return utf32.encode( obj, errors=errors, endianness='B', include_bom=include_bom )

    @staticmethod
    def decode( obj, errors='strict', endianness=None ):
        """Decodes a UTF-32 byte string into a Unicode string.

        Returns tuple (bytearray, num_bytes)

        The errors argument shold be one of 'strict', 'ignore',
        'replace', 'backslashreplace', or 'xmlcharrefreplace'.

        The endianness should either be None (for auto-guessing), or a
        word that starts with 'B' (big) or 'L' (little).

        Will detect a Byte-Order Mark. If a BOM is found and endianness
        is also set, then the two must match.

        If neither a BOM is found nor endianness is set, then big
        endian order is assumed.

        """
        import struct, sys
        maxunicode = sys.maxunicode
        unpack = struct.unpack

        # Detect BOM
        if obj.startswith( utf32.BOM_UTF32_BE ):
            bom_endianness = 'B'
            start = len(utf32.BOM_UTF32_BE)
        elif obj.startswith( utf32.BOM_UTF32_LE ):
            bom_endianness = 'L'
            start = len(utf32.BOM_UTF32_LE)
        else:
            bom_endianness = None
            start = 0

        num_bytes = start

        if endianness == None:
            if bom_endianness == None:
                endianness = sys.byteorder.upper()[0]   # Assume platform default
            else:
                endianness = bom_endianness
        else:
            endianness = endianness[0].upper()
            if bom_endianness and endianness != bom_endianness:
                raise UnicodeDecodeError('utf32',obj,0,start,'BOM does not match expected byte order')

        # Check for truncated last character
        if ((len(obj)-start) % 4) != 0:
            raise UnicodeDecodeError('utf32',obj,start,len(obj),
                                     'Data length not a multiple of 4 bytes')

        # Start decoding characters
        chars = []
        packspec = '>L' if endianness=='B' else '<L'
        i = 0
        for i in range(start, len(obj), 4):
            seq = obj[i:i+4]
            n = unpack( packspec, seq )[0]
            num_bytes += 4

            if n > maxunicode or (0xD800 <= n <= 0xDFFF):
                if errors == 'strict':
                    raise UnicodeDecodeError('utf32',obj,i,i+4,'Invalid code point U+%04X' % n)
                elif errors == 'replace':
                    chars.append( unichr(0xFFFD) )
                elif errors == 'backslashreplace':
                    if n > 0xffff:
                        esc = "\\u%04x" % (n,)
                    else:
                        esc = "\\U%08x" % (n,)
                    for esc_c in esc:
                        chars.append( esc_c )
                elif errors == 'xmlcharrefreplace':
                    esc = "&#%d;" % (n,)
                    for esc_c in esc:
                        chars.append( esc_c )
                else: # ignore
                    pass
            else:
                chars.append( unichr(n) )
        return (u''.join( chars ), num_bytes)

    @staticmethod
    def utf32le_decode( obj, errors='strict' ):
        """Decodes a UTF-32LE (little endian) byte string into a Unicode string."""
        return utf32.decode( obj, errors=errors, endianness='L' )

    @staticmethod
    def utf32be_decode( obj, errors='strict' ):
        """Decodes a UTF-32BE (big endian) byte string into a Unicode string."""
        return utf32.decode( obj, errors=errors, endianness='B' )


# ----------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------

def _make_unsafe_string_chars():
    import unicodedata
    unsafe = []
    for c in [unichr(i) for i in range(0x100)]:
        if c == u'"' or c == u'\\' \
                or unicodedata.category( c ) in ['Cc','Cf','Zl','Zp']:
            unsafe.append( c )
    return u''.join( unsafe )

class helpers(object):
    """A set of utility functions."""

    hexdigits = '0123456789ABCDEFabcdef'
    octaldigits = '01234567'
    unsafe_string_chars = _make_unsafe_string_chars()

    always_use_custom_codecs = False   # If True use demjson's codecs
                                       # before system codecs. This
                                       # is mainly here for testing.

    @staticmethod
    def make_raw_bytes( byte_list ):
        """Constructs a byte array (bytes in Python 3, str in Python 2) from a list of byte values (0-255).

        """
        return _make_raw_bytes( byte_list )

    @staticmethod
    def is_hex_digit( c ):
        """Determines if the given character is a valid hexadecimal digit (0-9, a-f, A-F)."""
        return (c in helpers.hexdigits)

    @staticmethod
    def is_octal_digit( c ):
        """Determines if the given character is a valid octal digit (0-7)."""
        return (c in helpers.octaldigits)

    @staticmethod
    def char_is_json_ws( c ):
        """Determines if the given character is a JSON white-space character"""
        return c in ' \t\n\r'

    @staticmethod
    def char_is_unicode_ws( c ):
        """Determines if the given character is a Unicode space character"""
        if not isinstance(c,unicode):
            c = unicode(c)
        if c in u' \t\n\r\f\v':
            return True
        import unicodedata
        return unicodedata.category(c) == 'Zs'

    @staticmethod
    def char_is_json_eol( c ):
        """Determines if the given character is a JSON line separator"""
        return c in '\n\r'

    @staticmethod
    def char_is_unicode_eol( c ):
        """Determines if the given character is a Unicode line or
        paragraph separator. These correspond to CR and LF as well as
        Unicode characters in the Zl or Zp categories.

        """
        return c in u'\r\n\u2028\u2029'

    @staticmethod
    def char_is_identifier_leader( c ):
        """Determines if the character may be the first character of a
        JavaScript identifier.
        """
        return c.isalpha() or c in '_$'

    @staticmethod
    def char_is_identifier_tail( c ):
        """Determines if the character may be part of a JavaScript
        identifier.
        """
        return c.isalnum() or c in u'_$\u200c\u200d'

    @staticmethod
    def extend_and_flatten_list_with_sep( orig_seq, extension_seq, separator='' ):
        for i, part in enumerate(extension_seq):
            if i > 0 and separator:
                orig_seq.append( separator )
            orig_seq.extend( part )

    @staticmethod
    def strip_format_control_chars( txt ):
        """Filters out all Unicode format control characters from the string.

        ECMAScript permits any Unicode "format control characters" to
        appear at any place in the source code.  They are to be
        ignored as if they are not there before any other lexical
        tokenization occurs.  Note that JSON does not allow them,
        except within string literals.

        * Ref. ECMAScript section 7.1.
        * http://en.wikipedia.org/wiki/Unicode_control_characters

        There are dozens of Format Control Characters, for example:
            U+00AD   SOFT HYPHEN
            U+200B   ZERO WIDTH SPACE
            U+2060   WORD JOINER

        """
        import unicodedata
        txt2 = filter( lambda c: unicodedata.category(unicode(c)) != 'Cf', txt )

        # 2to3 NOTE: The following is needed to work around a broken
        # Python3 conversion in which filter() will be transformed
        # into a list rather than a string.
        if not isinstance(txt2,basestring):
            txt2 = u''.join(txt2)
        return txt2

    @staticmethod
    def lookup_codec( encoding ):
        """Wrapper around codecs.lookup().

        Returns None if codec not found, rather than raising a LookupError.
        """
        encoding = encoding.lower()
        import codecs
        if helpers.always_use_custom_codecs:
            # Try custom utf32 first, then standard python codecs
            cdk = utf32.lookup(encoding)
            if not cdk:
                try:
                    cdk = codecs.lookup( encoding )
                except LookupError:
                    cdk = None
        else:
            # Try standard python codecs first, then custom utf32
            try:
                cdk = codecs.lookup( encoding )
            except LookupError:
                cdk = utf32.lookup( encoding )
        return cdk

    @staticmethod
    def auto_detect_encoding( s ):
        """Takes a string (or byte array) and tries to determine the Unicode encoding it is in.

        Returns the encoding name, as a string.

        """
        if not s:
            return "utf-8"

        if len(s) == 0:
            return ''.decode('utf8')

        # Get the byte values of up to the first 4 bytes
        ords = []
        for i in range(0, min(len(s),4)):
            x = s[i]
            if isinstance(x, basestring):
                x = ord(x)
            ords.append( x )

        # Look for BOM marker
        import sys, codecs
        if len(s) >= 2:
            bom2 = s[:2]
        else:
            bom2 = None
        if len(s) >= 4:
            bom4 = s[:4]
        else:
            bom4 = None

        # Assign values of first four bytes to: a, b, c, d; and last byte to: z
        a, b, c, d, z = None, None, None, None, None
        if len(s) >= 1:
            a = ords[0]
        if len(s) >= 2:
            b = ords[1]
        if len(s) >= 3:
            c = ords[2]
        if len(s) >= 4:
            d = ords[3]

        z = s[-1]
        if isinstance(z, basestring):
            z = ord(z)

        if bom4 and ( (hasattr(codecs,'BOM_UTF32_LE') and bom4 == codecs.BOM_UTF32_LE) or
                      (bom4 == utf32.BOM_UTF32_LE) ):
            encoding = 'utf-32le'
            s = s[4:]
        elif bom4 and ( (hasattr(codecs,'BOM_UTF32_BE') and bom4 == codecs.BOM_UTF32_BE) or
                        (bom4 == utf32.BOM_UTF32_BE) ):
            encoding = 'utf-32be'
            s = s[4:]
        elif bom2 and bom2 == codecs.BOM_UTF16_LE:
            encoding = 'utf-16le'
            s = s[2:]
        elif bom2 and bom2 == codecs.BOM_UTF16_BE:
            encoding = 'utf-16be'
            s = s[2:]

        # No BOM, so autodetect encoding used by looking at first four
        # bytes according to RFC 4627 section 3.  The first and last bytes
        # in a JSON document will be ASCII.  The second byte will be ASCII
        # unless the first byte was a quotation mark.

        elif len(s)>=4 and a==0 and b==0 and c==0 and d!=0: # UTF-32BE  (0 0 0 x)
            encoding = 'utf-32be'
        elif len(s)>=4 and a!=0 and b==0 and c==0 and d==0 and z==0: # UTF-32LE  (x 0 0 0 [... 0])
            encoding = 'utf-32le'
        elif len(s)>=2 and a==0 and b!=0: # UTF-16BE  (0 x)
            encoding = 'utf-16be'
        elif len(s)>=2 and a!=0 and b==0 and z==0: # UTF-16LE  (x 0 [... 0])
            encoding = 'utf-16le'
        elif ord('\t') <= a <= 127:
            # First byte appears to be ASCII, so guess UTF-8.
            encoding = 'utf8'
        else:
            raise JSONDecodeError("Can not determine the Unicode encoding for this JSON document")

        return encoding

    @staticmethod
    def auto_unicode_decode( s ):
        """Takes a string (or byte array) and tries to convert it to a Unicode string.

        This will return a Python unicode string type corresponding to the
        input string (either str or unicode).  The character encoding is
        guessed by looking for either a Unicode BOM prefix, or by the
        rules specified by RFC 7158.  When in doubt it is assumed the
        input is encoded in UTF-8 (the default for JSON).

        The BOM (byte order mark) if present will be stripped off of the
        returned string.

        """
        if isinstance(s, unicode):
            return s  # Already Unicode

        encoding = helpers.auto_detect_encoding( s )

        # Make sure the encoding is supported by Python
        cdk = helpers.lookup_codec( encoding )
        if not cdk:
            raise JSONDecodeError('no codec available for character encoding',encoding)

        # See if codec accepts errors argument
        try:
            cdk.decode( helpers.make_raw_bytes([]), errors='strict' )
        except TypeError:
            cdk_kw = {}
        else:
            cdk_kw = {'errors': 'strict'}

        # Convert to unicode using a standard codec (can raise UnicodeDecodeError)
        unis, ulen = cdk.decode( s, **cdk_kw )
        return unis

    @staticmethod
    def surrogate_pair_as_unicode( c1, c2 ):
        """Takes a pair of unicode surrogates and returns the equivalent unicode character.

        The input pair must be a surrogate pair, with c1 in the range
        U+D800 to U+DBFF and c2 in the range U+DC00 to U+DFFF.

        """
        n1, n2 = ord(c1), ord(c2)
        if n1 < 0xD800 or n1 > 0xDBFF or n2 < 0xDC00 or n2 > 0xDFFF:
            raise JSONDecodeError('illegal Unicode surrogate pair',(c1,c2))
        a = n1 - 0xD800
        b = n2 - 0xDC00
        v = (a << 10) | b
        v += 0x10000
        return unichr(v)

    @staticmethod
    def unicode_as_surrogate_pair( c ):
        """Takes a single unicode character and returns a sequence of surrogate pairs.

        The output of this function is a tuple consisting of one or two unicode
        characters, such that if the input character is outside the BMP range
        then the output is a two-character surrogate pair representing that character.

        If the input character is inside the BMP then the output tuple will have
        just a single character...the same one.

        """
        n = ord(c)
        if n < 0x10000:
            return (unichr(n),)  # in BMP, surrogate pair not required
        v = n - 0x10000
        vh = (v >> 10) & 0x3ff   # highest 10 bits
        vl = v & 0x3ff  # lowest 10 bits
        w1 = 0xD800 | vh
        w2 = 0xDC00 | vl
        return (unichr(w1), unichr(w2))

    @staticmethod
    def isnumbertype( obj ):
        """Is the object of a Python number type (excluding complex)?"""
        return isinstance(obj, (int,long,float)) \
               and not isinstance(obj, bool) \
               or obj is nan or obj is inf or obj is neginf

    @staticmethod
    def isstringtype( obj ):
        """Is the object of a Python string type?"""
        if isinstance(obj, basestring):
            return True
        # Must also check for some other pseudo-string types
        import types, UserString
        return isinstance(obj, types.StringTypes) \
               or isinstance(obj, UserString.UserString)
               ## or isinstance(obj, UserString.MutableString)

    @staticmethod
    def decode_hex( hexstring ):
        """Decodes a hexadecimal string into it's integer value."""
        # We don't use the builtin 'hex' codec in python since it can
        # not handle odd numbers of digits, nor raise the same type
        # of exceptions we want to.
        n = 0
        for c in hexstring:
            if '0' <= c <= '9':
                d = ord(c) - ord('0')
            elif 'a' <= c <= 'f':
                d = ord(c) - ord('a') + 10
            elif 'A' <= c <= 'F':
                d = ord(c) - ord('A') + 10
            else:
                raise ValueError('Not a hexadecimal number', hexstring)
            # Could use ((n << 4 ) | d), but python 2.3 issues a FutureWarning.
            n = (n * 16) + d
        return n

    @staticmethod
    def decode_octal( octalstring ):
        """Decodes an octal string into it's integer value."""
        n = 0
        for c in octalstring:
            if '0' <= c <= '7':
                d = ord(c) - ord('0')
            else:
                raise ValueError('Not an octal number', octalstring)
            # Could use ((n << 3 ) | d), but python 2.3 issues a FutureWarning.
            n = (n * 8) + d
        return n

##!!!!




# ----------------------------------------------------------------------
# Exception classes.

class JSONSkipHook(Exception):
    """An exception to be raised by user-defined code within hook
    callbacks to indicate the callback does not want to handle the
    situation.

    """
    pass

class JSONError(ValueError):
    """Our base class for all JSON-related errors.

    """
    def pretty_description(self):
        err = self.args[0]
        if len(self.args) > 1:
            err += ': '
            for anum, a in enumerate(self.args[1:]):
                if anum > 1:
                    err += ', '
                astr = repr(a)
                if len(astr) > 20:
                    astr = astr[:20] + '...'
                err += astr
        return err

class JSONDecodeError(JSONError):
    """An exception class raised when a JSON decoding error (syntax error) occurs."""
    pass

class JSONDecodeHookError(JSONDecodeError):
    """An exception that occured within a decoder hook.
    
    The original exception is available in the 'hook_exception' attribute.
    """
    def __init__(self, hook_name, exc_info, encoded_obj, *args, **kwargs):
        self.hook_name = hook_name
        if not exc_info:
            exc_info = (None, None, None)
        exc_type, self.hook_exception, self.hook_traceback = exc_info
        self.object_type = type(encoded_obj)
        msg = "Hook %s raised %r while decoding type <%s>" % (hook_name, self.hook_exception.__class__.__name__, self.object_type.__name__)
        if len(args) >= 1:
            msg += ": " + args[0]
            args = args[1:]
        super(JSONDecodeHookError,self).__init__(msg, *args,**kwargs)

class JSONEncodeError(JSONError):
    """An exception class raised when a python object can not be encoded as a JSON string."""
    pass

class JSONEncodeHookError(JSONEncodeError):
    """An exception that occured within an encoder hook.
    
    The original exception is available in the 'hook_exception' attribute.
    """
    def __init__(self, hook_name, exc_info, encoded_obj, *args, **kwargs):
        self.hook_name = hook_name
        if not exc_info:
            exc_info = (None, None, None)
        exc_type, self.hook_exception, self.hook_traceback = exc_info
        self.object_type = type(encoded_obj)
        msg = "Hook %s raised %r while encoding type <%s>" % (self.hook_name, self.hook_exception.__class__.__name__, self.object_type.__name__)
        if len(args) >= 1:
            msg += ": " + args[0]
            args = args[1:]
        super(JSONEncodeHookError,self).__init__(msg, *args, **kwargs)

#----------------------------------------------------------------------
# The main JSON encoder/decoder class.

class JSON(object):
    """An encoder/decoder for JSON data streams.

    Usually you will call the encode() or decode() methods.  The other
    methods are for lower-level processing.

    Whether the JSON parser runs in strict mode (which enforces exact
    compliance with the JSON spec) or the more forgiving non-string mode
    can be affected by setting the 'strict' argument in the object's
    initialization; or by assigning True or False to the 'strict'
    property of the object.

    You can also adjust a finer-grained control over strictness by
    allowing or preventing specific behaviors.  You can get a list of
    all the available behaviors by accessing the 'behaviors' property.
    Likewise the allowed_behaviors and prevented_behaviors list which
    behaviors will be allowed and which will not.  Call the allow()
    or prevent() methods to adjust these.
    
    """
    _escapes_json = { # character escapes in JSON
        '"': '"',
        '/': '/',
        '\\': '\\',
        'b': '\b',
        'f': '\f',
        'n': '\n',
        'r': '\r',
        't': '\t',
        }

    _escapes_js = { # character escapes in Javascript
        '"': '"',
        '\'': '\'',
        '\\': '\\',
        'b': '\b',
        'f': '\f',
        'n': '\n',
        'r': '\r',
        't': '\t',
        'v': '\v',
        '0': '\x00'
        }

    # Following is a reverse mapping of escape characters, used when we
    # output JSON.  Only those escapes which are always safe (e.g., in JSON)
    # are here.  It won't hurt if we leave questionable ones out.
    _rev_escapes = {'\n': '\\n',
                    '\t': '\\t',
                    '\b': '\\b',
                    '\r': '\\r',
                    '\f': '\\f',
                    '"': '\\"',
                    '\\': '\\\\'}

    json_syntax_characters = u"{}[]\"\\,:0123456789.-+abcdefghijklmnopqrstuvwxyz \t\n\r"

    all_hook_names = ('decode_number', 'decode_float', 'decode_object', 'decode_array', 'decode_string',
                      'encode_value', 'encode_dict', 'encode_dict_key', 'encode_sequence', 'encode_bytes', 'encode_default')

    def __init__(self, strict=False, compactly=True, escape_unicode=False, encode_namedtuple_as_object=True):
        """Creates a JSON encoder/decoder object.
        
        If 'strict' is set to True, then only strictly-conforming JSON
        output will be produced.  Note that this means that some types
        of values may not be convertable and will result in a
        JSONEncodeError exception.
        
        If 'compactly' is set to True, then the resulting string will
        have all extraneous white space removed; if False then the
        string will be "pretty printed" with whitespace and indentation
        added to make it more readable.
        
        If 'escape_unicode' is set to True, then all non-ASCII characters
        will be represented as a unicode escape sequence; if False then
        the actual real unicode character will be inserted if possible.

        The 'escape_unicode' can also be a function, which when called
        with a single argument of a unicode character will return True
        if the character should be escaped or False if it should not.
        
        If you wish to extend the encoding to ba able to handle
        additional types, you may either:

              * subclass this class and override the encode_default()
                method, or

              * set an 'encode_default' hook function (see set_hook())

        If 'encode_namedtuple_as_object' is True, then objects of type
        namedtuple, or subclasses of 'tuple' that have an _asdict()
        method, will be encoded as an object rather than an array.

        """
        import sys, unicodedata, re
        self._numberlike_re = re.compile('^([-+0-9.a-zA-Z]+)')

        self._set_strictness(strict)
        self._encode_compactly = compactly
        self.encode_namedtuple_as_object = encode_namedtuple_as_object
        for hookname in self.all_hook_names:
            self.set_hook( hookname, None )
        try:
            # see if we were passed a predicate function
            b = escape_unicode(u'A')
            self._encode_unicode_as_escapes = escape_unicode
        except (ValueError, NameError, TypeError):
            # Just set to True or False.  We could use lambda x:True
            # to make it more consistent (always a function), but it
            # will be too slow, so we'll make explicit tests later.
            self._encode_unicode_as_escapes = bool(escape_unicode)
        self._sort_dictionary_keys = True

        # The following is a boolean map of the first 256 characters
        # which will quickly tell us which of those characters never
        # need to be escaped.

        self._asciiencodable = \
            [32 <= c < 128 \
                 and not self._rev_escapes.has_key(chr(c)) \
                 and not unicodedata.category(unichr(c)) in ['Cc','Cf','Zl','Zp']
             for c in range(0,256)]

    def clear_hook(self, hookname):
        """Unsets a hook callback, as previously set with set_hook()."""
        self.set_hook( hookname, None )

    def clear_all_hooks(self):
        """Unsets all hook callbacks, as previously set with set_hook()."""
        for hookname in self.all_hook_names:
            self.clear_hook( hookname )

    def set_hook(self, hookname, function):
        """Sets a user-defined callback function used during encoding or decoding.

        The 'hookname' argument must be a string containing the name of
        one of the available hooks, listed below.

        The 'function' argument must either be None, which disables the hook,
        or a callable function.  Hooks do not stack, if you set a hook it will
        undo any previously set hook.

        Netsted values.  When decoding JSON that has nested objects or
        arrays, the decoding hooks will be called once for every
        corresponding value, even if nested.  Generally the decoding
        hooks will be called from the inner-most value outward, and
        then left to right.

        Skipping. Any hook function may raise a JSONSkipHook exception
        if it does not wish to handle the particular invocation.  This
        will have the effect of skipping the hook for that particular
        value, as if the hook was net set.

        AVAILABLE HOOKS:

        * decode_string
            Called for every JSON string literal with the
            Python-equivalent string value as an argument. Expects to
            get a Python object in return.

        * decode_float:
            Called for every JSON number that looks like a float (has
            a ".").  The string representation of the number is passed
            as an argument.  Expects to get a Python object in return.

        * decode_number:
            Called for every JSON number. The string representation of
            the number is passed as an argument.  Expects to get a
            Python object in return.  NOTE: If the number looks like a
            float and the 'decode_float' hook is set, then this hook
            will not be called.

        * decode_array:
            Called for every JSON array. A Python list is passed as
            the argument, and expects to get a Python object back.
            NOTE: this hook will get called for every array, even
            for nested arrays.

        * decode_object:
            Called for every JSON object.  A Python dictionary is passed
            as the argument, and expects to get a Python object back.
            NOTE: this hook will get called for every object, even
            for nested objects.

        * encode_value:
            Called for every Python object which is to be encoded into JSON.

        * encode_dict:
            Called for every Python dictionary or anything that looks
            like a dictionary.

        * encode_dict_key:
            Called for every dictionary key.

        * encode_sequence:
            Called for every Python sequence-like object that is not a
            dictionary or string. This includes lists and tuples.

        * encode_bytes:
            Called for every Python bytes or bytearray type; or for
            any memoryview with a byte ('B') item type.  (Python 3 only)

        * encode_default:
            Called for any Python type which can not otherwise be converted
            into JSON, even after applying any other encoding hooks.

        """
        if hookname in self.all_hook_names:
            att = hookname + '_hook'
            if function != None and not callable(function):
                raise ValueError("Hook %r must be None or a callable function" % hookname)
            setattr( self, att, function )
        else:
            raise ValueError("Unknown hook name %r" % hookname)


    def has_hook(self, hook_name):
        if not hook_name or hook_name not in self.all_hook_names:
            return False
        hook = getattr( self, hook_name + '_hook' )
        return hook != None


    def call_hook(self, hook_name, *args, **kwargs):
        import sys
        if hook_name not in self.all_hook_names:
            raise AttributeError("No such hook %r" % hook_name)
        hook = getattr( self, hook_name + '_hook' )
        try:
            rval = hook( *args, **kwargs )
        except JSONSkipHook:
            raise
        except Exception, err:
            e2 = sys.exc_info()
            if hook_name.startswith('encode_'):
                ecls = JSONEncodeHookError
            else:
                ecls = JSONDecodeHookError
            newerr = ecls( hook_name, e2, *args )
            # Simulate Python 3's: "raise X from Y" exception chaining
            newerr.__cause__ = err
            newerr.__traceback__ = e2[2]
            raise newerr
        return rval


    def _set_strictness(self, strict):
        """Changes the strictness behavior.

        Pass True to be very strict about JSON syntax, or False to be looser.
        """
        self._allow_any_type_at_start = True    # Changed in RFC 7158 (was 'not strict')
        self._allow_all_numeric_signs = not strict
        self._allow_comments = not strict
        self._allow_control_char_in_string = not strict
        self._allow_hex_numbers = not strict
        self._allow_initial_decimal_point = not strict
        self._allow_js_string_escapes = not strict
        self._allow_non_numbers = not strict
        self._allow_nonescape_characters = not strict  # "\z" -> "z"
        self._allow_nonstring_keys = not strict
        self._allow_omitted_array_elements = not strict
        self._allow_single_quoted_strings = not strict
        self._allow_trailing_comma_in_literal = not strict
        self._allow_undefined_values = not strict
        self._allow_unicode_format_control_chars = not strict
        self._allow_unicode_whitespace = not strict
        # Always disable this by default
        self._allow_octal_numbers = False

    def allow(self, behavior):
        """Allow the specified behavior (turn off a strictness check).

        The list of all possible behaviors is available in the behaviors property.
        You can see which behaviors are currently allowed by accessing the
        allowed_behaviors property.

        """
        p = '_allow_' + behavior
        if hasattr(self, p):
            setattr(self, p, True)
        else:
            raise AttributeError('Behavior is not known',behavior)

    def prevent(self, behavior):
        """Prevent the specified behavior (turn on a strictness check).

        The list of all possible behaviors is available in the behaviors property.
        You can see which behaviors are currently prevented by accessing the
        prevented_behaviors property.

        """
        p = '_allow_' + behavior
        if hasattr(self, p):
            setattr(self, p, False)
        else:
            raise AttributeError('Behavior is not known',behavior)

    def _get_behaviors(self):
        return sorted([ n[len('_allow_'):] for n in self.__dict__ \
                        if n.startswith('_allow_')])
    behaviors = property(_get_behaviors,
                         doc='List of known behaviors that can be passed to allow() or prevent() methods')

    def _get_allowed_behaviors(self):
        return sorted([ n[len('_allow_'):] for n in self.__dict__ \
                        if n.startswith('_allow_') and getattr(self,n)])
    allowed_behaviors = property(_get_allowed_behaviors,
                                 doc='List of known behaviors that are currently allowed')

    def _get_prevented_behaviors(self):
        return sorted([ n[len('_allow_'):] for n in self.__dict__ \
                        if n.startswith('_allow_') and not getattr(self,n)])
    prevented_behaviors = property(_get_prevented_behaviors,
                                   doc='List of known behaviors that are currently prevented')

    def _is_strict(self):
        return not self.allowed_behaviors
    strict = property(_is_strict, _set_strictness,
                      doc='True if adherence to RFC 7158 syntax is strict, or False is more generous ECMAScript syntax is permitted')


    def isws(self, c):
        """Determines if the given character is considered as white space.
        
        Note that Javscript is much more permissive on what it considers
        to be whitespace than does JSON.
        
        Ref. ECMAScript section 7.2

        """
        if not self._allow_unicode_whitespace:
            return c in ' \t\n\r'
        else:
            if not isinstance(c,unicode):
                c = unicode(c)
            if c in u' \t\n\r\f\v':
                return True
            import unicodedata
            return unicodedata.category(c) == 'Zs'

    def islineterm(self, c):
        """Determines if the given character is considered a line terminator.

        Ref. ECMAScript section 7.3

        """
        if c == '\r' or c == '\n':
            return True
        if c == u'\u2028' or c == u'\u2029': # unicodedata.category(c) in  ['Zl', 'Zp']
            return True
        return False


    def decode_null(self, s, i=0):
        """Intermediate-level decoder for ECMAScript 'null' keyword.

        Takes a string and a starting index, and returns a Python
        None object and the index of the next unparsed character.

        """
        if i < len(s) and s[i:i+4] == 'null':
            return None, i+4
        raise JSONDecodeError('literal is not the JSON "null" keyword', s)

    def encode_undefined(self):
        """Produces the ECMAScript 'undefined' keyword."""
        return 'undefined'

    def encode_null(self):
        """Produces the JSON 'null' keyword."""
        return 'null'

    def decode_boolean(self, s, i=0):
        """Intermediate-level decode for JSON boolean literals.

        Takes a string and a starting index, and returns a Python bool
        (True or False) and the index of the next unparsed character.

        """
        if s[i:i+4] == 'true':
            return True, i+4
        elif s[i:i+5] == 'false':
            return False, i+5
        raise JSONDecodeError('literal value is not a JSON boolean keyword',s)

    def encode_boolean(self, b):
        """Encodes the Python boolean into a JSON Boolean literal."""
        if bool(b):
            return 'true'
        return 'false'

    def decode_number(self, s, i=0, imax=None):
        """Intermediate-level decoder for JSON numeric literals.

        Takes a string and a starting index, and returns a Python
        suitable numeric type and the index of the next unparsed character.

        The returned numeric type can be either of a Python int,
        long, or float.  In addition some special non-numbers may
        also be returned such as nan, inf, and neginf (technically
        which are Python floats, but have no numeric value.)

        Ref. ECMAScript section 8.5.

        """
        if imax is None:
            imax = len(s)
        # Use external number parser hook if available
        if self.has_hook('decode_number') or self.has_hook('decode_float'):
            match = self._numberlike_re.match( s[i:] )
            if match:
                nbr = match.group(1)
                if '.' in nbr and self.has_hook('decode_float'):
                    try:
                        val = self.call_hook( 'decode_float', nbr )
                    except JSONSkipHook:
                        pass
                    else:
                        return val, i + len(nbr)
                elif self.has_hook('decode_number'):
                    try:
                        val = self.call_hook( 'decode_number', nbr )
                    except JSONSkipHook:
                        pass
                    else:
                        return val, i + len(nbr)
        # Detect initial sign character(s)
        if not self._allow_all_numeric_signs:
            if s[i] == '+' or (s[i] == '-' and i+1 < imax and \
                               s[i+1] in '+-'):
                raise JSONDecodeError('numbers in strict JSON may only have a single "-" as a sign prefix',s[i:])
        sign = +1
        j = i  # j will point after the sign prefix
        while j < imax and s[j] in '+-':
            if s[j] == '-': sign = sign * -1
            j += 1
        # Check for ECMAScript symbolic non-numbers
        if s[j:j+3] == 'NaN':
            if self._allow_non_numbers:
                return nan, j+3
            else:
                raise JSONDecodeError('NaN literals are not allowed in strict JSON')
        elif s[j:j+8] == 'Infinity':
            if self._allow_non_numbers:
                if sign < 0:
                    return neginf, j+8
                else:
                    return inf, j+8
            else:
                raise JSONDecodeError('Infinity literals are not allowed in strict JSON')
        elif s[j:j+2] in ('0x','0X'):
            hexdig = helpers.hexdigits
            if self._allow_hex_numbers:
                k = j+2
                while k < imax and s[k] in hexdig:
                    k += 1
                n = sign * helpers.decode_hex( s[j+2:k] )
                return n, k
            else:
                raise JSONDecodeError('hexadecimal literals are not allowed in strict JSON',s[i:])
        else:
            # Decimal (or octal) number, find end of number.
            # General syntax is:  \d+[\.\d+][e[+-]?\d+]
            k = j   # will point to end of digit sequence
            could_be_octal = ( k+1 < imax and s[k] == '0' )  # first digit is 0
            decpt = None  # index into number of the decimal point, if any
            ept = None # index into number of the e|E exponent start, if any
            esign = '+' # sign of exponent
            sigdigits = 0 # number of significant digits (approx, counts end zeros)
            while k < imax and (s[k].isdigit() or s[k] in '.+-eE'):
                c = s[k]
                if c not in helpers.octaldigits:
                    could_be_octal = False
                if c == '.':
                    if decpt is not None or ept is not None:
                        break
                    else:
                        decpt = k-j
                elif c in 'eE':
                    if ept is not None:
                        break
                    else:
                        ept = k-j
                elif c in '+-':
                    if not ept:
                        break
                    esign = c
                else: #digit
                    if not ept:
                        sigdigits += 1
                k += 1
            number = s[j:k]  # The entire number as a string
            #print 'NUMBER IS: ', repr(number), ', sign', sign, ', esign', esign, \
            #      ', sigdigits', sigdigits, \
            #      ', decpt', decpt, ', ept', ept

            # Handle octal integers first as an exception.  If octal
            # is not enabled (the ECMAScipt standard) then just do
            # nothing and treat the string as a decimal number.
            if could_be_octal and self._allow_octal_numbers:
                n = sign * helpers.decode_octal( number )
                return n, k

            # A decimal number.  Do a quick check on JSON syntax restrictions.
            if number[0] == '.' and not self._allow_initial_decimal_point:
                raise JSONDecodeError('numbers in strict JSON must have at least one digit before the decimal point',s[i:])
            elif number[0] == '0' and \
                     len(number) > 1 and number[1].isdigit():
                if self._allow_octal_numbers:
                    raise JSONDecodeError('initial zero digit is only allowed for octal integers',s[i:])
                else:
                    raise JSONDecodeError('initial zero digit must not be followed by other digits (octal numbers are not permitted)',s[i:])
            # Make sure decimal point is followed by a digit
            if decpt is not None:
                if decpt+1 >= len(number) or not number[decpt+1].isdigit():
                    raise JSONDecodeError('decimal point must be followed by at least one digit',s[i:])
            # Determine the exponential part
            if ept is not None:
                if ept+1 >= len(number):
                    raise JSONDecodeError('exponent in number is truncated',s[i:])
                try:
                    exponent = int(number[ept+1:])
                except ValueError:
                    raise JSONDecodeError('not a valid exponent in number',s[i:])
                ##print 'EXPONENT', exponent
            else:
                exponent = 0
            # Try to make an int/long first.
            if decpt is None and exponent >= 0:
                # An integer
                if ept:
                    n = int(number[:ept])
                else:
                    n = int(number)
                n *= sign
                if exponent:
                    n *= 10**exponent
                if n == 0 and sign < 0:
                    # minus zero, must preserve negative sign so make a float
                    n = -0.0
            else:
                try:
                    if decimal and (abs(exponent) > float_maxexp or sigdigits > float_sigdigits):
                        try:
                            n = decimal.Decimal(number)
                            #n = n.normalize()
                        except decimal.Overflow:
                            if sign<0:
                                n = neginf
                            else:
                                n = inf
                        else:
                            n *= sign
                    else:
                        n = float(number) * sign
                except ValueError:
                    raise JSONDecodeError('not a valid JSON numeric literal', s[i:j])
            return n, k

    def encode_number(self, n):
        """Encodes a Python numeric type into a JSON numeric literal.
        
        The special non-numeric values of float('nan'), float('inf')
        and float('-inf') are translated into appropriate JSON
        literals.
        
        Note that Python complex types are not handled, as there is no
        ECMAScript equivalent type.
        
        """
        if isinstance(n, complex):
            if n.imag:
                raise JSONEncodeError('Can not encode a complex number that has a non-zero imaginary part',n)
            n = n.real
        if isinstance(n, (int,long)):
            return str(n)
        if decimal and isinstance(n, decimal.Decimal):
            return str(n)
        global nan, inf, neginf
        if n is nan:
            return 'NaN'
        elif n is inf:
            return 'Infinity'
        elif n is neginf:
            return '-Infinity'
        elif isinstance(n, float):
            # Check for non-numbers.
            # In python nan == inf == -inf, so must use repr() to distinguish
            reprn = repr(n).lower()
            if ('inf' in reprn and '-' in reprn) or n == neginf:
                return '-Infinity'
            elif 'inf' in reprn or n is inf:
                return 'Infinity'
            elif 'nan' in reprn or n is nan:
                return 'NaN'
            return repr(n)
        else:
            raise TypeError('encode_number expected an integral, float, or decimal number type',type(n))

    def decode_string(self, s, i=0, imax=None):
        """Intermediate-level decoder for JSON string literals.

        Takes a string and a starting index, and returns a Python
        string (or unicode string) and the index of the next unparsed
        character.

        """
        if imax is None:
            imax = len(s)
        if imax < i+2 or s[i] not in '"\'':
            raise JSONDecodeError('string literal must be properly quoted',s[i:])
        closer = s[i]
        if closer == '\'' and not self._allow_single_quoted_strings:
            raise JSONDecodeError('string literals must use double quotation marks in strict JSON',s[i:])
        i += 1 # skip quote
        if self._allow_js_string_escapes:
            escapes = self._escapes_js
        else:
            escapes = self._escapes_json
        ccallowed = self._allow_control_char_in_string
        chunks = []
        _append = chunks.append
        done = False
        high_surrogate = None
        while i < imax:
            c = s[i]
            # Make sure a high surrogate is immediately followed by a low surrogate
            if high_surrogate and (i+1 >= imax or s[i:i+2] != '\\u'):
                raise JSONDecodeError('High unicode surrogate must be followed by a low surrogate',s[i:])
            if c == closer:
                i += 1 # skip end quote
                done = True
                break
            elif c == '\\':
                # Escaped character
                i += 1
                if i >= imax:
                    raise JSONDecodeError('escape in string literal is incomplete',s[i-1:])
                c = s[i]

                if '0' <= c <= '7' and self._allow_octal_numbers:
                    # Handle octal escape codes first so special \0 doesn't kick in yet.
                    # Follow Annex B.1.2 of ECMAScript standard.
                    if '0' <= c <= '3':
                        maxdigits = 3
                    else:
                        maxdigits = 2
                    octdig = helpers.octaldigits
                    for k in range(i, i+maxdigits+1):
                        if k >= imax or s[k] not in octdig:
                            break
                    n = helpers.decode_octal(s[i:k])
                    if n < 128:
                        _append( chr(n) )
                    else:
                        _append( unichr(n) )
                    i = k
                    continue

                if escapes.has_key(c):
                    _append(escapes[c])
                    i += 1
                elif c == 'u' or c == 'x':
                    i += 1
                    if c == 'u':
                        digits = 4
                    else: # c== 'x'
                        if not self._allow_js_string_escapes:
                            raise JSONDecodeError(r'string literals may not use the \x hex-escape in strict JSON',s[i-1:])
                        digits = 2
                    if i+digits >= imax:
                        raise JSONDecodeError('numeric character escape sequence is truncated',s[i-1:])
                    n = helpers.decode_hex( s[i:i+digits] )
                    if high_surrogate:
                        # Decode surrogate pair and clear high surrogate
                        _append( helpers.surrogate_pair_as_unicode( high_surrogate, unichr(n) ) )
                        high_surrogate = None
                    elif n < 128:
                        # ASCII chars always go in as a str
                        _append( chr(n) )
                    elif 0xd800 <= n <= 0xdbff: # high surrogate
                        if imax < i + digits + 2 or s[i+digits] != '\\' or s[i+digits+1] != 'u':
                            raise JSONDecodeError('High unicode surrogate must be followed by a low surrogate',s[i-2:])
                        high_surrogate = unichr(n)  # remember until we get to the low surrogate
                    elif 0xdc00 <= n <= 0xdfff: # low surrogate
                        raise JSONDecodeError('Low unicode surrogate must be proceeded by a high surrogate',s[i-2:])
                    else:
                        # Other chars go in as a unicode char
                        _append( unichr(n) )
                    i += digits
                else:
                    # Unknown escape sequence
                    if self._allow_nonescape_characters:
                        _append( c )
                        i += 1
                    else:
                        raise JSONDecodeError('unsupported escape code in JSON string literal',s[i-1:])
            elif ord(c) <= 0x1f: # A control character
                if self.islineterm(c):
                    raise JSONDecodeError('line terminator characters must be escaped inside string literals',s[i:])
                elif ccallowed:
                    _append( c )
                    i += 1
                else:
                    raise JSONDecodeError('control characters must be escaped inside JSON string literals',s[i:])
            else: # A normal character; not an escape sequence or end-quote.
                # Find a whole sequence of "safe" characters so we can append them
                # all at once rather than one a time, for speed.
                j = i
                i += 1
                unsafe = helpers.unsafe_string_chars
                while i < imax and s[i] not in unsafe and s[i] != closer:
                    i += 1
                _append(s[j:i])
        if not done:
            raise JSONDecodeError('string literal is not terminated with a quotation mark',s)
        s = ''.join( chunks )
        if self.has_hook('decode_string'):
            try:
                s = self.call_hook( 'decode_string', s )
            except JSONSkipHook:
                pass
        return s, i

    def encode_string(self, s):
        """Encodes a Python string into a JSON string literal.

        """
        # Must handle instances of UserString specially in order to be
        # able to use ord() on it's simulated "characters".
        import unicodedata
        import UserString
        if isinstance(s, UserString.UserString):
            def tochar(c):
                return c.data
        else:
            # Could use "lambda c:c", but that is too slow.  So we set to None
            # and use an explicit if test inside the loop.
            tochar = None
        
        chunks = []
        chunks.append('"')
        revesc = self._rev_escapes
        asciiencodable = self._asciiencodable
        encunicode = self._encode_unicode_as_escapes
        i = 0
        imax = len(s)
        while i < imax:
            if tochar:
                c = tochar(s[i])
            else:
                c = s[i]
            cord = ord(c)
            if cord < 256 and asciiencodable[cord] and isinstance(encunicode, bool):
                # Contiguous runs of plain old printable ASCII can be copied
                # directly to the JSON output without worry (unless the user
                # has supplied a custom is-encodable function).
                j = i
                i += 1
                while i < imax:
                    if tochar:
                        c = tochar(s[i])
                    else:
                        c = s[i]
                    cord = ord(c)
                    if cord < 256 and asciiencodable[cord]:
                        i += 1
                    else:
                        break
                chunks.append( unicode(s[j:i]) )
            elif revesc.has_key(c):
                # Has a shortcut escape sequence, like "\n"
                chunks.append(revesc[c])
                i += 1
            elif cord <= 0x1F:
                # Always unicode escape ASCII-control characters
                chunks.append(r'\u%04x' % cord)
                i += 1
            elif 0xD800 <= cord <= 0xDFFF:
                # A raw surrogate character!  This should never happen
                # and there's no way to include it in the JSON output.
                # So all we can do is complain.
                cname = 'U+%04X' % cord
                raise JSONEncodeError('can not include or escape a Unicode surrogate character',cname)
            else:
                # Some other Unicode character
                ccat = unicodedata.category( unichr(cord) )
                if cord <= 0xFFFF:
                    # Other BMP Unicode character
                    if ccat in ['Cc','Cf','Zl','Zp']:
                        doesc = True
                    elif isinstance(encunicode, bool):
                        doesc = encunicode
                    else:
                        doesc = encunicode( c )
                    if doesc:
                        chunks.append(r'\u%04x' % cord)
                    else:
                        chunks.append( c )
                    i += 1
                else: # ord(c) >= 0x10000
                    # Non-BMP Unicode
                    if ccat in ['Cc','Cf','Zl','Zp']:
                        doesc = True
                    elif isinstance(encunicode, bool):
                        doesc = encunicode
                    else:
                        doesc = encunicode( c )
                    if doesc:
                        for surrogate in helpers.unicode_as_surrogate_pair(c):
                            chunks.append(r'\u%04x' % ord(surrogate))
                    else:
                        chunks.append( c )
                    i += 1
        chunks.append('"')
        return ''.join( chunks )

    def skip_comment(self, txt, i=0):
        """Skips an ECMAScript comment, either // or /* style.

        The contents of the comment are returned as a string, as well
        as the index of the character immediately after the comment.

        """
        if i+1 >= len(txt) or txt[i] != '/' or txt[i+1] not in '/*':
            return None, i
        if not self._allow_comments:
            raise JSONDecodeError('comments are not allowed in strict JSON',txt[i:])
        multiline = (txt[i+1] == '*')
        istart = i
        i += 2
        while i < len(txt):
            if multiline:
                if txt[i] == '*' and i+1 < len(txt) and txt[i+1] == '/':
                    j = i+2
                    break
                elif txt[i] == '/' and i+1 < len(txt) and txt[i+1] == '*':
                    raise JSONDecodeError('multiline /* */ comments may not nest',txt[istart:i+1])
            else:
                if self.islineterm(txt[i]):
                    j = i  # line terminator is not part of comment
                    break
            i += 1

        if i >= len(txt):
            if not multiline:
                j = len(txt)  # // comment terminated by end of file is okay
            else:
                raise JSONDecodeError('comment was never terminated',txt[istart:])
        return txt[istart:j], j

    def skipws(self, txt, i=0, imax=None, skip_comments=True):
        """Skips whitespace.
        """
        if not self._allow_comments and not self._allow_unicode_whitespace:
            if imax is None:
                imax = len(txt)
            while i < imax and txt[i] in ' \r\n\t':
                i += 1
            return i
        else:
            return self.skipws_any(txt, i, imax, skip_comments)

    def skipws_any(self, txt, i=0, imax=None, skip_comments=True):
        """Skips all whitespace, including comments and unicode whitespace

        Takes a string and a starting index, and returns the index of the
        next non-whitespace character.

        If skip_comments is True and not running in strict JSON mode, then
        comments will be skipped over just like whitespace.

        """
        if imax is None:
            imax = len(txt)
        while i < imax:
            if txt[i] == '/':
                cmt, i = self.skip_comment(txt, i)
            if i < imax and self.isws(txt[i]):
                i += 1
            else:
                break
        return i

    def decode_composite(self, txt, i=0, imax=None):
        """Intermediate-level JSON decoder for composite literal types (array and object).

        Takes text and a starting index, and returns either a Python list or
        dictionary and the index of the next unparsed character.

        """
        if imax is None:
            imax = len(txt)
        i = self.skipws(txt, i, imax)
        starti = i
        if i >= imax or txt[i] not in '{[':
            raise JSONDecodeError('composite object must start with "[" or "{"',txt[i:])
        if txt[i] == '[':
            isdict = False
            closer = ']'
            obj = []
        else:
            isdict = True
            closer = '}'
            obj = {}
        i += 1 # skip opener
        i = self.skipws(txt, i, imax)

        if i < imax and txt[i] == closer:
            # empty composite
            i += 1
            done = True
        else:
            saw_value = False   # set to false at beginning and after commas
            done = False
            while i < imax:
                i = self.skipws(txt, i, imax)
                if i < imax and (txt[i] == ',' or txt[i] == closer):
                    c = txt[i]
                    i += 1
                    if c == ',':
                        if not saw_value:
                            # no preceeding value, an elided (omitted) element
                            if isdict:
                                raise JSONDecodeError('can not omit elements of an object (dictionary)')
                            if self._allow_omitted_array_elements:
                                if self._allow_undefined_values:
                                    obj.append( undefined )
                                else:
                                    obj.append( None )
                            else:
                                raise JSONDecodeError('strict JSON does not permit omitted array (list) elements',txt[i:])
                        saw_value = False
                        continue
                    else: # c == closer
                        if not saw_value and not self._allow_trailing_comma_in_literal:
                            if isdict:
                                raise JSONDecodeError('strict JSON does not allow a final comma in an object (dictionary) literal',txt[i-2:])
                            else:
                                raise JSONDecodeError('strict JSON does not allow a final comma in an array (list) literal',txt[i-2:])
                        done = True
                        break

                # Decode the item
                if isdict and self._allow_nonstring_keys:
                    r = self.decodeobj(txt, i, identifier_as_string=True)
                else:
                    r = self.decodeobj(txt, i, identifier_as_string=False)
                if r:
                    if saw_value:
                        # two values without a separating comma
                        raise JSONDecodeError('values must be separated by a comma', txt[i:r[1]])
                    saw_value = True
                    i = self.skipws(txt, r[1], imax)
                    if isdict:
                        key = r[0]  # Ref 11.1.5
                        if not helpers.isstringtype(key):
                            if helpers.isnumbertype(key):
                                if not self._allow_nonstring_keys:
                                    raise JSONDecodeError('strict JSON only permits string literals as object properties (dictionary keys)',txt[starti:])
                            else:
                                raise JSONDecodeError('object properties (dictionary keys) must be either string literals or numbers',txt[starti:])
                        if i >= imax or txt[i] != ':':
                            raise JSONDecodeError('object property (dictionary key) has no value, expected ":"',txt[starti:])
                        i += 1
                        i = self.skipws(txt, i, imax)
                        rval = self.decodeobj(txt, i)
                        if rval:
                            i = self.skipws(txt, rval[1], imax)
                            obj[key] = rval[0]
                        else:
                            raise JSONDecodeError('object property (dictionary key) has no value',txt[starti:])
                    else: # list
                        obj.append( r[0] )
                else: # not r
                    if isdict:
                        raise JSONDecodeError('expected a value, or "}"',txt[i:])
                    elif not self._allow_omitted_array_elements:
                        raise JSONDecodeError('expected a value or "]"',txt[i:])
                    else:
                        raise JSONDecodeError('expected a value, "," or "]"',txt[i:])
            # end while
        if not done:
            if isdict:
                raise JSONDecodeError('object literal (dictionary) is not terminated',txt[starti:])
            else:
                raise JSONDecodeError('array literal (list) is not terminated',txt[starti:])
        if isdict and self.has_hook('decode_object'):
            try:
                obj = self.call_hook( 'decode_object', obj )
            except JSONSkipHook:
                pass
        elif self.has_hook('decode_array'):
            try:
                obj = self.call_hook( 'decode_array', obj )
            except JSONSkipHook:
                pass
        return obj, i

    def decode_javascript_identifier(self, name):
        """Convert a JavaScript identifier into a Python string object.

        This method can be overriden by a subclass to redefine how JavaScript
        identifiers are turned into Python objects.  By default this just
        converts them into strings.

        """
        return name

    def decodeobj(self, txt, i=0, imax=None, identifier_as_string=False, only_object_or_array=False):
        """Intermediate-level JSON decoder.

        Takes a string and a starting index, and returns a two-tuple consting
        of a Python object and the index of the next unparsed character.

        If there is no value at all (empty string, etc), the None is
        returned instead of a tuple.

        """
        if imax is None:
            imax = len(txt)
        obj = None
        i = self.skipws(txt, i, imax)
        if i >= imax:
            raise JSONDecodeError('Unexpected end of input')
        c = txt[i]

        if c == '[' or c == '{':
            obj, i = self.decode_composite(txt, i, imax)
        elif only_object_or_array:
            raise JSONDecodeError('JSON document must start with an object or array type only', txt[i:i+20])
        elif c == '"' or c == '\'':
            obj, i = self.decode_string(txt, i, imax)
        elif c.isdigit() or c in '.+-':
            obj, i = self.decode_number(txt, i, imax)
        elif c.isalpha() or c in'_$':
            j = i
            while j < imax and (txt[j].isalnum() or txt[j] in '_$'):
                j += 1
            kw = txt[i:j]
            if kw == 'null':
                obj, i = None, j
            elif kw == 'true':
                obj, i = True, j
            elif kw == 'false':
                obj, i = False, j
            elif kw == 'undefined':
                if self._allow_undefined_values:
                    obj, i = undefined, j
                else:
                    raise JSONDecodeError('strict JSON does not allow undefined elements',txt[i:])
            elif kw == 'NaN' or kw == 'Infinity':
                obj, i = self.decode_number(txt, i)
            else:
                if identifier_as_string:
                    obj, i = self.decode_javascript_identifier(kw), j
                else:
                    raise JSONDecodeError('unknown keyword or identifier',kw)
        else:
            raise JSONDecodeError('can not decode value',txt[i:])
        return obj, i



    def decode(self, txt):
        """Decodes a JSON-endoded string into a Python object."""
        if self._allow_unicode_format_control_chars:
            txt = helpers.strip_format_control_chars(txt)
        r = self.decodeobj(txt, 0, only_object_or_array=not self._allow_any_type_at_start)
        if not r:
            raise JSONDecodeError('can not decode value',txt)
        else:
            obj, i = r
            i = self.skipws(txt, i)
            if i < len(txt):
                raise JSONDecodeError('unexpected or extra text',txt[i:])
        return obj

    def encode(self, obj, nest_level=0):
        """Encodes the Python object into a JSON string representation.

        This method will first attempt to encode an object by seeing
        if it has a json_equivalent() method.  If so than it will
        call that method and then recursively attempt to encode
        the object resulting from that call.

        Next it will attempt to determine if the object is a native
        type or acts like a squence or dictionary.  If so it will
        encode that object directly.

        Finally, if no other strategy for encoding the object of that
        type exists, it will call the encode_default() method.  That
        method currently raises an error, but it could be overridden
        by subclasses to provide a hook for extending the types which
        can be encoded.

        """
        chunks = []
        self.encode_helper(chunks, obj, nest_level)
        if nest_level == 0 and not self._encode_compactly:
            chunks.append( u"\n" )
        return ''.join( chunks )

    def _classify_for_encoding( self, obj ):
        import sys
        c = 'other'
        if obj is None:
            c = 'null'
        elif obj is undefined:
            c = 'undefined'
        elif isinstance(obj,bool):
            c =  'bool'
        elif isinstance(obj, (int,long,float,complex)) or\
                (decimal and isinstance(obj, decimal.Decimal)):
            c = 'number'
        elif isinstance(obj, basestring) or helpers.isstringtype(obj):
            c = 'string'
        else:
            if isinstance(obj,dict):
                c = 'dict'
            elif isinstance(obj,tuple) and self.encode_namedtuple_as_object \
                and hasattr(obj,'_asdict') and callable(obj._asdict):
                c = 'namedtuple'
            elif isinstance(obj, (list,tuple,set,frozenset)):
                c =  'sequence'
            elif hasattr(obj,'iterkeys') or (hasattr(obj,'__getitem__') and hasattr(obj,'keys')):
                c = 'dict'
            elif sys.version_info.major >= 3 and isinstance(obj,(bytes,bytearray)):
                c = 'bytes'
            elif sys.version_info.major >= 3 and isinstance(obj,memoryview):
                c = 'memoryview'
            else:
                c = 'other'
        return c

    def encode_helper(self, chunklist, obj, nest_level):
        #print 'encode_helper(chunklist=%r, obj=%r, nest_level=%r)'%(chunklist,obj,nest_level)
        obj_classification = self._classify_for_encoding( obj )

        if self.has_hook('encode_value'):
            orig_obj = obj
            try:
                obj = self.call_hook( 'encode_value', obj )
            except JSONSkipHook:
                pass

            if obj is not orig_obj:
                prev_cls = obj_classification
                obj_classification = self._classify_for_encoding( obj )
                if obj_classification != prev_cls:
                    # Got a different type of object, re-encode again
                    chunklist.append( self.encode( obj, nest_level=nest_level ) )
                    return

        if hasattr(obj, 'json_equivalent'):
            json = self.encode_equivalent( obj, nest_level=nest_level )
            if json is not None:
                chunklist.append( json )
                return


        if obj_classification == 'null':
            chunklist.append( self.encode_null() )
        elif obj_classification == 'undefined':
            if self._allow_undefined_values:
                chunklist.append( self.encode_undefined() )
            else:
                raise JSONEncodeError('strict JSON does not permit "undefined" values')
        elif obj_classification == 'bool':
            chunklist.append( self.encode_boolean(obj) )
        elif obj_classification == 'number':
            try:
                encoded_num = self.encode_number(obj)
            except JSONEncodeError, err1:
                # Bad number, probably a complex with non-zero imaginary part.
                # Let the default encoders take a shot at encoding.
                try:
                    encoded_num = self.try_encode_default(obj)
                except Exception, err2:
                    # Default handlers couldn't deal with it, re-raise original exception.
                    raise err1
            chunklist.append( encoded_num )
        elif obj_classification == 'string':
            chunklist.append( self.encode_string(obj) )
        else:
            # Anything left is probably composite, or an unconvertable type.
            self.encode_composite(chunklist, obj, nest_level)

    def encode_composite(self, chunklist, obj, nest_level, obj_classification=None):
        """Encodes just dictionaries, lists, or sequences.

        Basically handles any python type for which iter() can create
        an iterator object.

        This method is not intended to be called directly.  Use the
        encode() method instead.

        """
        import sys
        if not obj_classification:
            obj_classification = self._classify_for_encoding(obj)

        # Convert namedtuples to dictionaries
        if obj_classification == 'namedtuple':
            obj = obj._asdict()
            obj_classification = 'dict'

        # Convert 'unsigned byte' memory views into plain bytes
        if obj_classification == 'memoryview' and obj.format == 'B':
            obj = obj.tobytes()
            obj_classification = 'bytes'

        # Run hooks
        hook_name = None
        if obj_classification == 'dict':
            hook_name = 'encode_dict'
        elif obj_classification == 'sequence':
            hook_name = 'encode_sequence'
        elif obj_classification == 'bytes':
            hook_name = 'encode_bytes'

        if self.has_hook(hook_name):
            try:
                new_obj = self.call_hook( hook_name, obj )
            except JSONSkipHook:
                pass
            else:
                if new_obj is not obj:
                    obj = new_obj
                    prev_cls = obj_classification
                    obj_classification = self._classify_for_encoding( obj )
                    if obj_classification != prev_cls:
                        # Transformed to a different kind of object, call
                        # back to the general encode() method.
                        chunklist.append( self.encode( obj, nest_level=nest_level ) )
                        return
                    # Else, fall through

        # At his point we have decided to do with an object or an array
        isdict = (obj_classification == 'dict')

        # Get iterator
        it = None
        if isdict and hasattr(obj,'iterkeys'):
            try:
                it = obj.iterkeys()
            except AttributeError:
                pass
        else:
            try:
                it = iter(obj)
            except TypeError:
                pass

        # Convert each member to JSON
        if it is not None:
            compactly = self._encode_compactly
            if isdict:
                chunklist.append('{')
                if compactly:
                    dictcolon = ':'
                else:
                    dictcolon = ' : '
            else:
                chunklist.append('[')
            #print nest_level, 'opening sequence:', repr(chunklist)
            if not compactly:
                indent0 = '  ' * nest_level
                indent = '  ' * (nest_level+1)
                chunklist.append(' ')
            sequence_chunks = []  # use this to allow sorting afterwards if dict
            try: # while not StopIteration
                numitems = 0
                while True:
                    obj2 = it.next()
                    if obj2 is obj:
                        raise JSONEncodeError('trying to encode an infinite sequence',obj)
                    if isdict:
                        obj3 = obj[obj2]
                        # Dictionary key is in obj2 and value in obj3.

                        # Let any hooks transform the key.
                        if self.has_hook('encode_value'):
                            try:
                                newobj = self.call_hook( 'encode_value', obj2 )
                            except JSONSkipHook:
                                pass
                            else:
                                obj2 = newobj
                        if self.has_hook('encode_dict_key'):
                            try:
                                newkey = self.call_hook( 'encode_dict_key', obj2 )
                            except JSONSkipHook:
                                pass
                            else:
                                obj2 = newkey

                        # Check JSON restrictions on key types
                        if not helpers.isstringtype(obj2):
                            if helpers.isnumbertype(obj2):
                                if not self._allow_nonstring_keys:
                                    raise JSONEncodeError('object properties (dictionary keys) must be strings in strict JSON',obj2)
                            else:
                                raise JSONEncodeError('object properties (dictionary keys) can only be strings or numbers in ECMAScript',obj2)

                    # Encode this item in the sequence and put into item_chunks
                    item_chunks = []
                    self.encode_helper( item_chunks, obj2, nest_level=nest_level+1 )
                    if isdict:
                        item_chunks.append(dictcolon)
                        self.encode_helper(item_chunks, obj3, nest_level=nest_level+2)

                    sequence_chunks.append(item_chunks)
                    numitems += 1
            except StopIteration:
                pass

            if isdict and self._sort_dictionary_keys:
                sequence_chunks.sort()  # Note sorts by JSON repr, not original Python object
            if compactly:
                sep = ','
            else:
                sep = ',\n' + indent

            #print nest_level, 'closing sequence'
            #print nest_level, 'chunklist:', repr(chunklist)
            #print nest_level, 'sequence_chunks:', repr(sequence_chunks)
            extend_and_flatten_list_with_sep( chunklist, sequence_chunks, sep )
            #print nest_level, 'new chunklist:', repr(chunklist)

            if not compactly:
                if numitems > 1:
                    chunklist.append('\n' + indent0)
                else:
                    chunklist.append(' ')
            if isdict:
                chunklist.append('}')
            else:
                chunklist.append(']')
        else: # Can not get iterator, must be an unknown type
            json_fragment = self.try_encode_default( obj, nest_level=nest_level )
            chunklist.append( json_fragment )


    def encode_equivalent( self, obj, nest_level=0 ):
        """This method is used to encode user-defined class objects.

        The object being encoded should have a json_equivalent()
        method defined which returns another equivalent object which
        is easily JSON-encoded.  If the object in question has no
        json_equivalent() method available then None is returned
        instead of a string so that the encoding will attempt the next
        strategy.

        If a caller wishes to disable the calling of json_equivalent()
        methods, then subclass this class and override this method
        to just return None.
        
        """
        if hasattr(obj, 'json_equivalent') \
               and callable(getattr(obj,'json_equivalent')):
            obj2 = obj.json_equivalent()
            if obj2 is obj:
                # Try to prevent careless infinite recursion
                raise JSONEncodeError('object has a json_equivalent() method that returns itself',obj)
            json2 = self.encode( obj2, nest_level=nest_level )
            return json2
        else:
            return None

    def try_encode_default( self, obj, nest_level=0 ):
        orig_obj = obj
        if self.has_hook('encode_default'):
            try:
                obj = self.call_hook( 'encode_default', obj )
            except JSONSkipHook:
                pass
            else:
                if obj is not orig_obj:
                    # Hook made a transformation, re-encode it
                    return self.encode( obj, nest_level=nest_level )

        # The last chance... encode_default method (possibly overridden by subclass)
        obj =self.encode_default( obj, nest_level=nest_level )
        if obj is not orig_obj:
            return self.encode( obj, nest_level=nest_level )

        # End of the road.
        raise JSONEncodeError('can not encode object into a JSON representation',obj)


    def encode_default(self, obj, nest_level=0):
        """DEPRECATED.

        This method is used to encode objects into JSON which are not straightforward.

        This method is intended to be overridden by subclasses which wish
        to extend this encoder to handle additional types.

        """
        raise JSONEncodeError('can not encode object into a JSON representation',obj)


# ------------------------------

def encode( obj,
            strict=False,
            compactly=True,
            escape_unicode=False,
            encoding=None,
            encode_namedtuple_as_object=True,
            **kw ):
    """Encodes a Python object into a JSON-encoded string.

    If 'strict' is set to True, then only strictly-conforming JSON
    output will be produced.  Note that this means that some types
    of values may not be convertable and will result in a
    JSONEncodeError exception.

    If 'compactly' is set to True, then the resulting string will
    have all extraneous white space removed; if False then the
    string will be "pretty printed" with whitespace and indentation
    added to make it more readable.

    If 'encode_namedtuple_as_object' is True, then objects of type
    namedtuple, or subclasses of 'tuple' that have an _asdict()
    method, will be encoded as an object rather than an array.

    CONCERNING CHARACTER ENCODING:

    The 'encoding' argument should be one of:

        * None - The return will be a Unicode string.
        * encoding_name - A string which is the name of a known
              encoding, such as 'UTF-8' or 'ascii'.
        * codec - A CodecInfo object, such as as found by codecs.lookup().
              This allows you to use a custom codec as well as those
              built into Python.

    If an encoding is given (either by name or by codec), then the
    returned value will be a byte array (Python 3), or a 'str' string
    (Python 2); which represents the raw set of bytes.  Otherwise,
    if encoding is None, then the returned value will be a Unicode
    string.

    The 'escape_unicode' argument is used to determine which characters
    in string literals must be \u escaped.  Should be one of:

        * True  -- All non-ASCII characters are always \u escaped.
        * False -- Try to insert actual Unicode characters if possible.
        * function -- A user-supplied function that accepts a single
             unicode character and returns True or False; where True
             means to \u escape that character.

    Regardless of escape_unicode, certain characters will always be
    \u escaped. Additionaly any characters not in the output encoding
    repertoire for the encoding codec will be \u escaped as well.

    """
    import sys, codecs

    # Find the codec to use. CodecInfo will be in 'cdk' and name in 'encoding'.
    if encoding is None:
        cdk = None
    elif isinstance(encoding, codecs.CodecInfo):
        cdk = encoding
        encoding = cdk.name
    else:
        cdk = helpers.lookup_codec( encoding )
        if not cdk:
            raise JSONEncodeError('no codec available for character encoding',encoding)

    if escape_unicode and callable(escape_unicode):
        pass  # User-supplied repertoire test function
    else:
        if escape_unicode==True or not cdk or cdk.name.lower() == 'ascii':
            # ASCII, ISO8859-1, or and Unknown codec -- \u escape anything not ASCII
            def escape_unicode( c ):
                return ord(c) >= 0x80
        elif cdk.name == 'iso8859-1':
            def escape_unicode( c ):
                return ord(c) >= 0x100
        elif cdk and cdk.name.lower().startswith('utf'):
            # All UTF-x encodings can do the whole Unicode repertoire, so
            # do nothing special.
            escape_unicode = False
        else:
            # An unusual codec.  We need to test every character
            # to see if it is in the codec's repertoire to determine
            # if we should \u escape that character.
            enc_func = cdk.encode
            def escape_unicode( c ):
                try:
                    enc_func( c )
                except UnicodeEncodeError:
                    return True
                else:
                    return False

    # Make sure the encoding is not degenerate
    if encoding is not None:
        try:
            output, nchars = cdk.encode( JSON.json_syntax_characters )
        except UnicodeError, err:
            raise JSONEncodeError("Output encoding %s is not sufficient to encode JSON" % cdk.name)

    # Do the JSON encoding
    j = JSON( strict=strict,
              compactly=compactly,
              escape_unicode=escape_unicode,
              encode_namedtuple_as_object=encode_namedtuple_as_object )

    for keyword, value in kw.items():
        if keyword in j.all_hook_names:
            j.set_hook( keyword, value )
        else:
            raise TypeError("%s.%s(): Unknown keyword argument %r" % (__name__,'encode',keyword))

    unitxt = j.encode( obj )

    # Do the final Unicode encoding
    if encoding is None:
        output = unitxt
    else:
        try:
            output, nchars = cdk.encode( unitxt )
        except UnicodeEncodeError, err:
            # Re-raise as a JSONDecodeError
            e2 = sys.exc_info()
            newerr = JSONEncodeError("a Unicode encoding error occurred")
            # Simulate Python 3's: "raise X from Y" exception chaining
            newerr.__cause__ = err
            newerr.__traceback__ = e2[2]
            raise newerr

    return output


def decode( txt, strict=False, encoding=None, **kw ):
    """Decodes a JSON-encoded string into a Python object.

    Strictness:
    -----------
    If 'strict' is set to True, then those strings that are not
    absolutely strictly conforming to JSON will result in a
    JSONDecodeError exception.

    Unicode decoding:
    -----------------
    The input string can be either a python string or a python unicode
    string (or a byte array in Python 3).  If it is already a unicode
    string, then it is assumed that no character set decoding is
    required.

    However, if you pass in a non-Unicode text string (a Python 2
    'str' type or a Python 3 'bytes' or 'bytearray') then an attempt
    will be made to auto-detect and decode the character encoding.
    This will be successful if the input was encoded in any of UTF-8,
    UTF-16 (BE or LE), or UTF-32 (BE or LE), and of course plain ASCII
    works too.
    
    Note though that if you know the character encoding, then you
    should convert to a unicode string yourself, or pass it the name
    of the 'encoding' to avoid the guessing made by the auto
    detection, as with

        python_object = demjson.decode( input_bytes, encoding='utf8' )

    Optional behaviors:
    -------------------
    Optional keywords arguments must be of the form
        allow_xxxx=True/False
    or
        prevent_xxxx=True/False
    where each will allow or prevent the specific behavior, after the
    evaluation of the 'strict' argument.  For example, if strict=True
    then by also passing 'allow_comments=True' then comments will be
    allowed.  If strict=False then prevent_comments=True will allow
    everything except comments.
    
    Callback hooks:
    ---------------
    You may supply callback hooks by using the hook name as the
    named argument, such as:
        decode_float=decimal.Decimal

    See the hooks documentation on the JSON.set_hook() method.

    """
    import sys
    # Initialize the JSON object
    j = JSON( strict=strict )
    for keyword, value in kw.items():
        behavior = None
        hook = None
        if keyword in j.all_hook_names:
            j.set_hook( keyword, value )
        elif keyword.startswith('allow_'):
            behavior = keyword[6:]
            allow = bool(value)
        elif keyword.startswith('prevent_'):
            behavior = keyword[8:]
            allow = not bool(value)
        else:
            raise TypeError("%s.%s(): Unknown keyword argument %r" % (__name__,'decode',keyword))
        if behavior:
            if allow:
                j.allow(behavior)
            else:
                j.prevent(behavior)

    # Convert the input string into unicode if needed.
    if isinstance(txt,unicode):
        unitxt = txt
    else:
        # Find codec to use.  CodecInfo will be in 'cdk' and name in 'encoding'.
        if encoding is None:
            cdk = None
        elif isinstance(encoding, codecs.CodecInfo):
            cdk = encoding
            encoding = cdk.name
        else:
            cdk = helpers.lookup_codec( encoding )
            if not cdk:
                raise JSONDecodeError('no codec available for character encoding',encoding)

        # Invoke the codec to decode
        try:
            if not cdk:
                unitxt = helpers.auto_unicode_decode( txt )
            else:
                try:
                    cdk.decode( helpers.make_raw_bytes([]), errors='strict' )
                except TypeError:
                    cdk_kw = {}  # This coded doesn't like the errors argument
                else:
                    cdk_kw = {'errors': 'strict'}

                unitxt, numbytes = cdk.decode( txt, **cdk_kw )
        except UnicodeDecodeError, err:
            # Re-raise as a JSONDecodeError
            e2 = sys.exc_info()
            newerr = JSONDecodeError("a Unicode decoding error occurred")
            # Simulate Python 3's: "raise X from Y" exception chaining
            newerr.__cause__ = err
            newerr.__traceback__ = e2[2]
            raise newerr

        # Check that the decoding seems sane.  Per RFC 4627 section 3:
        #    "Since the first two characters of a JSON text will
        #    always be ASCII characters [RFC0020], ..."
        # [WAS removed from RFC 7158, but still valid via the grammar.]
        #
        # This check is probably not necessary, but it allows us to
        # raise a suitably descriptive error rather than an obscure
        # syntax error later on.
        #
        # Note that the RFC requirements of two ASCII characters seems
        # to be an incorrect statement as a JSON string literal may
        # have as it's first character any unicode character.  Thus
        # the first two characters will always be ASCII, unless the
        # first character is a quotation mark.  And in non-strict
        # mode we can also have a few other characters too.
        if len(unitxt) > 2:
            first, second = unitxt[:2]
            if first in '"\'':
                pass # second can be anything inside string literal
            else:
                if ((ord(first) < 0x20 or ord(first) > 0x7f) or \
                    (ord(second) < 0x20 or ord(second) > 0x7f)) and \
                    (not j.isws(first) and not j.isws(second)):
                    # Found non-printable ascii, must check unicode
                    # categories to see if the character is legal.
                    # Only whitespace, line and paragraph separators,
                    # and format control chars are legal here.
                    import unicodedata
                    catfirst = unicodedata.category(unicode(first))
                    catsecond = unicodedata.category(unicode(second))
                    if catfirst not in ('Zs','Zl','Zp','Cf') or \
                           catsecond not in ('Zs','Zl','Zp','Cf'):
                        raise JSONDecodeError('the decoded string is gibberish, is the encoding correct?',encoding)
    # Now ready to do the actual decoding
    obj = j.decode( unitxt )
    return obj


# ======================================================================

class jsonlint(object):
    """This class contains most of the logic for the "jsonlint" command.

    You generally create an instance of this class, to defined the
    program's environment, and then call the main() method.  A simple
    wrapper to turn this into a script might be:

        import sys, demjson
        if __name__ == '__main__':
            lint = demjson.jsonlint( sys.argv[0] )
            return lint.main( sys.argv[1:] )

    """
    _jsonlint_usage = """Usage: %(program_name)s [<options> ...] inputfile.json ...

With no input filename, or "-", it will read from standard input.

The return status will be 0 if the file is conforming JSON (per the
RFC 7158 specification), or non-zero otherwise.

OPTIONS:

 -v | --verbose    Show details of lint checking
 -q | --quiet      Don't show any warnings

 -s | --strict     Be strict in what is considered conforming JSON (the default)
 -S | --nonstrict  Be loose in what is considered conforming JSON

 -f | --format     Reformat the JSON text (if conforming) to stdout
 -F | --format-compactly
        Reformat the JSON simlar to -f, but do so compactly by
        removing all unnecessary whitespace
 -o filename | --output filename
        The filename to which reformatted JSON is to be written.
        Without this option the standard output is used.

UNICODE OPTIONS:

 -e codec | --encoding=codec     Set both input and output encodings
 --input-encoding=codec          Set the input encoding
 --output-encoding=codec         Set the output encoding

    These options set the character encoding codec (e.g., "ascii",
    "utf-8", "utf-16").  The -e will set both the input and output
    encodings to the same thing.  The output encoding is used when
    reformatting with the -f or -F options.

    Unless set, the input encoding is guessed and the output
    encoding will be "utf-8".

REFORMATTING / PRETTY-PRINTING:

    When reformatting JSON with -f or -F, output is only produced if
    the input passed validation.  By default the reformatted JSON will
    be written to standard output, unless the -o option was given.

    The default output codec is UTF-8, unless an encoding option is
    provided.  Any Unicode characters will be output as literal
    characters if the encoding permits, otherwise they will be
    \u-escaped.  You can use "--output-encoding ascii" to force all
    Unicode characters to be escaped.

MORE INFORMATION:

    Use '%(program_name)s --version [-v]' to see versioning information.
    Use '%(program_name)s --copyright' to see author and copyright details.'

    %(program_name)s is distributed as part of the "demjson" Python module.
    See %(homepage)s
"""

    def __init__(self, program_name='jsonlint', stdin=None, stdout=None, stderr=None ):
        """Create an instance of a "jsonlint" program.

        You can optionally pass options to define the program's environment:

          * program_name  - the name of the program, usually sys.argv[0]
          * stdin   - the file object to use for input, default sys.stdin
          * stdout  - the file object to use for outut, default sys.stdout
          * stderr  - the file object to use for error output, default sys.stderr

        After creating an instance, you typically call the main() method.

        """
        import os, sys
        self.program_path = program_name
        self.program_name = os.path.basename(program_name)
        if stdin:
            self.stdin = stdin
        else:
            self.stdin = sys.stdin

        if stdout:
            self.stdout = stdout
        else:
            self.stdout = sys.stdout

        if stderr:
            self.stderr = stderr
        else:
            self.stderr = sys.stderr

    @property
    def usage(self):
        """A mutlti-line string containing the program usage instructions.
        """
        return self._jsonlint_usage % {'program_name':self.program_name, 'homepage':__homepage__}

    def _lintcheck_data( self,
                        jsondata,
                        verbose_fp=None, strict=True,
                        reformat=False,
                        input_encoding=None, output_encoding=None, escape_unicode=True,
                        pfx='' ):
        global decode, encode
        success = False
        reformatted = None
        try:
            data = decode(jsondata, strict=strict, encoding=input_encoding)
        except JSONError, err:
            success = False
            if verbose_fp:
                verbose_fp.write('%s%s\n' % (pfx, err.pretty_description()) )
        except UnicodeDecodeError, err:
            success = False
            if verbose_fp:
                verbose_fp.write('%sFile is not text: %s\n' % (pfx, str(err) ))
        else:
            success = True
            if reformat == 'compactly':
                reformatted = encode(data, compactly=True, encoding=output_encoding, escape_unicode=escape_unicode)
            elif reformat:
                reformatted = encode(data, compactly=False, encoding=output_encoding, escape_unicode=escape_unicode)
        return (success, reformatted)
    
    
    def _lintcheck( self, filename, output_filename,
                   verbose=False, strict=True, reformat=False,
                   input_encoding=None, output_encoding=None, escape_unicode=True ):
        import sys
        verbose_fp = None
    
        if not filename or filename == "-":
            pfx = '<stdin>: '
            jsondata = self.stdin.read()
            if verbose:
                verbose_fp = self.stderr
        else:
            pfx = '%s: ' % filename
            try:
                fp = open( filename, 'rb' )
                jsondata = fp.read()
                fp.close()
            except IOError, err:
                self.stderr.write('%s: %s\n' % (pfx, str(err)) )
                return False
            if verbose:
                verbose_fp = self.stdout
    
        success, reformatted = self._lintcheck_data(
            jsondata,
            verbose_fp=verbose_fp,
            strict=strict,
            reformat=reformat,
            input_encoding=input_encoding, output_encoding=output_encoding,
            escape_unicode=escape_unicode,
            pfx=pfx )
        if success and reformat:
            if output_filename:
                try:
                    fp = open( output_filename, 'wb' )
                    fp.write( reformatted )
                except IOError, err:
                    self.stderr.write('%s: %s\n' % (pfx, str(err)) )
                    success = False
            else:
                self.stdout.write( reformatted )
        elif success and verbose_fp:
            verbose_fp.write('%sok\n' % pfx)
    
        return success


    def main( self, argv ):
        """The main routine for program "jsonlint".

        Should be called with sys.argv[1:] as its sole argument.

        Note sys.argv[0] which normally contains the program name
        should not be passed to main(); instead this class itself
        is initialized with sys.argv[0].

        Use "--help" for usage syntax, or consult the 'usage' member.

        """
        import sys, os, getopt, unicodedata

        success = True
        verbose = 'auto'  # one of 'auto', True, or False
        strict = True
        reformat = False
        output_filename = None
        input_encoding = None
        output_encoding = 'utf-8'
        escape_unicode = False
    
        try:
            opts, args = getopt.getopt( argv,
                                        'vqfFe:o:sS',
                                        ['verbose','quiet',
                                         'format','format-compactly',
                                         'output',
                                         'strict','nonstrict',
                                         'encoding=',
                                         'input-encoding=','output-encoding=',
                                         'help','version','copyright'] )
        except getopt.GetoptError, err:
            self.stderr.write( "Error: %s.  Use \"%s --help\" for usage information.\n" \
                                  % (err.msg, self.program_name) )
            return 1
    
        # Set verbose before looking at any other options
        for opt, val in opts:
            if opt in ('-v', '--verbose'):
                verbose=True
    
        # Process all options
        for opt, val in opts:
            if opt in ('-h', '--help'):
                self.stdout.write( self._jsonlint_usage \
                                      % {'program_name':self.program_name, 'homepage':__homepage__} )
                return 0
            elif opt == '--version':
                self.stdout.write( '%s (%s) version %s (%s)\n' \
                                      % (self.program_name, __name__, __version__, __date__) )
                if verbose == True:
                    self.stdout.write( 'demjson from %r\n' % (__file__,) )
                if verbose == True:
                    self.stdout.write( 'Python version: %s\n' % (sys.version.replace('\n',' '),) )
                    self.stdout.write( 'This python implementation supports:\n' )
                    self.stdout.write( '  * Max unicode: U+%X\n' % (sys.maxunicode,) )
                    self.stdout.write( '  * Unicode version: %s\n' % (unicodedata.unidata_version,) )
                    self.stdout.write( '  * Floating-point significant digits: %d\n' % (float_sigdigits,) )
                    self.stdout.write( '  * Floating-point max 10^exponent: %d\n' % (float_maxexp,) )
                    if str(0.0)==str(-0.0):
                        szero = 'No'
                    else:
                        szero = 'Yes'
                    self.stdout.write( '  * Floating-point has signed-zeros: %s\n' % (szero,) )
                    if decimal:
                        has_dec = 'Yes'
                    else:
                        has_dec = 'No'
                    self.stdout.write( '  * Decimal (bigfloat) support: %s\n' % (has_dec,) )
                return 0
            elif opt == '--copyright':
                self.stdout.write( "%s is distributed as part of the \"demjson\" python package.\n" \
                                      % (self.program_name,) )
                self.stdout.write( "See %s\n\n\n" % (__homepage__,) )
                self.stdout.write( __credits__ )
                return 0
            elif opt in ('-v', '--verbose'):
                verbose = True
            elif opt in ('-q', '--quiet'):
                verbose = False
            elif opt in ('-s', '--strict'):
                strict = True
            elif opt in ('-S', '--nonstrict'):
                strict = False
            elif opt in ('-f', '--format'):
                reformat = True
            elif opt in ('-F', '--format-compactly'):
                reformat = 'compactly'
            elif opt in ('-o', '--output'):
                output_filename = val
            elif opt in ('-e','--encoding'):
                input_encoding = val
                output_encoding = val
                escape_unicode = False
            elif opt in ('--output-encoding'):
                output_encoding = val
                escape_unicode = False
            elif opt in ('--input-encoding'):
                input_encoding = val
            else:
                self.stderr.write('Unknown option %r\n' % opt)
                return 1
                
        if not args:
            args = [None]
    
        for fn in args:
            if not self._lintcheck( fn, output_filename=output_filename,
                                   verbose=verbose, reformat=reformat,
                                   strict=strict,
                                   input_encoding=input_encoding,
                                   output_encoding=output_encoding,
                                   escape_unicode=escape_unicode ):
                success = False
    
        if not success:
            return 1
        return 0

# end file
