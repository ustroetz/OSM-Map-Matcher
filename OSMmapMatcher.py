import gdal, ogr, osr
gdal.SetConfigOption('OSM_CONFIG_FILE', 'osmconf.ini')
gdal.UseExceptions()
import math
import psycopg2
import os, sys
import time
import requests
import gdal
from optparse import OptionParser


def createOSMroads(bboxWGS84,osmfn):
    bboxCoords = str(bboxWGS84[0]) + ',' + str(bboxWGS84[2]) + ',' + str(bboxWGS84[1]) + ',' + str(bboxWGS84[3])
    url = 'http://www.overpass-api.de/api/xapi?way[highway=*][bbox=%s]' % bboxCoords
    osm = requests.get(url)
    file = open(osmfn, 'w')
    file.write(osm.text.encode('utf-8'))
    file.close()

def getBbox(l):
    bbox = l.GetExtent()
    return bbox

def createWaysTable(connString, qLayer, lineID):
    osmfn = 'OSMroads' + lineID + '.osm'
    bbox = getBbox(qLayer)
    createOSMroads(bbox, osmfn)

    t = 'ways'
    ds = ogr.Open(osmfn)
    w = ds.GetLayer(1)
    connOGR = ogr.Open("PG: " + connString)

    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)

    oLayer = connOGR.CreateLayer(t, srs, ogr.wkbLineString, ['OVERWRITE=YES'] )
    oLayerDef = oLayer.GetLayerDefn()
    oLayer.CreateField(ogr.FieldDefn("oneway", ogr.OFTInteger))
    oLayer.CreateField(ogr.FieldDefn("bearing", ogr.OFTReal))
    oLayer.CreateField(ogr.FieldDefn("roundabout", ogr.OFTReal))


    for lF in w:
        if lF.GetField("oneway") == "yes": oneWay = 1
        else: oneWay = 0

        if lF.GetField("junction") == "roundabout":roundAbout =1
        else: roundAbout = 0

        if roundAbout == 0:
            g = lF.GetGeometryRef()
            pCount = g.GetPointCount()
            count = 0
            while count in range(pCount-1):
                p1 = g.GetPoint(count)
                count += 1
                p2 = g.GetPoint(count)
                l = ogr.Geometry(ogr.wkbLineString)
                l.AddPoint(p1[0],p1[1],p1[2])
                l.AddPoint(p2[0],p2[1],p2[2])

                f = ogr.Feature(oLayerDef)
                bn = bearing(p1, p2)
                f.SetField("oneway", oneWay)
                f.SetField("bearing", bn)

                f.SetGeometry(l)
                oLayer.StartTransaction()
                oLayer.CreateFeature(f)
                oLayer.CommitTransaction()

    w.ResetReading()
    w.SetAttributeFilter("junction = 'roundabout'")
    roundAboutList = []
    roundAboutListI = []


    for f in w:
        roundAboutList.append(f.GetGeometryRef().ExportToJson())

    w.SetAttributeFilter("")
    for RAgeojson in roundAboutList:
        gRA = ogr.CreateGeometryFromJson(RAgeojson)
        w.ResetReading()
        for lF in w:
            g = lF.GetGeometryRef()
            if g.Intersects(gRA):
                i = gRA.Intersection(g)
                if i.GetGeometryType() == 1:
                    roundAboutListI.append(i.GetPoint())


    for RAgeojson in roundAboutList:
        gRA = ogr.CreateGeometryFromJson(RAgeojson)
        pRACount = gRA.GetPointCount()
        count = 0
        l = ogr.Geometry(ogr.wkbLineString)
        while count in range(pRACount):
            p = gRA.GetPoint(count)
            l.AddPoint(p[0],p[1],p[2])

            if p in roundAboutListI and l.GetPointCount() > 1:
                bn = bearing(l.GetPoint(l.GetPointCount()),l.GetPoint(0))
                f = ogr.Feature(oLayerDef)
                f.SetField("roundabout", roundAbout)
                f.SetField("oneway", oneWay)
                f.SetField("bearing", bn)
                f.SetGeometry(l)
                oLayer.StartTransaction()
                oLayer.CreateFeature(f)
                oLayer.CommitTransaction()
                l = ogr.Geometry(ogr.wkbLineString)
                p = gRA.GetPoint(count)
                l.AddPoint(p[0],p[1],p[2])
            count += 1







