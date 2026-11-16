#!/usr/bin/env python3
"""Build PHP 7.2.34's bundled ZipArchive extension without global changes."""
from pathlib import Path
import re
import subprocess

workspace = Path(__file__).resolve().parents[1]
runtime = workspace / 'native-runtime'
prefix = runtime / 'root/opt/local'
source = runtime / 'src/php-7.2.34/ext/zip'
headers = prefix / 'include/php72/php'
output = prefix / 'lib/php72/extensions/no-debug-non-zts-20170718/zip.so'
build = runtime / 'build-zip'
build.mkdir(exist_ok=True)

# Use precisely the bundled-libzip source list selected by official config.m4.
config = (source / 'config.m4').read_text()
bundled = config.split('PHP_ZIP_SOURCES="', 1)[1].split('"', 1)[0]
members = re.findall(r'lib/[A-Za-z0-9_-]+\.c', bundled)
sources = [source / name for name in ['php_zip.c', 'zip_stream.c', *members]]
includes = [headers, headers/'main', headers/'Zend', headers/'TSRM',
            headers/'ext', source, source/'lib', prefix/'include']
defines = ['HAVE_ZIP=1', 'COMPILE_DL_ZIP=1',
           'ZEND_ENABLE_STATIC_TSRMLS_CACHE=1', 'HAVE_STDBOOL_H=1',
           'SIZEOF_OFF_T=8', 'SIZEOF_SIZE_T=8']
command = ['/usr/bin/clang', '-bundle', '-undefined', 'dynamic_lookup',
           '-O2', '-std=gnu99', '-Wno-deprecated-declarations',
           '-Wno-implicit-function-declaration']
command += ['-I' + str(p) for p in includes]
command += ['-D' + value for value in defines]
command += [str(p) for p in sources]
command += ['-lz', '-o', str(output)]
subprocess.run(command, check=True)
print(f'Built {output} from {len(sources)} PHP/bundled-libzip source files')
