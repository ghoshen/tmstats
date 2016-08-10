#!/usr/bin/env python
""" This program gets all available performance reports from Toastmasters 
    for the current Toastmasters year.  Use it to catch up when starting
    to track district statistics. """

import urllib, tmparms, os, sys
from tmutil import cleandate
from datetime import datetime, timedelta, date
    
        
def monthend(m, y):
    lasts = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)

    if (m == 2) and (0 == y % 4):
        eom = (2, 29, y)
    else:
        eom = (m, lasts[m-1], y)
        
    return '%d/%d/%d' % eom
    

def makeurl(report, district, tmyearpiece="", monthend="", asof=""):
    baseurl = "http://dashboards.toastmasters.org/export.aspx?type=CSV&report=" + report + "~" + district
    return baseurl + "~" + monthend + "~" + asof + "~" + tmyearpiece

        
def getresponse(url):
    print url
    flo = urllib.urlopen(url)
    clubinfo = flo.readlines()
    # clubinfo = urllib.urlopen(url).read().split('\n')
    if len(clubinfo) < 10:
        # We didn't get anything of value
        clubinfo = False
    elif clubinfo[0][0] in ['{', '<']:
        # This isn't a naked CSV
        clubinfo = False
    return clubinfo
        
        
def getreportfromWHQ(report, district, altdistrict, tmyearpiece, month, thedate):
    url = makeurl(report, district, tmyearpiece, monthend(month[0],month[1]), datetime.strftime(thedate, '%m/%d/%Y'))
    resp = getresponse(url)
    if not resp:
        if altdistrict:
            url = makeurl(report, altdistrict, tmyearpiece, monthend(month[0],month[1]), datetime.strftime(thedate, '%m/%d/%Y'))
            print 'Trying', url
            resp = getresponse(url)
    if not resp:
        print "No valid response received"
    return resp
    


def makefilename(reportname, thedate):
    return '%s.%s.csv' % (reportname, thedate.strftime('%Y-%m-%d'))
    
def writedailyreports(data, district, altdistrict, tmyearpiece, month, thedate):
    print 'writing Month of %s reports for %s' % ('/'.join(['%02d' % m for m in month]), thedate.strftime('%Y-%m-%d'))
    with open(makefilename('clubperf', thedate), 'w') as f:
        f.write(''.join(data).replace('\r',''))
    data = getreportfromWHQ('divisionperformance', district, altdistrict, tmyearpiece, month, thedate)
    with open(makefilename('areaperf', thedate), 'w') as f:
        f.write(''.join(data).replace('\r',''))
    data = getreportfromWHQ('districtperformance', district, altdistrict, tmyearpiece, month, thedate)
    with open(makefilename('distperf', thedate), 'w') as f:
        f.write(''.join(data).replace('\r',''))
    
def dolatest(district, altdistrict, finals, tmyearpiece):
    for monthend in finals:
        for (urlpart, filepart) in (('clubperformance', 'clubperf'), 
                                    ('divisionperformance', 'areaperf'),
                                    ('districtperformance', 'distperf')):
            url = makeurl(urlpart, district, monthend=monthend, tmyearpiece=tmyearpiece)
            data = getresponse(url)
            if not data and altdistrict:
                url = makeurl(urlpart, altdistrict, monthend=monthend, tmyearpiece=tmyearpiece)
                data = getresponse(url)
            if data:
                thedate = datetime.strptime(cleandate(data[-1].split()[-1]), '%Y-%m-%d').date()  # "Month of Jun, as of 07/02/2015" => '2015-07-02'
                with open(makefilename(filepart, thedate), 'w') as f:
                    f.write(''.join(data).replace('\r',''))
                print 'Updated %s for %s (month: %s, year: %s)' % (filepart, thedate, monthend, tmyearpiece)