def checkReverseBearing(oB, oneWay):
    if not oneWay:
        if oB > 180: oB = oB - 180
        else: oB = oB + 180

    return oB


def checkIntersectIDs(l,id1,id2):
    f1 = l.GetFeature(id1)
    g1 = f1.GetGeometryRef()
    f2 = l.GetFeature(id2)
    g2 = f2.GetGeometryRef()
    return g1.Intersect(g2)


def removeSideways(rList, oLayer, oID0, oID1, oID2, oIDselected, connString, matchTable):
    oID3 = oID2
    oID2 = oID1
    oID1 = oID0
    oID0 = oIDselected
    if oID3 is not None:
        # check if oID1 and oID2 connect
        oID1oID2 = checkIntersectIDs(oLayer,oID1,oID2)

        # check if oID1 and oID3 connect
        oID1oID3 = checkIntersectIDs(oLayer,oID1,oID3)

        # if both true check if oID0 connects to oID1 or oID 2 -> non-connected fails
        if oID1oID2 and oID1oID3:
            if not checkIntersectIDs(oLayer,oID0,oID1):
                rList.remove(oID1)
            elif not checkIntersectIDs(oLayer,oID0,oID2):
                rList.remove(oID2)
            else:
                createOutputTable(connString,rList, matchTable)
                raise Exception("ConnectThree Error")

    return rList, oID0, oID1, oID2


def findFirstMatch(qID, qLayer, oLayer, rList):

    # Find first matching OSM segment o1 for q1
    oDict = {}
    qFeature, q1Geom = GetGeomGetFeatFromID(qLayer, qID)
    oLayer.ResetReading()
    for oFeature in oLayer:
        oGeom = oFeature.GetGeometryRef()
        oIDcurrent = oFeature.GetFID()
        oDict[oIDcurrent] = oGeom.Distance(q1Geom)

    oIDselected = min(oDict, key=oDict.get)
    rList.append(oIDselected)

    return oIDselected, rList


def findNextMatch(qID, qLayer, oLayer, rList):
    oDict = {}
    oIDselected = None

    while oIDselected == None:

        qFeature, qGeom = GetGeomGetFeatFromID(qLayer, qID)
        oLayer.ResetReading()
        oLayer.SetAttributeFilter("ogc_fid NOT IN ("  + (",".join(str(x) for x in rList)) + ")")

        bufferDist = 0.01
        fGeom = qGeom.Buffer(bufferDist)
        oLayer.SetSpatialFilter(fGeom)
        while oLayer.GetFeatureCount() < 10:
            # increase buffer if not enough features are within buffer
            bufferDist += 0.1
            fGeom = qGeom.Buffer(bufferDist)
            oLayer.SetSpatialFilter(fGeom)

        qGeom = transformGeom(qGeom, 4326, 3857)

        for oFeature in oLayer:
            oGeom = oFeature.GetGeometryRef()
            oGeom = transformGeom(oGeom, 4326, 3857)
            oIDcurrent = oFeature.GetFID()
            dist = oGeom.Distance(qGeom)
            if dist <= 5.0:
                oDict[oIDcurrent] = dist

        if oDict:
            oIDselected = min(oDict, key=oDict.get)
        else:
            qID += 1

    return qID, oIDselected


def testMatch(qID, qLayer, oLayer, rList):

    test = False
    count = 0
    countT = 0

    while count < 3:
            qFeature, qGeom = GetGeomGetFeatFromID(qLayer, qID)
            qGeom = transformGeom(qGeom, 4326, 3857)
            oLayer.ResetReading()
            for oFeature in oLayer:
                oGeom = oFeature.GetGeometryRef()
                oGeom = transformGeom(oGeom, 4326, 3857)
                oIDcurrent = oFeature.GetFID()
                dist = oGeom.Distance(qGeom)
                if dist <= 5.0:
                    qID += 1
                    countT += 1
                    break

            count += 1

    if countT == 3:
        test = True

    return test


