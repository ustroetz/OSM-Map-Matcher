# OSM Map Matcher
OSM Map Matcher matches GPS coordinates to existing OSM highways. Currently it returns solely the id of the matched highways.

## Requires
* python-gdal
* psycopg2
* PostgreSQL with PostGIS and pgRouting

## Convert KML to GPX
http://www.gpsvisualizer.com/convert_input

## OSM Data Preperation
### Create Database
```
createdb omm -U postgres;
psql -U postgres -d omm -U postgres -c "CREATE EXTENSION postgis;"
psql -U postgres -d omm -U postgres -c "CREATE EXTENSION pgrouting;"
```

### OSM Data Preperation
##### 1. Download OSM Metro Extracts
```
wget https://s3.amazonaws.com/metro-extracts.mapzen.com/istanbul_turkey.osm.pbf
```
##### 2. Import OSM data into DB
Enable the follwoing lines in osm2po.config:
```
postp.1.class = de.cm.osm2po.plugins.postp.PgVertexWriter
wtr.tag.highway.track =          1,  71, 10,  bike|foot
wtr.tag.highway.service =        1,  51, 5,   car|bike
```

```
java -jar osm2po-core-5.0.0-signed.jar istanbul_turkey.osm.pbf
psql -d omm -q -f osm/osm_2po_4pgr.sql
psql -d omm -q -f osm/osm_2po_vertex.sql
```
##### 3. Apply Explode lines in QGIS
##### 4. Reload into PostGIS
```
ogr2ogr -f "PostgreSQL" PG:"host=localhost user=postgres dbname=omm" -nln ways_split temp.shp
```


## Run script
```
python OSMmapMatcher.py
```
If the script exits, a GPX file is generated `osm_date-time.gpx`
1. Go to https://www.openstreetmap.org/edit
2. Drag and drop the GPX file
3. Digitize the road
4. Use `#allryder` as a commit message

Else a table with the matching OSM streets is created in the database


## Background
* first OSM segment is found by closest distance
* all further features need to connect to previously selected feature
* feature is selected based on weighted distance and bearing
