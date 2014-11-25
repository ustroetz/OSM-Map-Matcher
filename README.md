                                                                            ;
# import GPS track
ogr2ogr -f "PostgreSQL" PG:"host=localhost user=ustroetz dbname=test" sample.geojson

# buffer GPS track
CREATE TABLE bufferGPS AS SELECT ogc_fid, ST_Transform(ST_Buffer(wkb_geometry,10),4326) FROM ogrgeojson

# intersect GPS buffer with roads
CREATE TABLE extractISTANBUL AS
SELECT
    a.id,
    b.geom_way
FROM
    osm_2po_4pgr as a,
    bufferGPS as b
WHERE
    ST_Intersects(a.geom_way,b.st_transform);