def findNextMatchS(qID, qLayer, oLayer, rList):
    test = False
    while not test:
        qID, oIDselected = findNextMatch(qID, qLayer, oLayer, rList)
        test = testMatch(qID, qLayer, oLayer, rList)
        qID += 1

    return (qID-1), oIDselected


def bearing(origin, destination):
    lon1, lat1, z = origin
    lon2, lat2, z = destination

    rlat1 = math.radians(lat1)
    rlat2 = math.radians(lat2)
    rlon1 = math.radians(lon1)
    rlon2 = math.radians(lon2)
    dlon = math.radians(lon2-lon1)

    b = math.atan2(math.sin(dlon)*math.cos(rlat2),math.cos(rlat1)*math.sin(rlat2)-math.sin(rlat1)*math.cos(rlat2)*math.cos(dlon)) # bearing calc
    bd = math.degrees(b)
    br,bn = divmod(bd+360,360) # the bearing remainder and final bearing

    return bn


def query(connString, statement):
    connPsycopg = psycopg2.connect(connString)
    cursor = connPsycopg.cursor()
    cursor.execute(statement)
    connPsycopg.commit()
    try:
        result = cursor.fetchall()
        return result
    except:
        pass


def vertexQuery(geom):
    return """
        SELECT id::integer FROM osm_2po_vertex
              ORDER BY geom_vertex <-> ST_GeometryFromText('%s',4326) LIMIT 1
              """% (geom.ExportToWkt())


def bufferQuery(lineID):
    return """
    CREATE TABLE tracks_buffer AS SELECT name, origin, destination, ST_Transform(ST_Buffer(pretty_geom,0.001),4326) FROM lines WHERE id = %s;
    """% (lineID)

def renameQuery(oldName,newName):
    return """
    ALTER TABLE %s RENAME TO %s;
    """% (oldName, newName)


def dropTableQuery(table):
    return """
    DROP TABLE IF EXISTS %s;
    """% (table)

def checkTableExistsQuery(table):
    return """
    SELECT relname FROM pg_class WHERE relname = '%s';
    """% (table)

def GetFIDfromIDQuery(ID):
    return """
        SELECT ogc_fid from ways_extract where id in (%s);
        """% (ID)


def intersectQuery():
    return """
        CREATE TABLE ways_extract AS
    SELECT
        a.ogc_fid,
        a.wkb_geometry,
        a.oneway,
        a.bearing,
        b.name,
        b.origin,
        b.destination
    FROM
        ways as a,
        tracks_buffer as b
    WHERE
        ST_Intersects(a.wkb_geometry,b.st_transform);
        """


def checkTableExists(table, connString):
    statement = checkTableExistsQuery(table)
    rowsCount = len(query(connString, statement))
    if rowsCount > 0:
        exists = True
        print table, "does already exist. Data preperation will be skipped"
    else:
        exists = False
        print table, "does not exist yet"
    return exists

def GetFIDfromID(ID, connString):
    statement = GetFIDfromIDQuery(ID)
    FID = query(connString, statement)
    return FID


def transformGeom(geom, sourceEPSG, targetEPSG):
    source = osr.SpatialReference()
    source.ImportFromEPSG(sourceEPSG)
    target = osr.SpatialReference()
    target.ImportFromEPSG(targetEPSG)
    transform = osr.CoordinateTransformation(source, target)
    geom.Transform(transform)

    return geom


def GetGeomGetFeatFromID(l, id):
    f = l.GetFeature(id)
    g = f.GetGeometryRef()

    return f, g


