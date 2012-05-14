import sys

_format_funcs = {None: lambda format_, val: str(val)}
MAX_LINES = 25
MAX_WIDTH = 80


def _get_pprint_size(max_lines=None, max_width=None):
    """Get the output size (number of lines and character width) for Column and
    Table pformat/pprint methods.

    If no value of ``max_lines`` is supplied then the height of the screen
    terminal is used to set ``max_lines``.  If the terminal height cannot be
    determined then a default of ``astropy.table.pprint.MAX_LINES`` is used.
    If a negative value of ``max_lines`` is supplied then there is no line
    limit applied.

    The Same applies for max_width except the default is
    ``astropy.table.pprint.MAX_WIDTH``.

    Parameters
    ----------
    max_lines : int or None
        Maximum lines of output (header + data rows)

    max_width : int or None
        Maximum width (characters) output

    Returns
    -------
    max_lines, max_width : int

    """
    if max_lines is None or max_width is None:
        try:  # Will likely fail on Windows
            import termios
            import fcntl
            import struct
            s = struct.pack("HHHH", 0, 0, 0, 0)
            fd_stdout = sys.stdout.fileno()
            x = fcntl.ioctl(fd_stdout, termios.TIOCGWINSZ, s)
            (lines, width, xpixels, ypixels) = struct.unpack("HHHH", x)
            if lines > 12:
                lines -= 6
            if width > 10:
                width -= 1
        except:
            lines, width = MAX_LINES, MAX_WIDTH

    if max_lines is None:
        max_lines = lines
    elif max_lines < 0:
        max_lines = sys.maxint
    if max_lines < 6:
        max_lines = 6

    if max_width is None:
        max_width = width
    elif max_width < 0:
        max_width = sys.maxint
    if max_width < 10:
        max_width = 10

    return max_lines, max_width


def _auto_format_func(format_, val):
    """Format ``val`` according to ``format_`` for both old- and new-
    style format specifications.  More importantly, determine and cache
    (in _format_funcs) a function that will do this subsequently.  In
    this way this complicated logic is only done for the first value.

    Returns the formatted value.
    """
    try:
        # Convert val to Python object with tolist().  See
        # https://github.com/astropy/astropy/issues/148#issuecomment-3930809
        out = format_.format(val.tolist())
        # Require that the format statement actually did something
        if out == format_:
            raise ValueError
        format_func = lambda format_, val: format_.format(val.tolist())
    except:  # Not sure what exceptions might be raised
        try:
            out = format_ % val
            if out == format_:
                raise ValueError
            format_func = lambda format_, val: format_ % val
        except:
            raise ValueError('Unable to parse format string {0}'
                             .format(format_))
    _format_funcs[format_] = format_func
    return out


def _pformat_col(col, max_lines=None, show_name=True, show_units=False):
    """Return a list of formatted string representation of column values.

    Parameters
    ----------
    max_lines : int
        Maximum lines of output (header + data rows)

    show_name : bool
        Include column name (default=True)

    show_units : bool
        Include a header row for units (default=False)

    Returns
    -------
    out : list
        List of formatted column values

    """
    max_lines, _ = _get_pprint_size(max_lines, -1)

    multidims = col.shape[1:]
    if multidims:
        multidim0 = tuple(0 for n in multidims)
        multidim1 = tuple(n - 1 for n in multidims)

    col_strs = []  # List of formatted column values
    i_dashes = None
    i_centers = []  # Line indexes where content should be centered
    if show_name:
        i_centers.append(len(col_strs))
        if multidims:
            col_name = col.name + ' [{}]'.format(
                ','.join(str(n) for n in multidims))
        else:
            col_name = col.name
        col_strs.append(col_name)
        max_lines -= 1
    if show_units:
        i_centers.append(len(col_strs))
        col_strs.append(col.units or '')
        max_lines -= 1
    if show_units or show_name:
        i_dashes = len(col_strs)
        col_strs.append('---')
        max_lines -= 1

    n_print2 = max_lines // 2
    n_rows = len(col)

    format_func = _format_funcs.get(col.format, _auto_format_func)
    if len(col) > max_lines:
        i0 = n_print2
        i1 = n_rows - n_print2 - max_lines % 2
    else:
        i0 = len(col)
        i1 = 0

    # Add formatted values if within bounds allowed by max_lines
    for i in xrange(n_rows):
        if i < i0 or i > i1:
            if multidims:
                col_str = (format_func(col.format, col[(i,) + multidim0]) +
                           ' .. ' +
                           format_func(col.format, col[(i,) + multidim1]))
            else:
                col_str = format_func(col.format, col[i])
            col_strs.append(col_str)
        elif i == i0:
            col_strs.append('...')

    col_width = max(len(x) for x in col_strs)

    # Center line content and generate dashed headerline
    for i in i_centers:
        col_strs[i] = col_strs[i].center(col_width)
    if i_dashes is not None:
        col_strs[i_dashes] = '-' * col_width

    # Now bring all the column string values to the same fixed width
    for i, col_str in enumerate(col_strs):
        col_strs[i] = col_str.rjust(col_width)

    return col_strs


def _pformat_table(table, max_lines=None, max_width=None, show_name=True,
                   show_units=False):
    """Return a list of lines for the formatted string representation of
    the table.

    Parameters
    ----------
    max_lines : int or None
        Maximum number of rows to output

    max_width : int or None
        Maximum character width of output

    show_name : bool
        Include a header row for column names (default=True)

    show_units : bool
        Include a header row for units (default=False)

    Returns
    -------
    out : str
        Formatted table as a single string

    """
    # "Print" all the values into temporary lists by column for subsequent
    # use and to determine the width
    max_lines, max_width = _get_pprint_size(max_lines, max_width)
    cols = [_pformat_col(col, max_lines, show_name, show_units)
            for col in table.columns.values()]

    if not cols:
        return []

    n_rows = len(cols[0])
    outwidth = lambda cols: sum(len(c[0]) for c in cols) + len(cols) - 1
    dots_col = ['...'] * n_rows
    middle = len(cols) // 2
    while outwidth(cols) > max_width:
        if len(cols) == 1:
            break
        if len(cols) == 2:
            cols[1] = dots_col
            break
        if cols[middle] is dots_col:
            cols.pop(middle)
            middle = len(cols) // 2
        cols[middle] = dots_col

    # Now "print" the (already-stringified) column values into a
    # row-oriented list.
    rows = []
    for i in range(n_rows):
        row = ' '.join(col[i] for col in cols)
        rows.append(row)

    return rows
