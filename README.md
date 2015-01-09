# OSM Map Matcher
OSM Map Matcher matches GPS coordinates to existing OSM highways. Currently it returns solely the id of the matched highways.

## Requires
* python-gdal
* psycopg2
* PostgreSQL with PostGIS and pgRouting

## Convert KML to GPX
http://www.gpsvisualizer.com/convert_input

## Create Database
```
createdb omm -U postgres;
psql -U postgres -d omm -U postgres -c "CREATE EXTENSION postgis;"
psql -U postgres -d omm -U postgres -c "CREATE EXTENSION pgrouting;"
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