def createTableFromIDQuery(rList,table):
    return """
    CREATE TABLE """ + table + """ AS SELECT ogc_fid, name, origin, destination, wkb_geometry FROM ways_extract WHERE "ogc_fid" IN (""" + (",".join(str(x) for x in rList)) + ")"


def createTableFromLineQuery(lineID, gpsTable):
    return """
    CREATE TABLE %s AS SELECT (ST_DumpPoints(pretty_geom)).geom FROM lines WHERE id = %s; ALTER TABLE %s ADD COLUMN ogc_Fid SERIAL;
    """% (gpsTable,lineID,gpsTable)

def addColumnToTableQuery(table, column, typeColumn):
    return """
    ALTER TABLE %s ADD COLUMN %s %s;
    """% (table,column, typeColumn)


def createOutputTable(connString,rList, table):
    statement = dropTableQuery(table)
    query(connString, statement)
    statement = createTableFromIDQuery(rList,table)
    query(connString, statement)
    print "Table %s created"% (table)

def createTracksTable(lineID, gpsTable, connString):
    print "GPS Data Preperation"
    statement = createTableFromLineQuery(lineID, gpsTable)
    query(connString, statement)
    addBearingToTable(gpsTable,connString)
    print "GPS points and tracks imported as 'tracks' and ", gpsTable


def addBearingToTable(table, connString):
    connOGR = ogr.Open("PG: " + connString, True)
    l = connOGR.GetLayer(table)
    l.CreateField(ogr.FieldDefn("bearing", ogr.OFTReal))

    fCount = l.GetFeatureCount()
    count = 1
    while count in range(fCount):
        f1, g1 = GetGeomGetFeatFromID(l, count)
        p1 =  g1.GetPoint(0)
        count += 1
        f2, g2 = GetGeomGetFeatFromID(l, count)
        p2 = g2.GetPoint(0)
        bn = bearing(p1, p2)
        f1.SetField("bearing", bn)
        l.StartTransaction()
        l.SetFeature(f1)
        l.CommitTransaction()



def createWaysExtractTable(connString, lineID):
    # buffer track
    statement = dropTableQuery("tracks_buffer")
    query(connString, statement)
    statement = bufferQuery(lineID)
    query(connString, statement)
    print "Buffer of 'tracks' created as 'tracks_buffer'"

    # extract ways intersecting buffer
    statement = dropTableQuery("ways_extract")
    query(connString, statement)
    statement = intersectQuery()
    query(connString, statement)
    print "Intersected 'tracks_buffer' with 'ways' created as 'ways_extract'"

    print "##################################################"


def createOSMGPX(connString, gpsTable, sqID,tqID):
    timestr = time.strftime("%Y%m%d-%H%M%S")
    osm_fn = "osm_" + timestr + ".gpx"
    tolerance = 50
    ogc_fidString = ( ", ".join( str(e) for e in range(sqID-tolerance, tqID+tolerance) ) )
    callStatement = "ogr2ogr -f 'GPX' " + osm_fn + " PG:'host=localhost " + connString + "' -sql 'SELECT ogc_fid, geom FROM " + gpsTable + " WHERE ogc_fid IN (" + ogc_fidString +")' -nlt Point"
    os.system(callStatement)


def checkPointExists(l,id):
    f = l.GetFeature(id)
    if f:
        return True
    else:
        return False



