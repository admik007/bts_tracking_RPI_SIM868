<?php
if (empty($_GET["valid"])) $valid='';
if(isset($_GET["valid"])) $valid=$_GET["valid"];

if (empty($_GET["mnc"])) $mnc='';
if(isset($_GET["mnc"])) $mnc=$_GET["mnc"];

if (empty($_GET["cell_id"])) $cell_id='';
if(isset($_GET["cell_id"])) $cell_id=$_GET["cell_id"];

if (empty($_GET["cid"])) $cid='';
if(isset($_GET["cid"])) $cid=$_GET["cid"];

if (empty($_GET["cell_loadid"])) $cell_loadid='';
if(isset($_GET["cell_loadid"])) $cell_loadid=$_GET["cell_loadid"];

if (empty($_GET["zoom"])) $zoom='';
if(isset($_GET["zoom"])) $zoom=$_GET["zoom"];


if (empty($_GET["update"])) $update='';
if(isset($_GET["update"])) $update=$_GET["update"];

if (empty($_GET["delete"])) $delete='';
if(isset($_GET["delete"])) $delete=$_GET["delete"];



$PORT = $_SERVER["SERVER_PORT"];
if ($PORT == '80') {
$HTTP='http://';
}
else {
$HTTP='https://';
}

$MAPA=$HTTP.'{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';




$iphome = gethostbyname('home.ztk-comp.sk');
$strba = '178.40.51.135';
$cancom = '195.135.184.250';

$ip=$_SERVER["REMOTE_ADDR"];
if (($ip == $strba) OR ($ip == '176.10.42.177') OR ($ip == '94.130.228.164') OR ($ip == '78.98.133.237') OR ($ip == '2a01:4f8:1c1c:9ce::1') OR ($ip == $iphome) OR ($ip == $cancom)){
 $_SESSION["admin"] = "admin_ok";
}


@include"_config.php";

// Only allow supported operator and location-status filters.
$mnc = in_array($mnc, ['01', '02', '03', '06'], true) ? $mnc : '';
$valid = in_array($valid, ['true', 'false'], true) ? $valid : '';
$FILTER = " AND technology = 'GSM'";
if ($mnc !== '') {
 $FILTER .= " AND mcc = '231' AND mnc = '$mnc'";
}
if ($valid === 'false') {
 $FILTER .= " AND (address IS NULL OR address = '' OR address LIKE '%no info%')";
} elseif ($valid === 'true') {
 $FILTER .= " AND address IS NOT NULL AND address <> '' AND address NOT LIKE '%no info%'";
}
if ($cell_loadid === 'on') {
 $cell_id = filter_var($cell_id, FILTER_VALIDATE_INT, ['options' => ['min_range' => 1]]) ?: 0;
}

if ($cell_loadid == 'on') {
 $FILTER=$FILTER." AND id = '".$cell_id."'";
 $lat="48.745323";
 $lon="19.550171";
 $zooma='11';
} else {
 $lat="48.745323";
 $lon="19.550171";
 $zooma='8';
}


if (($delete == 'on') and ($_SESSION["admin"] == "admin_ok")) {
 if(isset($_GET["id"])) $dbid=$_GET["id"];
# echo "DELETE FROM $MySQL_table WHERE id='$dbid';<br> \n";
 mysqli_query($spojenie,"DELETE FROM $MySQL_table WHERE id='$dbid';");
 echo "Value successfully deleted.<br>\n";
}


