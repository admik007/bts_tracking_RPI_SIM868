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



#$tracking_list_db = mysqli_query($spojenie,"SELECT * FROM $MySQL_table WHERE mcc='231' $FILTER order by time DESC ");
#$tracking_list_db = mysqli_query($spojenie,"SELECT * FROM $MySQL_table WHERE lat NOT like '0.0%' AND lon NOT like '0.0%' AND mcc='231' $FILTER order by time DESC ");
$tracking_list_db = mysqli_query($spojenie,"SELECT * FROM $MySQL_table WHERE lat NOT like '0.0%' AND lon NOT like '0.0%' $FILTER order by time DESC ");
$tracking_list_db_row = mysqli_num_rows ($tracking_list_db);
$marker='var latLong = [
';

for ($i = 0; $i <= $tracking_list_db_row; $i++) {
 $entries = mysqli_fetch_array ($tracking_list_db, MYSQLI_ASSOC);
 if ((!empty($entries['lat'])) && (!empty($entries['lon']))) {
  $GET_LAT=substr($entries['lat'], 0, 6);
  $GET_LON=substr($entries['lon'], 0, 6);

  if ($cell_loadid == 'on') {
   $lat=$entries['lat'];
   $lon=$entries['lon'];
   $zooma='17';
  } else {
   $lat="48.745323";
   $lon="19.550171";
   $zooma='8';
  }



  if ($entries['mcc'].$entries['mnc'] == '23101') {
   $color="Orange";
   $colorfill="Black";
   $operator="Orange";
  }

  if ($entries['mcc'].$entries['mnc'] == '23102') {
   $color="Magenta";
   $colorfill="Black";
   $operator="Telekom";
  }

  if ($entries['mcc'].$entries['mnc'] == '23103') {
   $color="Green";
   $colorfill="Black";
   $operator="4ka";
  }

  if ($entries['mcc'].$entries['mnc'] == '23106') {
   $color="DodgerBlue";
   $colorfill="Black";
   $operator="O2";
  }

  if ($entries['mcc'] != '231') {
   $color="#A".$entries['mcc'].$entries['mnc'];
   $colorfill="#F".$entries['mcc'].$entries['mnc'];

   switch ($entries['mcc']) {
    case "226":
     $operator="Romania";
     break;

    case "216":
     $operator="Hungary";
     break;

    case "284":
     $operator="Bulgaria";
     break;

   }

  }

  $markerA='OK';
  $dbid=$entries['id'];

  if ($_SESSION["admin"] == "admin_ok") {
   $position_lat='';
   $position_lon='';
   $address_new='';

   $marker=$marker.' ["<form action=\"/?address='.$address_new.'&position_lat='.$position_lat.'&position_lon='.$position_lon.'&dbid='.$dbid.'\" > <span style=\"font-weight:bold;\">Operator:</span> '.$entries['mcc'].$entries['mnc'].' - '.$operator.'<br> <span style=\"font-weight:bold;\">CellID:</span> >>> '.$entries['cellid'].' <<<<br> <span style=\"font-weight:bold;\">DB_ID:</span> '.$entries['id'].'<br> <span style=\"font-weight:bold;\">Time:</span> '.$entries['time'].' <input type=\"text\" name=\"id\" value=\"'.$entries['id'].'\" hidden > <br> <span style=\"font-weight:bold;\">Address:</span> &nbsp;<input type=\"text\" name=\"address_new\" value=\"'.$entries['address'].'\"><br> <span style=\"font-weight:bold;\">Position:</span> &nbsp;<input type=\"text\" size=\"5\" name=\"position_lat\" value=\"'.$entries['lat'].'\"> / <input type=\"text\" size=\"5\" name=\"position_lon\" value=\"'.$entries['lon'].'\"><br> <span style=\"font-weight:bold;\">Sea level:</span> <input type=\"text\" size=\"5\" name=\"alt\" value=\"'.$entries['alt'].'\"> mnm <br> <center><input type=\"checkbox\" id=\"update\" name=\"update\" checked hidden/> <input type=\"submit\" value=\"Ulozit\"> </form> <p><form action=\"/?dbid='.$dbid.'\"> <input type=\"text\" name=\"id\" value=\"'.$entries['id'].'\" hidden > <input type=\"checkbox\" id=\"delete\" name=\"delete\" checked hidden/> <input type=\"submit\" value=\"Zmazat - '.$dbid.'\"> </form> <a href=\"https://api.geoapify.com/v1/geocode/reverse?type=street&format=xml&lat='.$entries['lat'].'&lon='.$entries['lon'].'&apiKey=054b7c9fcae24adf9976f2e5b6982fa0\" target=\"_blank\"> Get address </a> &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; <a href=\"http://maps.ztk-comp.sk/?lat='.$entries['lat'].'&lon='.$entries['lon'].'&zoom=16\" target=\"_blank\">OSM</a>    ",'.$entries['lat'].','.$entries['lon'].',"'.$color.'","'.$colorfill.'"],
';
  } else {
   $marker=$marker.' ["<span style=\"font-weight:bold;\">Operator:</span> '.$entries['mcc'].$entries['mnc'].' - '.$operator.'<br> <span style=\"font-weight:bold;\">CellID:</span> '.$entries['cellid'].'<br> <span style=\"font-weight:bold;\">DB_ID:</span> '.$entries['id'].'<br> <span style=\"font-weight:bold;\">Address:</span> '.$entries['address'].'<br> <span style=\"font-weight:bold;\">Position:</span> '.$entries['lat'].' / '.$entries['lon'].' ('.$entries['alt'].'mnm) <br>   <center> ",'.$entries['lat'].','.$entries['lon'].',"'.$color.'","'.$colorfill.'"],
';
  }
 }
}

