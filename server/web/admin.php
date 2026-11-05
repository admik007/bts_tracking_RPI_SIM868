<?php
declare(strict_types=1);

// Separate BTS administration. No password or credential is stored in this repository.
// Configure BTS_ADMIN_PASSWORD_HASH in the PHP/Apache environment (password_hash(...)).
ini_set('session.use_strict_mode', '1');
ini_set('session.cookie_httponly', '1');
if (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') {
    ini_set('session.cookie_secure', '1');
}
ini_set('session.cookie_samesite', 'Strict');
session_start();
header('Cache-Control: no-store, private');
header('X-Content-Type-Options: nosniff');
header('X-Frame-Options: DENY');

require __DIR__ . '/_config.php';
if (!isset($spojenie) || !($spojenie instanceof mysqli)) {
    http_response_code(500);
    exit('Database connection unavailable.');
}
if (!isset($MySQL_table) || !preg_match('/^[a-zA-Z0-9_]+$/', (string)$MySQL_table)) {
    http_response_code(500);
    exit('Invalid configured database table.');
}
$spojenie->set_charset('utf8mb4');

function esc($value): string {
    return htmlspecialchars((string)$value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}
function csrf(): string {
    if (empty($_SESSION['bts_admin_csrf'])) {
        $_SESSION['bts_admin_csrf'] = bin2hex(random_bytes(32));
    }
    return $_SESSION['bts_admin_csrf'];
}
function csrf_ok(): bool {
    return isset($_POST['csrf']) && is_string($_POST['csrf'])
        && hash_equals(csrf(), $_POST['csrf']);
}
function redirect_to(string $url): void {
    header('Location: ' . $url, true, 303);
    exit;
}
function valid_coordinate($value, float $min, float $max): ?float {
    if (!is_string($value) && !is_numeric($value)) return null;
    $value = trim((string)$value);
    if ($value === '' || !is_numeric($value)) return null;
    $number = (float)$value;
    return is_finite($number) && $number >= $min && $number <= $max ? $number : null;
}

$hash = getenv('BTS_ADMIN_PASSWORD_HASH') ?: '';
$enabled = $hash !== '';
$error = '';
$notice = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!csrf_ok()) {
        http_response_code(403);
        $error = 'Neplatný bezpečnostný token. Obnov stránku.';
    } elseif (($_POST['action'] ?? '') === 'login') {
        if ($enabled && is_string($_POST['password'] ?? null) && password_verify($_POST['password'], $hash)) {
            session_regenerate_id(true);
            $_SESSION['bts_admin_auth'] = true;
            redirect_to('/admin.php');
        }
        usleep(300000);
        $error = 'Nesprávne heslo alebo administrácia nie je nakonfigurovaná.';
    } elseif (($_POST['action'] ?? '') === 'logout') {
        unset($_SESSION['bts_admin_auth'], $_SESSION['bts_admin_csrf']);
        session_regenerate_id(true);
        redirect_to('/admin.php');
    } elseif (!empty($_SESSION['bts_admin_auth']) && ($_POST['action'] ?? '') === 'save') {
        $id = filter_var($_POST['id'] ?? null, FILTER_VALIDATE_INT, ['options'=>['min_range'=>1]]);
        $lat = valid_coordinate($_POST['lat'] ?? null, -90, 90);
        $lon = valid_coordinate($_POST['lon'] ?? null, -180, 180);
        $address = trim((string)($_POST['address'] ?? ''));
        if (!$id || $lat === null || $lon === null || ($lat == 0.0 && $lon == 0.0)
            || strlen($address) > 255) {
            $error = 'Skontroluj ID, súradnice a dĺžku adresy (max. 255 znakov).';
        } else {
            // Explicitly update only the selected BTS row; no deletion from this UI.
            $stmt = $spojenie->prepare("UPDATE $MySQL_table SET lat = ?, lon = ?, address = ? WHERE id = ? AND technology = 'GSM'");
            $stmt->bind_param('ddsi', $lat, $lon, $address, $id);
            if ($stmt->execute()) {
                $stmt->close();
                redirect_to('/admin.php?id=' . $id . '&saved=1');
            }
            $error = 'Zápis do databázy zlyhal.';
            $stmt->close();
        }
    }
}
$authenticated = $enabled && !empty($_SESSION['bts_admin_auth']);
if (!$authenticated && $error === '' && !$enabled) {
    $error = 'Administrácia nie je nakonfigurovaná. Nastav BTS_ADMIN_PASSWORD_HASH na serveri.';
}
$id = filter_var($_GET['id'] ?? null, FILTER_VALIDATE_INT, ['options'=>['min_range'=>1]]) ?: 0;
$operator = (string)($_GET['mnc'] ?? '');
if (!in_array($operator, ['', '01', '02', '03', '06'], true)) $operator = '';
$status = (string)($_GET['status'] ?? '');
if (!in_array($status, ['', 'mapped', 'unmapped'], true)) $status = '';
$search = trim((string)($_GET['q'] ?? ''));
$search = substr($search, 0, 80);
$page = max(1, min(10000, (int)($_GET['page'] ?? 1)));
$perPage = 60;
$selected = null;
$records = [];
if ($authenticated) {
    if ($id > 0) {
        $stmt = $spojenie->prepare("SELECT id, mcc, mnc, cellid, lac, lat, lon, address, alt, time FROM $MySQL_table WHERE id = ? AND technology = 'GSM' LIMIT 1");
        $stmt->bind_param('i', $id);
        $stmt->execute();
        $selected = $stmt->get_result()->fetch_assoc() ?: null;
        $stmt->close();
    }
    $where = "technology = 'GSM' AND mcc = '231'";
    if ($operator !== '') $where .= " AND mnc = '" . $operator . "'";
    if ($status === 'mapped') $where .= " AND address IS NOT NULL AND address <> '' AND address NOT LIKE '%no info%'";
    if ($status === 'unmapped') $where .= " AND (address IS NULL OR address = '' OR address LIKE '%no info%')";
    if ($search !== '') {
        $where .= " AND (CAST(cellid AS CHAR) LIKE ? OR CAST(id AS CHAR) LIKE ? OR address LIKE ?)";
        $query = '%' . $search . '%';
        $stmt = $spojenie->prepare("SELECT id, mcc, mnc, cellid, lat, lon, address FROM $MySQL_table WHERE $where ORDER BY cellid, id LIMIT ? OFFSET ?");
        $offset = ($page - 1) * $perPage;
        $stmt->bind_param('sssii', $query, $query, $query, $perPage, $offset);
    } else {
        $stmt = $spojenie->prepare("SELECT id, mcc, mnc, cellid, lat, lon, address FROM $MySQL_table WHERE $where ORDER BY cellid, id LIMIT ? OFFSET ?");
        $offset = ($page - 1) * $perPage;
        $stmt->bind_param('ii', $perPage, $offset);
    }
    $stmt->execute();
    $records = $stmt->get_result()->fetch_all(MYSQLI_ASSOC);
    $stmt->close();
}
function page_href(int $page, string $operator, string $status, string $search): string {
    return '/admin.php?' . http_build_query(array_filter(['page'=>$page, 'mnc'=>$operator, 'status'=>$status, 'q'=>$search], static fn($v)=>$v !== ''));
}
?>
<!DOCTYPE html>
<html lang="sk">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>BTS – administrácia</title>
<link rel="stylesheet" href="/leaflet.css">
<style>
* {box-sizing:border-box}
body {margin:0;background:#101418;color:#e7edf3;font:15px system-ui,Arial,sans-serif}
header {background:#1b222b;padding:14px 20px;display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap}
h1 {font-size:20px;margin:0}
h2 {font-size:18px}
a {color:#9cc9ff}
main {max-width:1250px;padding:18px;margin:auto}
.card {background:#1b222b;border:1px solid #374353;border-radius:10px;padding:16px;margin-bottom:16px}
input,select,button {font:inherit;border-radius:6px;border:1px solid #526070;padding:9px;background:#121920;color:#e7edf3;max-width:100%}
button {background:#345b84;cursor:pointer}
button:hover {background:#4475a7}
label {display:flex;flex-direction:column;gap:6px}
.filters {display:flex;gap:10px;flex-wrap:wrap;align-items:end}
.grid {display:grid;grid-template-columns:1fr 1fr;gap:16px}
table {width:100%;border-collapse:collapse}
td,th {padding:8px;border-bottom:1px solid #374353;text-align:left}
td {overflow-wrap:anywhere}
tr:hover {background:#26323f}
.error {color:#ffb4ad}
.success {color:#91e1b3}
#admin-map {height:340px;border-radius:8px;margin:12px 0}
.fields {display:grid;grid-template-columns:1fr 1fr;gap:12px}
.span2 {grid-column:span 2}
.muted {color:#abb8c5}
@media(max-width:850px){.grid{grid-template-columns:1fr}.fields{grid-template-columns:1fr}.span2{grid-column:auto}}
</style>
</head>
<body>
<header>
<h1>BTS – administrácia</h1>
<div><a href="/">Verejná mapa</a></div>
<?php if ($authenticated): ?>
<form method="post"><input type="hidden" name="csrf" value="<?= esc(csrf()) ?>"><input type="hidden" name="action" value="logout"><button type="submit">Odhlásiť</button></form>
<?php endif; ?>
</header>
<main>
<?php if ($error !== ''): ?><p class="error"><?= esc($error) ?></p><?php endif; ?>
<?php if (($_GET['saved'] ?? '') === '1' && $authenticated): ?><p class="success">Zmeny uložené.</p><?php endif; ?>
<?php if (!$authenticated): ?>
<div class="card" style="max-width:430px">
<h2>Prihlásenie</h2>
<form method="post" autocomplete="off">
<input type="hidden" name="csrf" value="<?= esc(csrf()) ?>">
<input type="hidden" name="action" value="login">
<label>Admin heslo <input type="password" name="password" required autocomplete="current-password"></label>
<p><button type="submit">Prihlásiť</button></p>
</form></div>
<?php else: ?>
<div class="card">
<form class="filters" method="get" action="/admin.php">
<label>Operátor <select name="mnc">
<option value="">Všetci</option>
<?php foreach (['01'=>'Orange','02'=>'Telekom','03'=>'4ka','06'=>'O2'] as $key=>$name): ?>
<option value="<?= $key ?>" <?= $operator===$key ? 'selected' : '' ?>><?= esc($name) ?></option>
<?php endforeach; ?>
</select></label>
<label>Poloha <select name="status">
<option value="">Všetky</option>
<option value="mapped" <?= $status==='mapped'?'selected':'' ?>>S adresou</option>
<option value="unmapped" <?= $status==='unmapped'?'selected':'' ?>>Bez adresy</option>
</select></label>
<label>CellID / ID / adresa <input name="q" value="<?= esc($search) ?>" placeholder="Hľadať"></label>
<button type="submit">Filtrovať</button>
</form>
</div>
<div class="grid">
<section class="card">
<h2>Zoznam BTS</h2>
<div style="overflow-x:auto">
<table><thead><tr><th>Operátor</th><th>CellID</th><th>Adresa</th><th></th></tr></thead><tbody>
<?php foreach ($records as $record): ?>
<tr><td><?= esc($record['mcc'].$record['mnc']) ?></td>
<td><?= esc($record['cellid']) ?></td>
<td><?= esc($record['address'] ?: 'Bez adresy') ?></td>
<td><a href="/admin.php?<?= esc(http_build_query(array_filter(['id'=>$record['id'],'mnc'=>$operator,'status'=>$status,'q'=>$search],static fn($v)=>$v!==''))) ?>">Upraviť</a></td></tr>
<?php endforeach; ?>
</tbody></table>
</div>
<p class="muted">Strana <?= $page ?> · max. <?= $perPage ?> záznamov</p>
<nav>
<?php if ($page > 1): ?><a href="<?= esc(page_href($page-1,$operator,$status,$search)) ?>">Predchádzajúca</a> &nbsp;<?php endif; ?>
<?php if (count($records) === $perPage): ?><a href="<?= esc(page_href($page+1,$operator,$status,$search)) ?>">Ďalšia</a><?php endif; ?>
</nav></section>
<section class="card">
<h2><?= $selected ? 'Upraviť BTS '.esc($selected['cellid']) : 'Výber BTS' ?></h2>
<?php if (!$selected): ?>
<p class="muted">Vyber BTS zo zoznamu, potom uprav adresu a polohu. Zmena sa uloží až po stlačení Uložiť.</p>
<?php else: ?>
<p class="muted">ID <?= esc($selected['id']) ?> · <?= esc($selected['mcc'].$selected['mnc']) ?> · LAC <?= esc($selected['lac'] ?? '') ?> · <?= esc($selected['time'] ?? '') ?></p>
<div id="admin-map"></div>
<p class="muted">Marker môžeš presunúť na mape alebo zadať súradnice ručne.</p>
<form method="post" action="/admin.php?id=<?= (int)$selected['id'] ?>">
<input type="hidden" name="csrf" value="<?= esc(csrf()) ?>">
<input type="hidden" name="action" value="save">
<input type="hidden" name="id" value="<?= (int)$selected['id'] ?>">
<div class="fields">
<label>Latitude <input id="edit-lat" name="lat" required value="<?= esc($selected['lat']) ?>"></label>
<label>Longitude <input id="edit-lon" name="lon" required value="<?= esc($selected['lon']) ?>"></label>
<label class="span2">Adresa <input name="address" maxlength="255" value="<?= esc($selected['address'] ?? '') ?>"></label>
</div>
<p class="muted">Za zameranú považujeme BTS s adresou (okrem „no info“). Bez adresy zostáva orientačná.</p>
<button type="submit">Uložiť zmeny</button>
</form>
<script src="/leaflet.js"></script>
<script>
(function () {
 const lat = <?= json_encode((float)$selected['lat']) ?>;
 const lon = <?= json_encode((float)$selected['lon']) ?>;
 if (!Number.isFinite(lat) || !Number.isFinite(lon) || lat === 0 || lon === 0) return;
 const map = L.map('admin-map').setView([lat, lon], 16);
 L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom:18, attribution:'&copy; OpenStreetMap contributors'}).addTo(map);
 const marker = L.marker([lat,lon], {draggable:true}).addTo(map);
 const latField=document.getElementById('edit-lat'), lonField=document.getElementById('edit-lon');
 marker.on('dragend',()=>{const p=marker.getLatLng();latField.value=p.lat.toFixed(7);lonField.value=p.lng.toFixed(7);});
 function updateMarker(){
  const a=Number(latField.value), b=Number(lonField.value);
  if(Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a)<=90&&Math.abs(b)<=180){marker.setLatLng([a,b]);map.panTo([a,b]);}
 }
 latField.addEventListener('change',updateMarker);
 lonField.addEventListener('change',updateMarker);
})();
</script>
<?php endif; ?>
</section>
</div>
<?php endif; ?>
</main>
</body>
</html>
