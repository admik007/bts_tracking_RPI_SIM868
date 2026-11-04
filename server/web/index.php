<?php
if (empty($_GET["valid"])) $valid='';
if(isset($_GET["valid"])) $valid=$_GET["valid"];

if (empty($_GET["mnc"])) $mnc='';
if(isset($_GET["mnc"])) $mnc=$_GET["mnc"];

if (empty($_GET["today"])) $today='';
if(isset($_GET["today"])) $today=$_GET["today"];


if (empty($_GET["lasthr"])) $lasthr='';
if(isset($_GET["lasthr"])) $lasthr=$_GET["lasthr"];


if (empty($_GET["cell_id"])) $cell_id='';
if(isset($_GET["cell_id"])) $cell_id=$_GET["cell_id"];

if (empty($_GET["cid"])) $cid='';
if(isset($_GET["cid"])) $cid=$_GET["ceid"];

if (empty($_GET["cell_loadid"])) $cell_loadid='';
if(isset($_GET["cell_loadid"])) $cell_loadid=$_GET["cell_loadid"];

if (empty($_GET["zoom"])) $zoom='';
if(isset($_GET["zoom"])) $zoom=$_GET["zoom"];


if (empty($_GET["update"])) $update='';
if(isset($_GET["update"])) $update=$_GET["update"];

if (empty($_GET["delete"])) $delete='';
if(isset($_GET["delete"])) $delete=$_GET["delete"];



if (empty($_GET["year"])) $year=Date("Y");
if(isset($_GET["year"])) $year=$_GET["year"];

if (empty($_GET["month"])) $month=Date("m");
if(isset($_GET["month"])) $month=$_GET["month"];

if (empty($_GET["day"])) $day=Date("d");
if(isset($_GET["day"])) $day=$_GET["day"];

if (empty($_GET["hour"])) $hour=Date("H");
if(isset($_GET["hour"])) $hour=$_GET["hour"];

if (empty($_GET["min"])) $min=Date("S");
if(isset($_GET["min"])) $min=$_GET["min"];



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

if ($mnc != '') {
 $FILTER=" AND mnc='$mnc'";
} else {
 $FILTER="";
}


if ($valid == 'false') {
 $FILTER=$FILTER." AND address like '%no info%'";
} 
if ($valid == 'true') {
  $FILTER=$FILTER." AND technology = 'GSM' AND address not like '%no info%'";
} 
if ($valid == '') {
 $FILTER=$FILTER." AND technology = 'GSM'";
}


if ($today == 'on') {
 $FILTER=$FILTER." AND time like '".$year."-".$month."-".$day."%'";
}

if ($lasthr == 'on') {
 $FILTER=$FILTER." AND time like '".$year."-".$month."-".$day."T00%'";
}