if __name__ == "__main__":
    
    # Make it easy to run under TextMate
    if 'TM_DIRECTORY' in os.environ:
        os.chdir(os.path.join(os.environ['TM_DIRECTORY'],'data'))
        if not sys.argv[1:]:
            sys.argv[1:] = '--district 4'.split()
    
    reload(sys).setdefaultencoding('utf8')
            
    parms = tmparms.tmparms()
    parms.add_argument('--district', type=int)
    parms.add_argument('--altdistrict', type=int)
    parms.add_argument('--startdate', default=None)
    parms.add_argument('--enddate', default='today')
    parms.add_argument('--skipclubs', action='store_true',
     help='Do not get latest club information.')
    parms.parse()

    district = "%0.2d" % parms.district
    clubdistrict = district   # Unless we have a problem
    try:
        os.remove('altdistrict.txt')
    except OSError:
        pass
    # Handle the case of a district being reformed
    if parms.altdistrict:
        altdistrict = "%0.2d" % parms.altdistrict
        url = "https://www.toastmasters.org/service/clubs/export/Downloads/Csv?district=%s&advanced=1&latitude=0&longitude=0" % district
        if not getresponse(url):
            sys.stderr.write('No clubs found for District %s; using %s instead.' % (district, altdistrict))
            clubdistrict = altdistrict
            with open('altdistrict.txt', 'w') as f:
                f.write(altdistrict + '\n')
    else:
        altdistrict = ''
            
    # Compute dates
    enddate = datetime.strptime(cleandate(parms.enddate), '%Y-%m-%d').date()
    if parms.startdate:
        startdate = datetime.strptime(cleandate(parms.startdate), '%Y-%m-%d').date()
        (lastmonth, last) = (False, False)
    else:
        # If nothing was specified, start with the latest date in the database.
        import dbconn, latest
        conn = dbconn.dbconn(parms.dbhost, parms.dbuser, parms.dbpass, parms.dbname)
        (lastmonth, last) = latest.getlatest('clubperf', conn)
        if last:
            startdate = datetime.strptime(last, '%Y-%m-%d').date() + timedelta(1)
        else:
            startdate = False
        conn.close()

    # To avoid needless chatter, figure out today and yesterday:
    today = date.today()
    yesterday = today - timedelta(1)

    # Figure out what months we need info for:
    tmmonths = (7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5, 6)
    # If it's January-July, we care about the TM year which started the previous July 1; otherwise, it's this year.
    if startdate:
        if (startdate.month <= 7):
            tmyear = startdate.year - 1 
        else:
            tmyear = startdate.year
    else:
        if (today.month <= 7):
            startdate = datetime(today.year-1, 7, 1)
        else:
            startdate = datetime(today.year, 7, 1)
        startdate = datetime.date(startdate)
        tmyear = startdate.year

    tmyearpiece = '%d-%d' % (tmyear, tmyear+1)  # For the URLs

    # Now, compute the months we're going to look for

    if (startdate.month == 7):
        months = tmmonths
    else:
        months = []
        for m in tmmonths:
            months.append(m)
            if m == startdate.month:
                break
    
    # Don't look for data for months earlier than the most recent data in the database
    if lastmonth:
        monthnum = int(lastmonth[5:7])
        months = months[months.index(monthnum):]
    months = [(m, tmyear + (1 if m <= 6 else 0)) for m in months]
    
    # Save the final and next-to-final months for "dolatest" to cope with Toastmasters'
    #  most recent change (not including Charter/Suspend info unless a month is given)
    finals = [monthend(m[0],m[1]) for m in months[-2:]]
    
    

    
    # Get today's data
    print "Getting the latest performance info"
    dolatest(district, altdistrict, finals, tmyearpiece)
        
        
    # And get and write current club data unless told not to
    if not parms.skipclubs:
        url = "https://www.toastmasters.org/service/clubs/export/Downloads/Csv?district=%s&advanced=1&latitude=0&longitude=0" % clubdistrict
        clubdata = getresponse(url)
        if clubdata:
            with open(makefilename('clubs', today), 'w') as f:
                        f.write(''.join(clubdata).replace('\r',''))

    sys.exit()   # Only today!

    # We assume all reports have identical availabilities, so we
    #    use the clubperf report to find the first available report
    #    on or after our startdate.
    
    # Try to get the obvious first candidate report if we're not looking at the most recent data
    thedate = startdate
    if thedate and (thedate < yesterday):
        report = getreportfromWHQ('clubperformance', district, altdistrict, tmyearpiece, months[0], thedate)
    else:
        report = None       # We'll get the latest data instead.

  
    # If we didn't get data and we're looking at the past,
    #   we may have gone past a month boundary.
    while not report and thedate <= enddate and thedate < yesterday:
        
        # See if there's data for "thedate" in the next month
        report = getreportfromWHQ('clubperformance', district, altdistrict, tmyearpiece, months[1], thedate)
        if report:
             # All is well; we're in a new month of data
             months = months[1:]
             break
            
        print 'No report available for month %d on %s' % (months[0][0], thedate.strftime('%Y-%m-%d'))
        # Try the next day
        
        thedate += timedelta(1)
        report = getreportfromWHQ('clubperformance', district, altdistrict, tmyearpiece, months[0], thedate)

    
    # OK, now we should have a report in hand.
    while (months and thedate <= enddate and thedate < yesterday):
        if report:
            writedailyreports(report, district, altdistrict, tmyearpiece, months[0], thedate)
        thedate += timedelta(1)
        report = getreportfromWHQ('clubperformance', district, altdistrict, tmyearpiece, months[0], thedate)
        if not report:
            # We might have found the end of the data for the previous month
            # print 'months[0][0] = %s, thedate.month = %s' % (months[0][0], thedate.month)
            if months[0][0] != thedate.month:
                months = months[1:]
                if not months:
                    break
                if thedate < yesterday:
                    print "Checking %d/%d" %  months[0]
                report = getreportfromWHQ('clubperformance', district, altdistrict, tmyearpiece, months[0], thedate)
            if not report and (thedate < yesterday):
                # Don't complain about missing data for today or yesterday; that's to be expected.
                print 'No data available for %s' % (thedate.strftime('%Y-%m-%d'))
                

        
    # If the enddate is today, get today's information and write it by the appropriate 'asof' thedate

    if enddate.year == today.year and enddate.month == today.month and enddate.day == today.day:
        print "Getting the latest performance info"
        dolatest(district, altdistrict, finals, tmyearpiece)
        
        
    # And get and write current club data unless told not to
    if not parms.skipclubs:
        url = "https://www.toastmasters.org/service/clubs/export/Downloads/Csv?district=%s&advanced=1&latitude=0&longitude=0" % clubdistrict
        clubdata = getresponse(url)
        if clubdata:
            with open(makefilename('clubs', today), 'w') as f:
                        f.write(''.join(clubdata).replace('\r',''))
     