$zoom=$zooma;
$marker=$marker.'
];
';


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
 .brand { font-size: 18px; margin-right: 10px; }
 .toolbar-group { display: flex; flex-wrap: wrap; gap: 6px; }
 .filter-link { display: inline-block; padding: 8px 11px; border-radius: 6px; border: 1px solid #4a5869; text-decoration: none; color: #e7edf3; white-space: nowrap; }
 .filter-link:hover, .filter-link.active { background: #364559; border-color: #aebed1; }
 .orange { border-left: 4px solid orange; } .magenta { border-left: 4px solid magenta; }
 .green { border-left: 4px solid #29ad50; } .blue { border-left: 4px solid dodgerblue; }
 .operator-grid { display: grid; grid-template-columns: repeat(4, minmax(165px, 1fr)); gap: 10px; width: 100%; max-width: 1050px; }
 .operator-panel { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
 .operator-panel .filter-link { text-align: center; font-weight: 600; }
 .cell-select { width: 100%; min-width: 0; padding: 8px; border-radius: 6px; border: 1px solid #526070; background: #121920; color: #e7edf3; }
 .status-line { display: flex; justify-content: center; align-items: center; gap: 18px; flex-wrap: wrap; padding: 8px; }
 @media (max-width: 740px) { .operator-grid { grid-template-columns: repeat(2, minmax(145px, 1fr)); } }
 @media (max-width: 370px) { .operator-grid { grid-template-columns: 1fr; } }
 #map { margin: 0 auto; }
 @media (max-width: 700px) { .toolbar { justify-content: flex-start; } .brand { flex-basis: 100%; } }
</style>
</head>
<body bgcolor="black" text="white">
<div class="toolbar">
 <strong class="brand">BTS Tracking</strong>
 <a class="filter-link<?php echo $mnc === '' && $cell_loadid !== 'on' ? ' active' : ''; ?>" href="?">Všetci operátori</a>
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
 <div class="toolbar-group" aria-label="Presnosť polohy">
  <a class="filter-link<?php echo $valid === '' ? ' active' : ''; ?>" href="?<?php echo http_build_query(array_filter(['mnc'=>$mnc])); ?>">Všetky polohy</a>
  <a class="filter-link<?php echo $valid === 'true' ? ' active' : ''; ?>" href="?<?php echo http_build_query(array_filter(['mnc'=>$mnc,'valid'=>'true'])); ?>">S adresou</a>
  <a class="filter-link<?php echo $valid === 'false' ? ' active' : ''; ?>" href="?<?php echo http_build_query(array_filter(['mnc'=>$mnc,'valid'=>'false'])); ?>">Bez adresy</a>
 </div>
</div>
<div class="status-line">
 <span><strong>Body:</strong> <?php echo (int)$tracking_list_db_row; ?> (GSM/2G)</span>
<?php if (($_SESSION["admin"] ?? '') === 'admin_ok') { ?>
 <a href="/show_on_map.php">Show on map</a>
 <a href="/list_all.php">List all and update</a>
<?php } ?>
</div>

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

<?php
if ($markerA == 'OK'){ 
echo $marker;

?>

 for (var i = 0; i < latLong.length; i++) {
  marker = new L.circle([latLong[i][1],latLong[i][2]], 5, {
   color: latLong[i][3],
   fillColor: latLong[i][4],
   fillOpacity: 1,
   radius: 1
  }).addTo(map).bindPopup(latLong[i][0]);
 }
<?php }?>
</script>

<?php
mysqli_close($spojenie);
?>
</body>
</html>

