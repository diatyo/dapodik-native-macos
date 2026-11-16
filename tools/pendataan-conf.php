<?php
// Native connection adapter; keep the upstream class map and application code.
$root = __DIR__;
while (!is_dir($root . '/webserver/modules')) {
    $parent = dirname($root);
    if ($parent === $root) throw new RuntimeException('Dapodik root missing.');
    $root = $parent;
}
$native = require __DIR__ . '/pendataan-conf.upstream.php';
foreach ($native['datasources'] as $name => &$source) {
    if (!is_array($source) || !isset($source['connection']['dsn'])) continue;
    $dsn = $source['connection']['dsn'];
    $database = $name === 'dapodik_app' ? 'dapodik_app' : 'pendataan';
    $dsn = preg_replace('/host=[^;]*/', 'host=127.0.0.1', $dsn);
    $dsn = preg_replace('/port=[^;]*/', 'port=54532', $dsn);
    $dsn = preg_replace('/dbname=[^;]*/', 'dbname=' . $database, $dsn);
    $source['connection']['dsn'] = $dsn;
}
unset($source);
return $native;
