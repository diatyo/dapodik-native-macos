#!/usr/bin/env python3
"""Build PHP 7.2's two PostgreSQL modules against the isolated native runtimes."""
import pathlib
import re
import subprocess

base = pathlib.Path(__file__).resolve().parents[1] / 'native-runtime'
prefix = base / 'root/opt/local'
src = base / 'src/php-7.2.34/ext'
php = prefix / 'include/php72/php'
out = base / 'extensions'
out.mkdir(exist_ok=True)
pq = prefix / 'lib/postgresql92/libpq.5.dylib'
symbols = subprocess.check_output(['/usr/bin/nm', '-gU', str(pq)], text=True)
for name in ['pgsql', 'pdo_pgsql']:
    defs = ['HAVE_%s=1' % name.upper(), 'COMPILE_DL_%s=1' % name.upper(), 'ZEND_ENABLE_STATIC_TSRMLS_CACHE=1', 'HAVE_PG_CONFIG_H=1']
    config = (src / name / 'config.m4').read_text()
    for symbol, macro in re.findall(r'AC_CHECK_LIB\(pq,\s*(\w+),\s*AC_DEFINE\((\w+)', config):
        if re.search(r'\b_' + re.escape(symbol) + r'\b', symbols):
            defs.append(macro + '=1')
    includes = [php, php/'main', php/'Zend', php/'TSRM', php/'ext', prefix/'include', prefix/'include/postgresql92']
    sources = [src/name/'pgsql.c'] if name == 'pgsql' else [src/name/f for f in ['pdo_pgsql.c', 'pgsql_driver.c', 'pgsql_statement.c']]
    if name == 'pgsql':
        compat_pgsql = out / 'pgsql_compat.c'
        diagnostic = '''pgsql = dapodik_native_connect(connstring);
                if (getenv("DAPODIK_NATIVE_DB_DIAGNOSTICS")) {
                    fprintf(stderr, "Native pgsql host=%s port=%s database=%s status=%d: %s\\n", PQhost(pgsql), PQport(pgsql), PQdb(pgsql), PQstatus(pgsql), PQerrorMessage(pgsql));
                }'''
        compat_pgsql.write_text(sources[0].read_text().replace('pgsql = PQconnectdb(connstring);', diagnostic))
        sources[0] = compat_pgsql
    if name == 'pdo_pgsql':
        # The installed PDO headers use size_t for column byte lengths.
        original = sources[-1].read_text()
        compat = out / 'pgsql_statement_compat.c'
        compat.write_text(original.replace('zend_ulong *len', 'size_t *len'))
        sources[-1] = compat
        driver = out / 'pgsql_driver_compat.c'
        diagnostic = '''H->server = dapodik_native_connect(conn_str);
    if (getenv("DAPODIK_NATIVE_DB_DIAGNOSTICS")) {
        fprintf(stderr, "Native PostgreSQL host=%s port=%s database=%s status=%d: %s\\n", PQhost(H->server), PQport(H->server), PQdb(H->server), PQstatus(H->server), PQerrorMessage(H->server));
    }'''
        driver.write_text(sources[1].read_text().replace('H->server = PQconnectdb(conn_str);', diagnostic))
        sources[1] = driver
    cmd = ['/usr/bin/clang', '-bundle', '-undefined', 'dynamic_lookup', '-O2', '-Wno-deprecated-declarations', '-Wno-implicit-function-declaration']
    cmd += ['-I' + str(p) for p in includes + [src/name]] + ['-D' + d for d in defs]
    cmd += ['-include', str(pathlib.Path(__file__).with_name('native_pg_connection.h'))]
    cmd += [str(p) for p in sources] + [str(pq), '-o', str(out/(name+'.so'))]
    subprocess.run(cmd, check=True)
    print('Built', name, flush=True)