if (($update == 'on') and ($_SESSION["admin"] == "admin_ok")) {
 if(isset($_GET["id"])) $dbid=$_GET["id"];

 if(isset($_GET["address_new"]))  $address_new=$_GET["address_new"];

 if(isset($_GET["position_lat"])) $position_lat=$_GET["position_lat"];
 $position_lat = str_replace(' ', '', $position_lat);

 if(isset($_GET["position_lon"])) $position_lon=$_GET["position_lon"];
 $position_lon = str_replace(' ', '', $position_lon);

# echo "UPDATE $MySQL_table SET lat='$position_lat' WHERE id='$dbid';<br> \n";
# echo "UPDATE $MySQL_table SET lon='$position_lon' WHERE id='$dbid';<br> \n";
# echo "UPDATE $MySQL_table SET address='$address_new' WHERE id='$dbid';<br> \n";
 mysqli_query($spojenie,"UPDATE $MySQL_table SET lat='$position_lat' WHERE id='$dbid';");
 mysqli_query($spojenie,"UPDATE $MySQL_table SET lon='$position_lon' WHERE id='$dbid';");
 mysqli_query($spojenie,"UPDATE $MySQL_table SET address='$address_new' WHERE id='$dbid';");
 echo "New values written.<br>\n";
}

if ($_SESSION["admin"] == "admin_ok") {
 echo "<center>SELECT * FROM $MySQL_table WHERE lat NOT like '0.0%' AND lon NOT like '0.0%' AND mcc='231' $FILTER order by time DESC\n";
}



// Send compact, safely escaped data; build popup HTML only when opened.
$tracking_list_db = mysqli_query($spojenie,
 "SELECT id, lat, lon, mcc, mnc, cellid, address, alt, time FROM $MySQL_table WHERE lat NOT like '0.0%' AND lon NOT like '0.0%' $FILTER");
$map_points = [];
while ($entries = mysqli_fetch_assoc($tracking_list_db)) {
 if (!is_numeric($entries['lat']) || !is_numeric($entries['lon'])) continue;
 $point_lat = (float)$entries['lat'];
 $point_lon = (float)$entries['lon'];
 if ($point_lat == 0.0 || $point_lon == 0.0) continue;
 $map_points[] = [
  $point_lat, $point_lon,
  (string)$entries['mcc'], (string)$entries['mnc'],
  (string)$entries['cellid'], (int)$entries['id'],
  (string)($entries['address'] ?? ''), (string)($entries['alt'] ?? ''),
  (string)($entries['time'] ?? '')
 ];
 if ($cell_loadid === 'on') {
  $lat = $point_lat;
  $lon = $point_lon;
  $zooma = 17;
 }
}
$tracking_list_db_row = count($map_points);
mysqli_free_result($tracking_list_db);
$zoom = $zooma;
$map_json = json_encode($map_points, JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT | JSON_INVALID_UTF8_SUBSTITUTE);
if ($map_json === false) $map_json = '[]';

?>
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
 <title> Slovak BTS map </title>
 <meta http-equiv="Expires" CONTENT="Sun, 12 May 2003 00:36:05 GMT">
 <meta http-equiv="Pragma" CONTENT="no-cache">
 <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
 <meta http-equiv="Cache-control" content="no-cache">
 <meta http-equiv="Content-Language" content="sk">
 <meta name="google-site-verification" content="GHY_X_yeijpdBowWr_AKSMWAT8WQ-ILU-Z441AsYG9A">
 <meta name="GOOGLEBOT" CONTENT="noodp">
 <meta name="pagerank" content="10">
 <meta name="msnbot" content="robots-terms">
 <meta name="msvalidate.01" content="B786069E75B8F08919826E2B980B971A">
 <meta name="revisit-after" content="2 days">
 <meta name="robots" CONTENT="index, follow">
 <meta name="alexa" content="100">
 <meta name="distribution" content="Global">
 <meta name="keywords" lang="en" content="osm, openstreetmaps, maps, leaflet">
 <meta name="description" content="OpenStreetMaps with Leaflet in Docker">
 <meta name="Author" content="ZTK-Comp WEBHOSTING">
 <meta name="copyright" content="(c) 2019 ZTK-Comp">
 <link rel="stylesheet" href="leaflet.css">
 <script type="text/javascript" src="leaflet.js"></script>

