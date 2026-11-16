#!/usr/bin/env python3
"""Adapt only readable Windows filesystem/archiver glue in the native copy."""
from pathlib import Path
import sys

base = Path(sys.argv[1])
native_discovery = '''function get_prefill_path($prefill_name) {
    $root = getenv('DAPODIK_PREFILL_DIR');
    if (!$root || !is_dir($root) || basename($prefill_name) !== $prefill_name) return 51;
    $root = realpath($root);
    $iterator = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($root, FilesystemIterator::SKIP_DOTS));
    foreach ($iterator as $file) {
        if (!$file->isFile() || $file->isLink() || $file->getFilename() !== $prefill_name) continue;
        $path = $file->getRealPath();
        if (strpos($path, $root . DIRECTORY_SEPARATOR) === 0) return $path;
    }
    return 51;
}
'''
for name in ['push_prefill.php','push_prefill_rapor.php']:
    p=base/'prefill'/name
    s=p.read_text()
    start=s.index('function get_prefill_path(')
    if s[start:].count('function ') != 1: raise RuntimeError('Unexpected prefill layout')
    s=s[:start]+native_discovery
    lines=s.splitlines()
    replaced=False
    for i,line in enumerate(lines):
        if '$cmd =' in line and '7za.exe' in line:
            lines[i]="\t$cmd = escapeshellarg(getenv('DAPODIK_NATIVE_7ZA')) . ' e ' . escapeshellarg((string)$getPrefillPath) . ' ' . escapeshellarg('-p' . $pass) . ' -so > ' . escapeshellarg($path . '/data.txt');"
            replaced=True
        if '$f = $path.' in line and 'data.txt' in line:
            lines[i]="\t$f = $path . '/data.txt';"
    if not replaced: raise RuntimeError('Archiver call was not found')
    s='\n'.join(lines)+'\n'
    s=s.replace('system($cmd);', "system($cmd, $native_archive_status);\n\tif ($native_archive_status !== 0) { error_log('Native prefill extraction failed.'); return 51; }")
    s=s.replace("$conf['appid']", "(isset($conf['AppId']) ? $conf['AppId'] : $conf['appid'])")
    p.write_text(s)
p=base/'sinkronisasi.php';s=p.read_text();s=s.replace("$path_7za = str_replace('config', '', $path) . 'php/7za.exe';", "$path_7za = getenv('DAPODIK_NATIVE_7ZA');");p.write_text(s)
p=base/'core/SyncLogger.php';s=p.read_text();s=s.replace('glob("c:/prefill_dapodik/*.*")', "glob(rtrim(getenv('DAPODIK_PREFILL_DIR'), '/') . '/*.prf')");p.write_text(s)
print('Native prefill paths and archiver calls prepared.')
