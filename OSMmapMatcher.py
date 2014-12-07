import ogr, osr
import sys
import math
import psycopg2
import warnings

def findFirstMatch(qID, qLayer, oLayer, rList):

    # Find first matching OSM segment o1 for q1
    oDict = {}
    qFeature = qLayer.GetFeature(qID)
    q1Geom = qFeature.GetGeometryRef()
    oLayer.ResetReading()
    for oFeature in oLayer:
        oGeom = oFeature.GetGeometryRef()
        oIDcurrent = oFeature.GetFID()
        oDict[oIDcurrent] = oGeom.Distance(q1Geom)

    oIDselected = min(oDict, key=oDict.get)
    rList.append(oIDselected)
    print "##########################"
    print "First matching OSM segment ID =", oIDselected

    return oIDselected, rList


def findNextMatch(qID, qLayer, oLayer, rList, transform3857):
    oDict = {}
    oIDselected = None

    while oIDselected == None:

        qFeature = qLayer.GetFeature(qID)
        qGeom = qFeature.GetGeometryRef()
        qGeom.Transform(transform3857)
        oLayer.ResetReading()
        for oFeature in oLayer:
            oGeom = oFeature.GetGeometryRef()
            oGeom.Transform(transform3857)
            oIDcurrent = oFeature.GetFID()
            dist = oGeom.Distance(qGeom)
            if dist <= 5.0:
                oDict[oIDcurrent] = dist

        if oDict:
            oIDselected = min(oDict, key=oDict.get)
        else:
            qID += 1


    return qID, oIDselected

def testMatch(qID, qLayer, oLayer, rList, transform3857):

    test = False
    count = 0
    countT = 0

    while count < 3:
            qFeature = qLayer.GetFeature(qID)
            qGeom = qFeature.GetGeometryRef()
            qGeom.Transform(transform3857)
            oLayer.ResetReading()
            for oFeature in oLayer:
                oGeom = oFeature.GetGeometryRef()
                oGeom.Transform(transform3857)
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

def findNextMatchS(qID, qLayer, oLayer, rList, transform3857):

    test = False
    while not test:
        qID, oIDselected = findNextMatch(qID, qLayer, oLayer, rList, transform3857)
        test = testMatch(qID, qLayer, oLayer, rList, transform3857)
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


def main():

    osmTable = "ways_extract_split"
    gpsTable = "track_points_sub"

    databaseName = "omm"
    databaseUser = "postgres"
    databasePW = ""
    connString = "dbname=%s user=%s password=%s" %(databaseName,databaseUser,databasePW)

    source = osr.SpatialReference()
    source.ImportFromEPSG(4326)
    target = osr.SpatialReference()
    target.ImportFromEPSG(3857)
    transform3857 = osr.CoordinateTransformation(source, target)
    transform4326 = osr.CoordinateTransformation(target, source)


    connOGR = ogr.Open("PG: " + connString)

    oLayer = connOGR.GetLayer(osmTable)
    qLayer = connOGR.GetLayer(gpsTable)
    qFeatureCount = qLayer.GetFeatureCount()

    print "Total GPS points to match:", qFeatureCount

    rList = []

    qID = 1
    oIDselected, rList = findFirstMatch(qID, qLayer, oLayer, rList)


    while qID <= qFeatureCount:
        # Loop over remaing OSM segments for all qn

        print "##################################################"
        print "Point ID", qID, "of", qFeatureCount
        oDict = {}

        # construct current GPS point
        qFeature = qLayer.GetFeature(qID)
        qGeom = qFeature.GetGeometryRef()

        # get selected line
        oSFeature = oLayer.GetFeature(oIDselected)
        oSGeom = oSFeature.GetGeometryRef()
        oSPointF, oSPointP = oSGeom.GetPoints()

        # reset reading
        oLayer.ResetReading()

        #loop through all segments in OSM layer
        for oFeature in oLayer:

            oGeom = oFeature.GetGeometryRef()
            oIDcurrent = oFeature.GetFID()

            # check if first or last point intersects with last selected line
            oPointD, oPointO = oGeom.GetPoints()
            if oPointO == oSPointF or oPointO == oSPointP or oPointD == oSPointF or oPointD == oSPointP:

                # get bearing weight
                if oFeature.GetField("reverse_co"):
                    oPointO = (oFeature.GetField("x1"), oFeature.GetField("y1"), 0.0)
                    oPointD = (oFeature.GetField("x2"), oFeature.GetField("y2"), 0.0)
                oB = bearing(oPointO, oPointD)
                qB = qFeature.GetField("course")
                dob = abs(oB - float(qB))
                wB = 1.0-float(qB)*dob/100.0/100.0
                if wB < 0:
                    wB = 0.0

                # get distance weight
                oGeom.Transform(transform3857)
                qGeom.Transform(transform3857)
                d = oGeom.Distance(qGeom)
                qGeom.Transform(transform4326)

                if d >= 10.0:                 # normalize distance weight
                    wD = 0
                elif d < 10.0 and d > 0.0:
                    wD = 1-d/50.0
                elif d == 0.00:
                    wD = 1.0

                # final weight
                w = (wD+(wB/10.0))/2.0

                print oIDcurrent, "connects to", oIDselected, "with weight", w, "(wB",wB,"wD",wD,")"


                oDict[oIDcurrent] = w, wB, wD





        if sum([wDList[2] for wDList in oDict.values()]) == 0:
            # q not within 50m of next oFeature (weight Distance eqauls 0)
            #warnings.warn("No road within 50m of current GPS point.")
            print "No road within 50m of current GPS point."

            qID, oIDselected = findNextMatchS(qID, qLayer, oLayer, rList, transform3857)
            print "Next connected Point", qID, "with OSM segment", oIDselected

            print "Routing to Point", qID
            qFeature = qLayer.GetFeature(qID)
            qGeom = qFeature.GetGeometryRef()
            for sq in qGeom:
                q = sq.GetPoint()

            connPsycopg = psycopg2.connect(connString)
            cursor = connPsycopg.cursor()
            statement = """
                SELECT seq, gid FROM pgr_fromAtoB('ways',%s,%s,%s,%s)
                        """% (str(q[0]),str(q[1]),str(oSGeom.GetPoint(0)[0]),str(oSGeom.GetPoint(0)[1]))
            cursor.execute(statement)
            selectedWays = cursor.fetchall()

            # add current oFeature to selectedWays TODO: can be replaced once split_ways are routable
            cursor.execute("select gid from ways_extract_split where ogc_fid = %s;"% oIDselected)
            selectedWay = cursor.fetchall()

            sSeg = ','.join(map(str, [row[1] for row in selectedWays])) + ',' + str(selectedWay[0][0])

            cursor.execute("select ogc_fid from ways_extract_split where gid in (%s);"% sSeg)
            tStatus = cursor.fetchall()
            print "Routing selected lines ID", [i[0] for i in tStatus]
            for i in tStatus:
                oIDselectedR = int(i[0])
                if oIDselectedR not in rList:
                    rList.append(oIDselectedR)

            if oIDselected not in rList:
                rList.append(oIDselectedR)
            print "selectedLine ID", oIDselected
            
            qID += 1


        else:
            oIDselected = max(oDict, key=oDict.get)
            qID += 1
            print "selectedLine ID", oIDselected
            if oIDselected not in rList:
                rList.append(oIDselected)


    print """ "ogc_fid" IN (""" + (",".join(str(x) for x in rList)) + ")"




if __name__ == '__main__':
    main()
