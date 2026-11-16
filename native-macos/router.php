<?php
$root = getenv('DAPODIK_DOCUMENT_ROOT');
$path = rawurldecode(parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH));
$file = realpath($root . $path);
if ($file !== false && strpos($file, $root . DIRECTORY_SEPARATOR) === 0 && is_file($file)) {
    return false;
}
chdir($root);
$_SERVER['SCRIPT_FILENAME'] = $root . '/index.php';
$_SERVER['SCRIPT_NAME'] = '/index.php';
$_SERVER['PHP_SELF'] = '/index.php';
// The upstream login layout translates both forms outside narrow windows.
// Keep the original desktop layout and show both forms at narrow widths.
ob_start(function ($html) {
    if (preg_match('/\bid=["\x27]?form1\b/', $html) && preg_match('/\bid=["\x27]?form2\b/', $html)) {
        $css = '<style>@media(max-width:768px){.container.right-panel-active .container__form,.container__form{transform:none!important;opacity:1!important;position:static!important;height:auto!important;width:100%!important}.container{height:auto!important;overflow:visible!important;margin-bottom:65px}.container__overlay{display:none!important}.form{height:auto!important}}</style>';
        $html = '<title>Dapodik 2027.b</title>' . $css . $html;
    }
    return $html;
});
require $root . '/index.php';