def main(lineID, qID, createWays):
    osmTable = "ways_extract"
    gpsTable = "track_points_" + lineID
    matchTable = "ways_match_" + lineID

    databaseName = "istanbul"
    databaseUser = "postgres"
    databasePW = ""
    connString = "dbname=%s user=%s password=%s" %(databaseName,databaseUser,databasePW)
    connOGR = ogr.Open("PG: " + connString)

    if not checkTableExists(gpsTable,connString):
        createTracksTable(lineID, gpsTable, connString)

    qLayer = connOGR.GetLayer(gpsTable)

    if createWays:
        createWaysTable(connString, qLayer, lineID)
        createWaysExtractTable(connString, lineID)

    oLayer = connOGR.GetLayer(osmTable)

    qFeatureCount = qLayer.GetFeatureCount()

    rList = []
    oID2 = None
    oID1 = None
    oID0 = None

    print "Total GPS points to match:", qFeatureCount

    oIDselected, rList = findFirstMatch(qID, qLayer, oLayer, rList)
    print "##################################################"
    print "First selecte segment ogc_fid =", oIDselected

    while qID <= qFeatureCount:
        # Loop over remaining OSM segments for all qn
        oDict = {}

        while not checkPointExists(qLayer,qID):
            qID += 1
            qFeatureCount += 1

        print "##################################################"
        print "Point ogc_fid", qID, "of", qFeatureCount
        qFeature, qGeom = GetGeomGetFeatFromID(qLayer, qID)

        # get selected line
        oSFeature, oSGeom = GetGeomGetFeatFromID(oLayer, oIDselected)

        oLayer.ResetReading()
        oLayer.SetAttributeFilter(None)
        oLayer.SetSpatialFilter(None)


        #loop through all segments in OSM layer
        for oFeature in oLayer:
            oGeom = oFeature.GetGeometryRef()
            oIDcurrent = oFeature.GetFID()
            if oFeature.GetField("oneway") == 1: oneWay = True
            else: oneWay = False

            # check if current line intersects with last selected line
            if oGeom.Intersects(oSGeom):

                # get bearing weight
                oB = oFeature.GetField("bearing")
                qB = qFeature.GetField("bearing")
                if qB != None and qB != 0.0:
                    wB1 = abs(1 - abs(qB - oB)/180.0)
                    oB = checkReverseBearing(oB, oneWay)
                    wB2 = abs(1 - abs(qB - oB)/180.0)
                    wB = max(wB1,wB2)
                else:
                    wB = 0.0

                # get distance weight
                oGeom = transformGeom(oGeom, 4326, 3857)
                qGeom = transformGeom(qGeom, 4326, 3857)
                d = oGeom.Distance(qGeom)
                qGeom = transformGeom(qGeom, 3857, 4326)

                # normalize distance weight
                dT = 100.0              # distance threshold
                if qID == 20: dt = 20.0 # decrease threshold after first 20 points (left parking spot)

                if d >= dT:
                    wD = 0.0
                elif d < dT and d > 0.0:
                    wD = 1-d/dT
                elif d == 0.00:
                    wD = 1.0

                # get final weight
                w = (wD*2+wB)/3.0

                print oIDcurrent, "connects to", oIDselected, "with weight", round(w,2), "| wB", round(wB,2), "(", oB, qB, oneWay, ") | wD", round(wD,2),""

                oDict[oIDcurrent] = w, wB, wD

        # Check if q not within 20m of next oFeature (weight Distance equals 0)
        if sum([wDList[2] for wDList in oDict.values()]) == 0:
            print "No road within 10 m of current GPS point."
            sqID = qID

            tqID, oIDselected = findNextMatchS(sqID, qLayer, oLayer, rList)
            print "Next Point on street segment", sqID, "with OSM segment", oIDselected

            createOutputTable(connString,rList, matchTable)

            createOSMGPX(connString, gpsTable, sqID,tqID)
            raise Exception("Road doesn't exist. OSM GPX file generated for digitizing in OSM")

        else:
            oIDselected = max(oDict, key=oDict.get)
            qID += 1
            if oIDselected not in rList:
                rList.append(oIDselected)
                rList, oID0, oID1, oID2 = removeSideways(rList, oLayer, oID0, oID1, oID2, oIDselected, connString, matchTable)

        print "selected line ogc_fid", oIDselected




    createOutputTable(connString,rList, matchTable)




if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option("-l", "--lineID", dest="lineID", type="string")
    parser.add_option("-q", "--qID", dest="qID", default=1, type="int")
    parser.add_option("-o", "--osm", action="store_true", default=False)

    (options, args) = parser.parse_args()

    lineID = options.lineID
    qID = options.qID
    createWays = options.osm

    main(lineID, qID, createWays)
