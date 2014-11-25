# Requires
* python-gdal

# Data Preperation
1. import GPS track
```
ogr2ogr -f "PostgreSQL" PG:"host=localhost user=ustroetz dbname=test" sample.geojson
```

2. buffer GPS track
```
CREATE TABLE bufferGPS AS SELECT ogc_fid, ST_Transform(ST_Buffer(wkb_geometry,10),4326) FROM ogrgeojson
```

3. intersect GPS buffer with roads
```
CREATE TABLE extractISTANBUL AS
SELECT
    a.id,
    b.geom_way
FROM
    osm_2po_4pgr as a,
    bufferGPS as b
WHERE
    ST_Intersects(a.geom_way,b.st_transform);
```

# Background
F. Marchal, J. Hackney and K.W. Axhausen (2004). Efficient map-matching of large GPS data sets - Tests on a speed monitoring experiment in Zurich. Arbeitsbericht Verkehrs- und Raumplanung, Institut fu ̈r Verkehrsplanung und Transportsysteme, ETH Zu ̈rich, Zurich