<style>
 body { margin: 0; background: #101418; color: #e7edf3; font: 14px Arial, sans-serif; }
 .toolbar { display: flex; flex-wrap: wrap; justify-content: center; align-items: center; gap: 14px; padding: 14px 18px; background: #1b222b; border-bottom: 1px solid #374353; }
 .toolbar-group { display: flex; flex-wrap: wrap; justify-content: center; gap: 6px; width: 100%; }
 .filter-link { display: inline-block; padding: 8px 11px; border-radius: 6px; border: 1px solid #4a5869; text-decoration: none; color: #e7edf3; white-space: nowrap; }
 .filter-link:hover, .filter-link.active { background: #364559; border-color: #aebed1; }
 .orange { border-left: 4px solid orange; } .magenta { border-left: 4px solid magenta; }
 .green { border-left: 4px solid #29ad50; } .blue { border-left: 4px solid dodgerblue; }
 .operator-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; width: 100%; max-width: 1050px; }
 .operator-panel { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
 .operator-panel .filter-link { text-align: center; font-weight: 600; }
 .cell-select { width: 100%; min-width: 0; padding: 8px; border-radius: 6px; border: 1px solid #526070; background: #121920; color: #e7edf3; }
 @media (max-width: 740px) { .operator-grid { grid-template-columns: repeat(2, minmax(145px, 1fr)); } }
 @media (max-width: 370px) { .operator-grid { grid-template-columns: 1fr; } }
 #map { margin: 0 auto; }
 .render-time { position: fixed; right: 12px; bottom: 12px; z-index: 1100; padding: 6px 10px; border-radius: 6px; background: rgba(16,20,24,.88); color: #e7edf3; font-size: 12px; pointer-events: none; }
 .load-time { position: fixed; left: 12px; bottom: 12px; z-index: 1100; padding: 6px 10px; border-radius: 6px; background: rgba(16,20,24,.88); color: #e7edf3; font-size: 12px; pointer-events: none; }
</style>
</head>
<body bgcolor="black" text="white">
<div class="toolbar">
 <div class="operator-grid">
<?php
$operators = [
 ['mnc' => '01', 'name' => 'Orange', 'class' => 'orange'],
 ['mnc' => '02', 'name' => 'Telekom', 'class' => 'magenta'],
 ['mnc' => '03', 'name' => '4ka', 'class' => 'green'],
 ['mnc' => '06', 'name' => 'O2', 'class' => 'blue'],
];
foreach ($operators as $op) {
 $operator_mnc = $op['mnc'];
 $selected = $mnc === $operator_mnc;
 $href = '?' . http_build_query(array_filter(['mnc' => $operator_mnc, 'valid' => $valid]));
 $stmt = mysqli_prepare($spojenie, "SELECT id, cellid, address FROM $MySQL_table WHERE mcc = '231' AND mnc = ? AND technology = 'GSM' ORDER BY cellid ASC");
 mysqli_stmt_bind_param($stmt, 's', $operator_mnc);
 mysqli_stmt_execute($stmt);
 $cells = mysqli_stmt_get_result($stmt);
 $cell_count = mysqli_num_rows($cells);
?>
  <div class="operator-panel">
   <a class="filter-link <?php echo $op['class'] . ($selected ? ' active' : ''); ?>" href="<?php echo htmlspecialchars($href, ENT_QUOTES, 'UTF-8'); ?>"><?php echo htmlspecialchars($op['name'], ENT_QUOTES, 'UTF-8'); ?></a>
   <form method="get" action="/">
    <input type="hidden" name="mnc" value="<?php echo $operator_mnc; ?>">
    <input type="hidden" name="cell_loadid" value="on">
    <select class="cell-select" name="cell_id" aria-label="CellID <?php echo htmlspecialchars($op['name'], ENT_QUOTES, 'UTF-8'); ?>" onchange="this.form.submit()">
     <option value="" selected>Celkom buniek: <?php echo $cell_count; ?> – vybrať CellID</option>
<?php while ($cell = mysqli_fetch_assoc($cells)) {
 $description = $cell['cellid'].' ('.$cell['id'].') – '.($cell['address'] ?? '');
?>
     <option value="<?php echo (int)$cell['id']; ?>"<?php echo ($cell_loadid === 'on' && (string)$cell_id === (string)$cell['id']) ? ' selected' : ''; ?>><?php echo htmlspecialchars($description, ENT_QUOTES, 'UTF-8'); ?></option>
<?php } mysqli_stmt_close($stmt); ?>
    </select>
   </form>
  </div>
<?php } ?>
 </div>
 <div class="toolbar-group" aria-label="Filtre mapy">
  <a class="filter-link<?php echo $mnc === '' && $cell_loadid !== 'on' ? ' active' : ''; ?>" href="?">Všetci operátori</a>
  <a class="filter-link<?php echo $valid === '' ? ' active' : ''; ?>" href="?<?php echo http_build_query(array_filter(['mnc'=>$mnc])); ?>">Všetky polohy</a>
  <a class="filter-link<?php echo $valid === 'true' ? ' active' : ''; ?>" href="?<?php echo http_build_query(array_filter(['mnc'=>$mnc,'valid'=>'true'])); ?>">S adresou</a>
  <a class="filter-link<?php echo $valid === 'false' ? ' active' : ''; ?>" href="?<?php echo http_build_query(array_filter(['mnc'=>$mnc,'valid'=>'false'])); ?>">Bez adresy</a>
 </div>
</div>
<div id="load-time" class="load-time" aria-live="polite">Načítavam...</div>
<div id="render-time" class="render-time" aria-live="polite"></div>
<table id="map" width="100">
 <td id="maph" height="100" >
 </td>
</table>

<script type="text/javascript">
 document.getElementById("map").width = window.innerWidth-"50";
 document.getElementById("maph").height = window.innerHeight-"200";
</script>

<script type="text/javascript">
 map = L.map('map').setView([<?php echo $lat;?>, <?php echo $lon;?>], <?php echo $zoom;?>);
 L.tileLayer('<?php echo $MAPA;?>', { maxZoom: 18,}).addTo(map);

 var popup = L.popup();
 function onMapClick(e) {
  popup
  .setLatLng(e.latlng)
  .setContent("<span style=\"font-weight:bold;\">Your position on map</span> <br>"+"<span style=\"font-weight:bold;\">Lat:</span> "+e.latlng.lat.toFixed(6)+"<br> <span style=\"font-weight:bold;\">Lon:</span>"+e.latlng.lng.toFixed(6))
  .openOn(map);
 }
 map.on('click', onMapClick);

// Map data is JSON; keep the same colors, radius and Canvas batching.
const latLong = <?php echo $map_json; ?>;
const btsAdmin = <?php echo json_encode(($_SESSION['admin'] ?? '') === 'admin_ok'); ?>;
const operatorInfo = {
 '23101': ['Orange', 'Orange'],
 '23102': ['Telekom', 'Magenta'],
 '23103': ['4ka', 'Green'],
 '23106': ['O2', 'DodgerBlue']
};
function escapeHtml(value) {
 return String(value ?? '').replace(/[&<>"']/g, function (character) {
  return {'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[character];
 });
}
function cellPopup(point) {
 const [lat, lon, mcc, mnc, cellid, id, address, alt, time] = point;
 const code = mcc + mnc;
 const operator = operatorInfo[code]?.[0] ||
  ({'226':'Romania', '216':'Hungary', '284':'Bulgaria'}[mcc] || 'Other');
 const title = '<strong>Operator:</strong> ' + escapeHtml(code) + ' - ' + escapeHtml(operator)
  + '<br><strong>CellID:</strong> ' + escapeHtml(cellid)
  + '<br><strong>DB_ID:</strong> ' + escapeHtml(id);
 if (!btsAdmin) {
  return title + '<br><strong>Address:</strong> ' + escapeHtml(address)
   + '<br><strong>Position:</strong> ' + escapeHtml(lat) + ' / ' + escapeHtml(lon)
   + ' (' + escapeHtml(alt) + ' mnm)';
 }
 function field(name, value, size) {
  return '<input type="text" name="' + name + '" value="' + escapeHtml(value)
   + '"' + (size ? ' size="' + size + '"' : '') + '>';
 }
 return '<form method="get" action="/">'
  + title + '<br><strong>Time:</strong> ' + escapeHtml(time)
  + '<input type="hidden" name="id" value="' + encodeURIComponent(id) + '">'
  + '<input type="hidden" name="update" value="on">'
  + '<br><strong>Address:</strong> ' + field('address_new', address)
  + '<br><strong>Position:</strong> ' + field('position_lat', lat, 9)
  + ' / ' + field('position_lon', lon, 9)
  + '<br><strong>Sea level:</strong> ' + escapeHtml(alt) + ' mnm'
  + '<br><button type="submit">Ulozit</button></form>'
  + '<form method="get" action="/">'
  + '<input type="hidden" name="id" value="' + encodeURIComponent(id) + '">'
  + '<input type="hidden" name="delete" value="on">'
  + '<button type="submit">Zmazat - ' + escapeHtml(id) + '</button></form>'
  + '<a target="_blank" rel="noopener" href="https://api.geoapify.com/v1/geocode/reverse?type=street&amp;format=xml&amp;lat='
  + encodeURIComponent(lat) + '&amp;lon=' + encodeURIComponent(lon)
  + '&amp;apiKey=054b7c9fcae24adf9976f2e5b6982fa0">Get address</a> &nbsp; '
  + '<a target="_blank" rel="noopener" href="https://maps.ztk-comp.sk/?lat='
  + encodeURIComponent(lat) + '&amp;lon=' + encodeURIComponent(lon)
  + '&amp;zoom=16">OSM</a>';
}
const btsCanvas = L.canvas({padding: 0.5});
const batchSize = 350;
let nextPoint = 0;
const renderStart = performance.now();
function drawBtsBatch() {
 const end = Math.min(nextPoint + batchSize, latLong.length);
 for (; nextPoint < end; nextPoint++) {
  const point = latLong[nextPoint];
  const palette = operatorInfo[point[2] + point[3]];
  const color = palette ? palette[1] : (point[2] !== '231' ? '#A' + point[2] + point[3] : '#888888');
  const fillColor = palette ? 'Black' : (point[2] !== '231' ? '#F' + point[2] + point[3] : 'Black');
  const marker = L.circleMarker([point[0], point[1]], {
   renderer: btsCanvas,
   radius: 3,
   color: color,
   fillColor: fillColor,
   fillOpacity: 1,
   weight: 1
  }).addTo(map);
  marker.bindPopup(function () { return cellPopup(point); });
 }
 if (nextPoint < latLong.length) {
  requestAnimationFrame(drawBtsBatch);
 } else {
  const display = document.getElementById('render-time');
  if (display) display.textContent = 'Vykreslenie ' + nextPoint + ' bodov: '
   + ((performance.now() - renderStart) / 1000).toFixed(2) + ' s';
 }
}
requestAnimationFrame(drawBtsBatch);
</script>
<script>
// Measure completed navigation; navigation.duration may still be zero in the load handler.
window.addEventListener('load', function () {
 requestAnimationFrame(function () {
  const el = document.getElementById('load-time');
  if (!el) return;
  const navigation = performance.getEntriesByType?.('navigation')?.[0];
  const elapsed = navigation && navigation.loadEventEnd > 0
   ? navigation.loadEventEnd - navigation.startTime
   : performance.now();
  el.textContent = 'Načítanie stránky: ' + (elapsed / 1000).toFixed(2) + ' s';
 });
});
</script>

<?php
mysqli_close($spojenie);
?>
</body>
</html>