if ($cell_loadid == 'on') {
 $FILTER=$FILTER." AND id = '".$cell_id."'";
 $lat=$entries['lat'];
 $lon=$entries['lon'];
 $zooma='11';
 if($lat == 0.000000) $lat="48.745323";
 if($lon == 0.000000) $lon="19.550171";
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

</head>
<body bgcolor="black" text="white">
<table align="center" border="1">
 <tr>
  <td align="center">
<?php
  if ($_SESSION["admin"] == "admin_ok") {
 echo $_SESSION["admin"];
}?>
 </td>
  <td align="center">
   <a href="?mnc=01"><font size="2" face="Verdana" color="Orange">=[231 01 - Orange]=</font></a>&nbsp;&nbsp;&nbsp;&nbsp;
  </td>
  <td align="center">
   <a href="?mnc=02"><font size="2" face="Verdana" color="Magenta">=[231 02 - T-Mobile]=</font></a>&nbsp;&nbsp;&nbsp;&nbsp;
  </td>
  <td align="center">
   <a href="?mnc=03"><font size="2" face="Verdana" color="Green">=[231 03 - 4KA]=</font></a>&nbsp;&nbsp;&nbsp;&nbsp;
  </td>
  <td align="center">
   <a href="?mnc=06"><font size="2" face="Verdana" color="DodgerBlue">=[231 06 - O2SK]=</font></a>
  </td>
 </tr>

<?php
  if ($_SESSION["admin"] == "admin_ok") {
?>
 <tr>
  <td align="center">No address
  </td>
  <td align="center">
   <a href="?mnc=01&valid=false"><font size="2" face="Verdana" color="Orange">=[231 01 - Orange]=</font></a>&nbsp;&nbsp;&nbsp;&nbsp;
  </td>
  <td align="center">
   <a href="?mnc=02&valid=false"><font size="2" face="Verdana" color="Magenta">=[231 02 - T-Mobile]=</font></a>&nbsp;&nbsp;&nbsp;&nbsp;
  </td>
  <td align="center">
   <a href="?mnc=03&valid=false"><font size="2" face="Verdana" color="Green">=[231 03 - 4KA]=</font></a>&nbsp;&nbsp;&nbsp;&nbsp;
  </td>
  <td align="center">
   <a href="?mnc=06&valid=false"><font size="2" face="Verdana" color="DodgerBlue">=[231 06 - O2SK]=</font></a>
  </td>
 </tr>

 <tr>
  <td align="center">Valid address
  </td>
  <td align="center">
   <a href="?mnc=01&valid=true"><font size="2" face="Verdana" color="Orange">=[231 01 - Orange]=</font></a>&nbsp;&nbsp;&nbsp;&nbsp;
  </td>
  <td align="center">
   <a href="?mnc=02&valid=true"><font size="2" face="Verdana" color="Magenta">=[231 02 - T-Mobile]=</font></a>&nbsp;&nbsp;&nbsp;&nbsp;
  </td>
  <td align="center">
   <a href="?mnc=03&valid=true"><font size="2" face="Verdana" color="Green">=[231 03 - 4KA]=</font></a>&nbsp;&nbsp;&nbsp;&nbsp;
  </td>
  <td align="center">
   <a href="?mnc=06&valid=true"><font size="2" face="Verdana" color="DodgerBlue">=[231 06 - O2SK]=</font></a>
  </td>
 </tr>

 <tr>
  <td align="center">List ALL
  </td>
  <td align="center">
   <a href="/list_all.php?mnc=01"><font size="2" face="Verdana" color="yellow">List all</font></a>
  </td>
  <td align="center">
   <a href="/list_all.php?mnc=02"><font size="2" face="Verdana" color="yellow">List all</font></a>
  </td>
  <td align="center">
   <a href="/list_all.php?mnc=03"><font size="2" face="Verdana" color="yellow">List all</font></a>
  </td>
  <td align="center">
   <a href="/list_all.php?mnc=06"><font size="2" face="Verdana" color="yellow">List all</font></a>
  </td>
 </tr>

 <tr>
  <td align="center">Cells </td>
  <td align="center">
   <form action = "?" id="cell_load1">
   <select id="cell_id" name="cell_id" form="cell_load1" onchange="document.getElementById('cell_load1').submit()">
<?php
 $tracking_bts_db = mysqli_query($spojenie,"SELECT * FROM $MySQL_table WHERE mcc = '231' AND mnc = '01' AND technology = 'GSM' order by cellid asc");
 $tracking_bts_db_row = mysqli_num_rows ($tracking_bts_db);
 echo "     <option value=\"\" selected> Total cells ".$tracking_bts_db_row."</option> \n";
 for ($i = 1; $i <= $tracking_bts_db_row; $i++) {
  $bts_entries = mysqli_fetch_array($tracking_bts_db, MYSQLI_ASSOC);
  $cid=$bts_entries["id"];
  $cell_id=$bts_entries["cellid"];
  $cell_addr=$bts_entries["address"];
  echo "     <option value=\"".$cid."\"> ".$cell_id." (".$cid.")- ".$cell_addr." </option> \n";
 } ?>
   </select>
   <input type="checkbox" id="cell_loadid" name="cell_loadid" form="cell_load1" checked hidden/>
   </form>
  </td>
  <td align="center">
   <form action = "?" id="cell_load2">
   <select id="cell_id" name="cell_id" form="cell_load2" onchange="document.getElementById('cell_load2').submit()">
<?php
 $tracking_bts_db = mysqli_query($spojenie,"SELECT * FROM $MySQL_table WHERE mcc = '231' AND mnc = '02' AND technology =  'GSM' order by cellid asc");
 $tracking_bts_db_row = mysqli_num_rows ($tracking_bts_db);
 echo "     <option value=\"\" selected> Total cells ".$tracking_bts_db_row."</option>\n";
 for ($i = 1; $i <= $tracking_bts_db_row; $i++) {
  $bts_entries = mysqli_fetch_array($tracking_bts_db, MYSQLI_ASSOC);
  $cid=$bts_entries["id"];
  $cell_id=$bts_entries["cellid"];
  $cell_addr=$bts_entries["address"];
  echo "     <option value=\"".$cid."\"> ".$cell_id." (".$cid.")- ".$cell_addr." </option>\n";
 } ?>
   </select>
   <input type="checkbox" id="cell_loadid" name="cell_loadid" form="cell_load2" checked hidden/>
   </form>
  </td>
  <td align="center">
   <form action = "?" id="cell_load3">
   <select id="cell_id" name="cell_id" form="cell_load3" onchange="document.getElementById('cell_load3').submit()">
<?php
 $tracking_bts_db = mysqli_query($spojenie,"SELECT * FROM $MySQL_table WHERE mcc = '231' AND mnc = '03' AND technology = 'GSM' order by cellid asc");
 $tracking_bts_db_row = mysqli_num_rows ($tracking_bts_db);
 echo "     <option value=\"\" selected> Total cells ".$tracking_bts_db_row."</option>\n";
 for ($i = 1; $i <= $tracking_bts_db_row; $i++) {
  $bts_entries = mysqli_fetch_array($tracking_bts_db, MYSQLI_ASSOC);
  $cid=$bts_entries["id"];
  $cell_id=$bts_entries["cellid"];
  $cell_addr=$bts_entries["address"];
  echo "     <option value=\"".$cid."\"> ".$cell_id." (".$cid.")- ".$cell_addr." </option>\n";
} ?>
   </select>
   <input type="checkbox" id="cell_loadid" name="cell_loadid" form="cell_load3" checked hidden/>
   </form>
  </td>
  <td align="center">
   <form action = "?" id="cell_load6">
   <select id="cell_id" name="cell_id" form="cell_load6" onchange="document.getElementById('cell_load6').submit()">
<?php
 $tracking_bts_db = mysqli_query($spojenie,"SELECT * FROM $MySQL_table WHERE mcc = '231' AND mnc = '06' AND technology = 'GSM' order by cellid asc");
 $tracking_bts_db_row = mysqli_num_rows ($tracking_bts_db);
 echo "     <option value=\"\" selected> Total cells ".$tracking_bts_db_row."</option>\n";
 for ($i = 1; $i <= $tracking_bts_db_row; $i++) {
  $bts_entries = mysqli_fetch_array($tracking_bts_db, MYSQLI_ASSOC);
  $cid=$bts_entries["id"];
  $cell_id=$bts_entries["cellid"];
  $cell_addr=$bts_entries["address"];
  echo "     <option value=\"".$cid."\"> ".$cell_id." (".$cid.")- ".$cell_addr." </option>\n";
} ?>
   </select>
   <input type="checkbox" id="cell_loadid" name="cell_loadid" form="cell_load6" checked hidden/>
   </form>
  </td>
 </tr>
 <tr>
  <td align="center">All others: </td>

  <td align="center" colspan="4">
   <form action = "?" id="cell_load7">
   <select id="cell_id" name="cell_id" form="cell_load7" onchange="document.getElementById('cell_load7').submit()">
<?php
 $tracking_bts_db = mysqli_query($spojenie,"SELECT * FROM $MySQL_table WHERE mcc != '231' AND technology = 'GSM' order by cellid asc");
 $tracking_bts_db_row = mysqli_num_rows ($tracking_bts_db);
 echo "     <option value=\"\" selected> Total cells ".$tracking_bts_db_row."</option>\n";
 for ($i = 1; $i <= $tracking_bts_db_row; $i++) {
  $bts_entries = mysqli_fetch_array($tracking_bts_db, MYSQLI_ASSOC);
  $cid=$bts_entries["id"];
  $cell_id=$bts_entries["cellid"];
  $cell_addr=$bts_entries["address"];
  $cell_mcc=$bts_entries["mcc"];
  $cell_mnc=$bts_entries["mnc"];

  echo "     <option value=\"".$cid."\"> ".$cell_id." (".$cid.") - ".$cell_mcc.$cell_mnc." - ".$cell_addr." </option>\n";
} ?>
   </select>
   <input type="checkbox" id="cell_loadid" name="cell_loadid" form="cell_load7" checked hidden/>
   </form>


  </td>
 </tr>
<?php } ?>

 <tr>
  <td  align="center">
<?php
  if ($_SESSION["admin"] == "admin_ok") { 
  echo $HTTP.$ip;
 }
?>
  </td>
  <td align="center">
<?php
  if ($_SESSION["admin"] == "admin_ok") { ?>
   <a href="/show_on_map.php"><font size="2" face="Verdana" color="yellow">Show on map</font></a>
<?php  }
?>
  </td>
  <td align="center">
   <font color="red"><b>Points:</b></font> <?php echo $tracking_list_db_row;?> (total) - [only GSM/2G]
  </td>
  <td align="center">
   <font color="red"><b>Screen:</b></font>
   <script type="text/javascript">
    document.write(window.innerWidth-"50"+"px x ");
    document.write(window.innerHeight-"200"+"px");
   </script>
  </td>
  <td align="center">
<?php
  if ($_SESSION["admin"] == "admin_ok") { ?>
   <a href="/list_all.php"><font size="2" face="Verdana" color="yellow">List all and update</font></a>
<?php  }
?>
  </td>
 </tr>
</table>

<?php
  if ($_SESSION["admin"] == "admin_ok") {
?>
<a align="center">
<form action="?" id="getdate">
 <select id="day" name="day" form="getdate">
  <option value="01"<?php if ($day == "01") { echo "selected"; } ?><?php if (Date("d") == "01") {echo ">>>"; } ?>> 01 <?php if (Date("d") == "01") {echo "<<<"; } ?></option>
  <option value="02"<?php if ($day == "02") { echo "selected"; } ?><?php if (Date("d") == "02") {echo ">>>"; } ?>> 02 <?php if (Date("d") == "02") {echo "<<<"; } ?></option>
  <option value="03"<?php if ($day == "03") { echo "selected"; } ?><?php if (Date("d") == "03") {echo ">>>"; } ?>> 03 <?php if (Date("d") == "03") {echo "<<<"; } ?></option>
  <option value="04"<?php if ($day == "04") { echo "selected"; } ?><?php if (Date("d") == "04") {echo ">>>"; } ?>> 04 <?php if (Date("d") == "04") {echo "<<<"; } ?></option>
  <option value="05"<?php if ($day == "05") { echo "selected"; } ?><?php if (Date("d") == "05") {echo ">>>"; } ?>> 05 <?php if (Date("d") == "05") {echo "<<<"; } ?></option>
  <option value="06"<?php if ($day == "06") { echo "selected"; } ?><?php if (Date("d") == "06") {echo ">>>"; } ?>> 06 <?php if (Date("d") == "06") {echo "<<<"; } ?></option>
  <option value="07"<?php if ($day == "07") { echo "selected"; } ?><?php if (Date("d") == "07") {echo ">>>"; } ?>> 07 <?php if (Date("d") == "07") {echo "<<<"; } ?></option>
  <option value="08"<?php if ($day == "08") { echo "selected"; } ?><?php if (Date("d") == "08") {echo ">>>"; } ?>> 08 <?php if (Date("d") == "08") {echo "<<<"; } ?></option>
  <option value="09"<?php if ($day == "09") { echo "selected"; } ?><?php if (Date("d") == "09") {echo ">>>"; } ?>> 09 <?php if (Date("d") == "09") {echo "<<<"; } ?></option>
  <option value="10"<?php if ($day == "10") { echo "selected"; } ?><?php if (Date("d") == "10") {echo ">>>"; } ?>> 10 <?php if (Date("d") == "10") {echo "<<<"; } ?></option>
  <option value="11"<?php if ($day == "11") { echo "selected"; } ?><?php if (Date("d") == "11") {echo ">>>"; } ?>> 11 <?php if (Date("d") == "11") {echo "<<<"; } ?></option>
  <option value="12"<?php if ($day == "12") { echo "selected"; } ?><?php if (Date("d") == "12") {echo ">>>"; } ?>> 12 <?php if (Date("d") == "12") {echo "<<<"; } ?></option>
  <option value="13"<?php if ($day == "13") { echo "selected"; } ?><?php if (Date("d") == "13") {echo ">>>"; } ?>> 13 <?php if (Date("d") == "13") {echo "<<<"; } ?></option>
  <option value="14"<?php if ($day == "14") { echo "selected"; } ?><?php if (Date("d") == "14") {echo ">>>"; } ?>> 14 <?php if (Date("d") == "14") {echo "<<<"; } ?></option>
  <option value="15"<?php if ($day == "15") { echo "selected"; } ?><?php if (Date("d") == "15") {echo ">>>"; } ?>> 15 <?php if (Date("d") == "15") {echo "<<<"; } ?></option>
  <option value="16"<?php if ($day == "16") { echo "selected"; } ?><?php if (Date("d") == "16") {echo ">>>"; } ?>> 16 <?php if (Date("d") == "16") {echo "<<<"; } ?></option>
  <option value="17"<?php if ($day == "17") { echo "selected"; } ?><?php if (Date("d") == "17") {echo ">>>"; } ?>> 17 <?php if (Date("d") == "17") {echo "<<<"; } ?></option>
  <option value="18"<?php if ($day == "18") { echo "selected"; } ?><?php if (Date("d") == "18") {echo ">>>"; } ?>> 18 <?php if (Date("d") == "18") {echo "<<<"; } ?></option>
  <option value="19"<?php if ($day == "19") { echo "selected"; } ?><?php if (Date("d") == "19") {echo ">>>"; } ?>> 19 <?php if (Date("d") == "19") {echo "<<<"; } ?></option>
  <option value="20"<?php if ($day == "20") { echo "selected"; } ?><?php if (Date("d") == "20") {echo ">>>"; } ?>> 20 <?php if (Date("d") == "20") {echo "<<<"; } ?></option>
  <option value="21"<?php if ($day == "21") { echo "selected"; } ?><?php if (Date("d") == "21") {echo ">>>"; } ?>> 21 <?php if (Date("d") == "21") {echo "<<<"; } ?></option>
  <option value="22"<?php if ($day == "22") { echo "selected"; } ?><?php if (Date("d") == "22") {echo ">>>"; } ?>> 22 <?php if (Date("d") == "22") {echo "<<<"; } ?></option>
  <option value="23"<?php if ($day == "23") { echo "selected"; } ?><?php if (Date("d") == "23") {echo ">>>"; } ?>> 23 <?php if (Date("d") == "23") {echo "<<<"; } ?></option>
  <option value="24"<?php if ($day == "24") { echo "selected"; } ?><?php if (Date("d") == "24") {echo ">>>"; } ?>> 24 <?php if (Date("d") == "24") {echo "<<<"; } ?></option>
  <option value="25"<?php if ($day == "25") { echo "selected"; } ?><?php if (Date("d") == "25") {echo ">>>"; } ?>> 25 <?php if (Date("d") == "25") {echo "<<<"; } ?></option>
  <option value="26"<?php if ($day == "26") { echo "selected"; } ?><?php if (Date("d") == "26") {echo ">>>"; } ?>> 26 <?php if (Date("d") == "26") {echo "<<<"; } ?></option>
  <option value="27"<?php if ($day == "27") { echo "selected"; } ?><?php if (Date("d") == "27") {echo ">>>"; } ?>> 27 <?php if (Date("d") == "27") {echo "<<<"; } ?></option>
  <option value="28"<?php if ($day == "28") { echo "selected"; } ?><?php if (Date("d") == "28") {echo ">>>"; } ?>> 28 <?php if (Date("d") == "28") {echo "<<<"; } ?></option>
  <option value="29"<?php if ($day == "29") { echo "selected"; } ?><?php if (Date("d") == "29") {echo ">>>"; } ?>> 29 <?php if (Date("d") == "29") {echo "<<<"; } ?></option>
  <option value="30"<?php if ($day == "30") { echo "selected"; } ?><?php if (Date("d") == "30") {echo ">>>"; } ?>> 30 <?php if (Date("d") == "30") {echo "<<<"; } ?></option>
  <option value="31"<?php if ($day == "31") { echo "selected"; } ?><?php if (Date("d") == "31") {echo ">>>"; } ?>> 31 <?php if (Date("d") == "31") {echo "<<<"; } ?></option>
 </select>
 <select id="month" name="month" form="getdate">
  <option value="01"<?php if ($month == "01") { echo "selected"; } ?><?php if (Date("m") == "01") {echo ">>>"; } ?>> Januar    <?php if (Date("m") == "01") {echo "<<<"; } ?></option>
  <option value="02"<?php if ($month == "02") { echo "selected"; } ?><?php if (Date("m") == "02") {echo ">>>"; } ?>> Februar   <?php if (Date("m") == "02") {echo "<<<"; } ?></option>
  <option value="03"<?php if ($month == "03") { echo "selected"; } ?><?php if (Date("m") == "03") {echo ">>>"; } ?>> Marec     <?php if (Date("m") == "03") {echo "<<<"; } ?></option>
  <option value="04"<?php if ($month == "04") { echo "selected"; } ?><?php if (Date("m") == "04") {echo ">>>"; } ?>> April     <?php if (Date("m") == "04") {echo "<<<"; } ?></option>
  <option value="05"<?php if ($month == "05") { echo "selected"; } ?><?php if (Date("m") == "05") {echo ">>>"; } ?>> Maj       <?php if (Date("m") == "05") {echo "<<<"; } ?></option>
  <option value="06"<?php if ($month == "06") { echo "selected"; } ?><?php if (Date("m") == "06") {echo ">>>"; } ?>> Jun       <?php if (Date("m") == "06") {echo "<<<"; } ?></option>
  <option value="07"<?php if ($month == "07") { echo "selected"; } ?><?php if (Date("m") == "07") {echo ">>>"; } ?>> Jul       <?php if (Date("m") == "07") {echo "<<<"; } ?></option>
  <option value="08"<?php if ($month == "08") { echo "selected"; } ?><?php if (Date("m") == "08") {echo ">>>"; } ?>> August    <?php if (Date("m") == "08") {echo "<<<"; } ?></option>
  <option value="09"<?php if ($month == "09") { echo "selected"; } ?><?php if (Date("m") == "09") {echo ">>>"; } ?>> September <?php if (Date("m") == "09") {echo "<<<"; } ?></option>
  <option value="10"<?php if ($month == "10") { echo "selected"; } ?><?php if (Date("m") == "10") {echo ">>>"; } ?>> Oktober   <?php if (Date("m") == "10") {echo "<<<"; } ?></option>
  <option value="11"<?php if ($month == "11") { echo "selected"; } ?><?php if (Date("m") == "11") {echo ">>>"; } ?>> November  <?php if (Date("m") == "11") {echo "<<<"; } ?></option>
  <option value="12"<?php if ($month == "12") { echo "selected"; } ?><?php if (Date("m") == "12") {echo ">>>"; } ?>> December  <?php if (Date("m") == "12") {echo "<<<"; } ?></option>
 </select>
 <select id="year" name="year" form="getdate">
  <option value="2026"<?php if ($year == "2026") { echo "selected"; } ?><?php if (Date("Y") == "2026") {echo ">>>"; } ?>> 2026 <?php if (Date("Y") == "2026") {echo "<<<"; } ?></option>
  <option value="2025"<?php if ($year == "2025") { echo "selected"; } ?><?php if (Date("Y") == "2025") {echo ">>>"; } ?>> 2025 <?php if (Date("Y") == "2025") {echo "<<<"; } ?></option>
  <option value="2024"<?php if ($year == "2024") { echo "selected"; } ?><?php if (Date("Y") == "2024") {echo ">>>"; } ?>> 2024 <?php if (Date("Y") == "2024") {echo "<<<"; } ?></option>
  <option value="2023"<?php if ($year == "2023") { echo "selected"; } ?><?php if (Date("Y") == "2023") {echo ">>>"; } ?>> 2023 <?php if (Date("Y") == "2023") {echo "<<<"; } ?></option>
 </select>
 <input type="checkbox" id="today" name="today" form="getdate" checked hidden/>
 <input type="submit">
 </form>
 <form action="?" id="lasthr">
 <input type="checkbox" id="lasthr" name="lasthr" form="lasthr" checked hidden/>
 <input type="submit">
 </form>
<?php } ?>

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
<?php if ($today=='on') { ?>  }).addTo(map).bindPopup(latLong[i][0],{autoClose: false, closeOnClick: false}); <?php };?>
<?php if (($today=='') AND ($lasthr!='on')) { ?>  }).addTo(map).bindPopup(latLong[i][0]); <?php };?>
<?php if (($today=='') AND ($lasthr=='on')) { ?>  }).addTo(map).bindPopup(latLong[i][0],{autoClose: false, closeOnClick: false}).openPopup(); <?php };?>
 }
<?php }?>
</script>

<?php
mysqli_close($spojenie);
?>
</body>
</html>

