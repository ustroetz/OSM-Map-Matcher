import ogr, osr
import math
import psycopg2
import os

def checkIntersectIDs(l,id1,id2):
    f1 = l.GetFeature(id1)
    g1 = f1.GetGeometryRef()
    f2 = l.GetFeature(id2)
    g2 = f2.GetGeometryRef()
    return g1.Intersect(g2)


def removeSideways(rList, oLayer, oID0, oID1, oID2, oIDselected):
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


def routeQuery(sV, tV):
    return """
        SELECT id2 FROM pgr_dijkstra('
                        SELECT id,
                                 source::integer,
                                 target::integer,
                                 cost
                                FROM osm_2po_4pgr',
                        %s, %s, false, false);
                        """% (sV, tV)


def bufferQuery():
    return """
    CREATE TABLE tracks_buffer AS SELECT ogc_fid, ST_Transform(ST_Buffer(wkb_geometry,0.001),4326) FROM tracks;
        """


def dropTableQuery(table):
        return """
            DROP TABLE IF EXISTS %s;
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
        a.id,
        a.wkb_geometry,
        a.x1,
        a.y1,
        a.x2,
        a.y2,
        a.reverse_co
    FROM
        ways_split as a,
        tracks_buffer as b
    WHERE
        ST_Intersects(a.wkb_geometry,b.st_transform);
        """


def GetFIDfromID(ID, connString):
    statement = GetFIDfromIDQuery(ID)
    FID = query(connString, statement)
    return FID


def routing(sourceGeom, targetGeom, connString):
    # routes form source to target and returns list with ids of ways

    # get source route vertex
    statement = vertexQuery(sourceGeom)
    sV = query(connString, statement)

    # get target route vertex
    statement = vertexQuery(targetGeom)
    tV = query(connString, statement)

    # get route
    statement = routeQuery(sV[0][0], tV[0][0])
    r = query(connString, statement)

    rW = [i[0] for i in r[:-1]]

    return rW


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
    CREATE TABLE """ + table + """ AS SELECT * FROM ways_extract WHERE "ogc_fid" IN (""" + (",".join(str(x) for x in rList)) + ")"


def createOutputTable(connString,rList):
    table = "ways_match"
    statement = dropTableQuery(table)
    query(connString, statement)
    statement = createTableFromIDQuery(rList,table)
    query(connString, statement)


def GPSDataPrep(gpxfn, connString):
    print "GPS Data Preperation"
    # import GPS points and track
    callStatement = "ogr2ogr -f 'PostgreSQL' PG:'" + connString + "' %s track_points tracks -overwrite"% (gpxfn)
    os.system(callStatement)
    print "GPS points and tracks imported as 'tracks' and 'track_points'"

    # buffer track
    statement = dropTableQuery("tracks_buffer")
    query(connString, statement)
    statement = bufferQuery()
    query(connString, statement)
    print "Buffer of 'tracks' created as 'tracks_buffer'"

    # extract ways intersecting buffer
    statement = dropTableQuery("ways_extract")
    query(connString, statement)
    statement = intersectQuery()
    query(connString, statement)
    print "Intersected 'tracks_buffer' with 'ways_split' created as 'ways_extract'"

    print "##################################################"


def main():
    gpxfn = "sample2.gpx"

    osmTable = "ways_extract"
    gpsTable = "track_points"

    databaseName = "omm"
    databaseUser = "ustroetz"
    databasePW = ""
    connString = "dbname=%s user=%s password=%s" %(databaseName,databaseUser,databasePW)

    GPSDataPrep(gpxfn, connString)

    connOGR = ogr.Open("PG: " + connString)

    oLayer = connOGR.GetLayer(osmTable)
    qLayer = connOGR.GetLayer(gpsTable)
    qFeatureCount = qLayer.GetFeatureCount()

    rList = []
    qID = 1
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

        print "##################################################"
        print "Point ogc_fid", qID, "of", qFeatureCount

        # construct current GPS point
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

            # check if current line intersects with last selected line
            if oGeom.Intersects(oSGeom):

                # get bearing weight
                if oFeature.GetField("reverse_co"):
                    oPointO = (oFeature.GetField("x1"), oFeature.GetField("y1"), 0.0)
                    oPointD = (oFeature.GetField("x2"), oFeature.GetField("y2"), 0.0)
                oB = bearing(oPointO, oPointD)
                qB = qFeature.GetField("course")
                if qB != None:
                    dob = abs(oB - float(qB))
                    wB = 1.0-float(qB)*dob/100.0/100.0
                else: wB = 0
                if wB < 0:
                    wB = 0.0

                # get distance weight
                oGeom = transformGeom(oGeom, 4326, 3857)
                qGeom = transformGeom(qGeom, 4326, 3857)
                d = oGeom.Distance(qGeom)
                qGeom = transformGeom(qGeom, 3857, 4326)

                # normalize distance weight
                dT = 100.0              # distance threshold
                if qID == 20: dt = 20.0 # decrease thresholf after first 20 points (left parking spot)

                if d >= dT:
                    wD = 0
                elif d < dT and d > 0.0:
                    wD = 1-d/dT
                elif d == 0.00:
                    wD = 1.0

                # get final weight
                w = (wD+(wB/3.0))/2.0

                print oIDcurrent, "connects to", oIDselected, "with weight", w, "(wB",wB,"wD",wD,")"

                oDict[oIDcurrent] = w, wB, wD


        if sum([wDList[2] for wDList in oDict.values()]) == 0:
            # q not within 50m of next oFeature (weight Distance equals 0)
            print "No road within 50 m of current GPS point."

            qID, oIDselected = findNextMatchS(qID, qLayer, oLayer, rList)
            print "Next connected Point", qID, "with OSM segment", oIDselected

            print "Routing from last selected line", oIDselected
            sourceGeom = ogr.Geometry(ogr.wkbPoint)
            sourceGeom.AddPoint(oSGeom.GetPoint()[0], oSGeom.GetPoint()[1], 0)

            print "Routing to Point", qID
            qFeature, qGeom = GetGeomGetFeatFromID(qLayer, qID)

            ID = routing(sourceGeom, qGeom, connString)
            print "Routing selected lines ID", ID

            rWL = ','.join(map(str, ID))
            sSeg = GetFIDfromID(rWL, connString)
            [rList.append(oIDselectedR[0]) if oIDselectedR[0] not in rList else '' for oIDselectedR in sSeg]

            if oIDselected not in rList:
                rList.append(oIDselected)
            qID += 1


        else:
            oIDselected = max(oDict, key=oDict.get)
            qID += 1
            if oIDselected not in rList:
                rList.append(oIDselected)
                rList, oID0, oID1, oID2 = removeSideways(rList, oLayer, oID0, oID1, oID2, oIDselected)

        print "selected line ogc_fid", oIDselected





    createOutputTable(connString,rList)
    print "Final table ways_match created"




if __name__ == '__main__':
    main()
