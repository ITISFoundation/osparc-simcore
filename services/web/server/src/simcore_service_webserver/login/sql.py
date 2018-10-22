from logging import getLogger


log = getLogger(__name__)
LOG_TPL = '%s <--%s'


def find_one(conn, table, filter, fields=None):
    sql, values = find_one_sql(table, filter, fields)
    log.debug(LOG_TPL, sql, values)
    return conn.fetchrow(sql, *values)


def find_one_sql(table, filter, fields=None):
    '''
    >>> find_one_sql('tbl', {'foo': 10, 'bar': 'baz'})
    ('SELECT * FROM tbl WHERE bar=$1 AND foo=$2', ['baz', 10])
    >>> find_one_sql('tbl', {'id': 10}, fields=['foo', 'bar'])
    ('SELECT foo, bar FROM tbl WHERE id=$1', [10])
    '''
    keys, values = _split_dict(filter)
    fields = ', '.join(fields) if fields else '*'
    where = _pairs(keys)
    sql = 'SELECT {} FROM {} WHERE {}'.format(fields, table, where)
    return sql, values


def insert(conn, table, data, returning='id'):
    sql, values = insert_sql(table, data, returning)
    log.debug(LOG_TPL, sql, values)
    return conn.fetchval(sql, *values)


def insert_sql(table, data, returning='id'):
    '''
    >>> insert_sql('tbl', {'foo': 'bar', 'id': 1})
    ('INSERT INTO tbl (foo, id) VALUES ($1, $2) RETURNING id', ['bar', 1])

    >>> insert_sql('tbl', {'foo': 'bar', 'id': 1}, returning=None)
    ('INSERT INTO tbl (foo, id) VALUES ($1, $2)', ['bar', 1])

    >>> insert_sql('tbl', {'foo': 'bar', 'id': 1}, returning='pk')
    ('INSERT INTO tbl (foo, id) VALUES ($1, $2) RETURNING pk', ['bar', 1])
    '''
    keys, values = _split_dict(data)
    sql = 'INSERT INTO {} ({}) VALUES ({}){}'.format(
        table,
        ', '.join(keys),
        ', '.join(_placeholders(data)),
        ' RETURNING {}'.format(returning) if returning else '')
    return sql, values


def update(conn, table, filter, updates):
    sql, values = update_sql(table, filter, updates)
    log.debug(LOG_TPL, sql, values)
    return conn.execute(sql, *values)


def update_sql(table, filter, updates):
    '''
    >>> update_sql('tbl', {'foo': 'a', 'bar': 1}, {'bar': 2, 'baz': 'b'})
    ('UPDATE tbl SET bar=$1, baz=$2 WHERE bar=$3 AND foo=$4', [2, 'b', 1, 'a'])
    '''
    where_keys, where_vals = _split_dict(filter)
    up_keys, up_vals = _split_dict(updates)
    changes = _pairs(up_keys, sep=', ')
    where = _pairs(where_keys, start=len(up_keys) + 1)
    sql = 'UPDATE {} SET {} WHERE {}'.format(
        table, changes, where)
    return sql, up_vals + where_vals


def delete(conn, table, filter):
    sql, values = delete_sql(table, filter)
    log.debug(LOG_TPL, sql, values)
    return conn.execute(sql, *values)


def delete_sql(table, filter):
    '''
    >>> delete_sql('tbl', {'foo': 10, 'bar': 'baz'})
    ('DELETE FROM tbl WHERE bar=$1 AND foo=$2', ['baz', 10])
    '''
    keys, values = _split_dict(filter)
    where = _pairs(keys)
    sql = 'DELETE FROM {} WHERE {}'.format(table, where)
    return sql, values


def _pairs(keys, *, start=1, sep=' AND '):
    '''
    >>> _pairs(['foo', 'bar', 'baz'], sep=', ')
    'foo=$1, bar=$2, baz=$3'
    >>> _pairs(['foo', 'bar', 'baz'], start=2)
    'foo=$2 AND bar=$3 AND baz=$4'
    '''
    return sep.join('{}=${}'.format(k, i) for i, k in enumerate(keys, start))


def _placeholders(variables):
    '''Returns placeholders by number of variables

    >>> _placeholders(['foo', 'bar', 1])
    ['$1', '$2', '$3']
    '''
    return ['${}'.format(i) for i, _ in enumerate(variables, 1)]


def _split_dict(dic):
    '''Split dict into sorted keys and values

    >>> _split_dict({'b': 2, 'a': 1})
    (['a', 'b'], [1, 2])
    '''
    keys = sorted(dic.keys())
    return keys, [dic[k] for k in keys]


if __name__ == "__main__":
    import doctest

    print(doctest.testmod(
        optionflags=doctest.REPORT_ONLY_FIRST_FAILURE
    ))
