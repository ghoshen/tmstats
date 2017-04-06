#!/usr/bin/env python
""" Creates the "Spring Forward" report """

import sys, csv
import tmparms, datetime
from tmutil import cleandate, UnicodeWriter, daybefore, stringify, isMonthFinal, haveDataFor, getMonthStart, getMonthEnd, dateAsWords, neaten

import tmglobals
globals = tmglobals.tmglobals()

def createResults(final, clubs):
    """ Returns a text string representing the clubs.  
        As a side effect, computes the award amount due for each club.
        Each club's name is enclosed in a span of class 'clubname'. """
    res = []
    for club in sorted(clubs, key=lambda club: club.clubname.lower()):
        htmlclass = 'clubname' + (' leader' if club.leader else '')
        club.amount = 5*club.growth
        if club.growth >= 5:
            club.amount += 25
        if final and club.leader:
            club.amount += 50
        res.append('<span class="clubname">%s%s%s</span> (%d, $%d)' % ('<i>' if club.leader else '', club.clubname, '</i>' if club.leader else '', club.growth, club.amount))
         
    return('<br>\n'.join(res))
   

class myclub:
    """ Just enough club info to sort the list nicely """
    def __init__(self, clubnumber, clubname, division, area, endnum, startnum, growth):
        self.area = area
        self.division = division
        self.clubnumber = clubnumber
        self.clubname = clubname
        self.growth = growth
        self.endnum = endnum
        self.startnum = startnum
        self.amount = 0
        self.leader = False


    def tablepart(self):
        return ('    <td>%s</td><td>%s</td>' % (self.area, self.clubname))

    def key(self):
        return '%s%2s%8s' % (self.division, self.area, self.clubnumber)



if __name__ == "__main__":

    # Handle parameters
    parms = tmparms.tmparms()
    parms.add_argument("--basedate", dest='basedate', default='M3')
    parms.add_argument("--finaldate", dest='finaldate', default='M5')
    parms.add_argument('--outfile', dest='outfile', default='springforward.txt')
    parms.add_argument('--csvfile', dest='csvfile', default='springforward.csv')
    
    # Do global setup
    globals.setup(parms)
    curs = globals.curs
    conn = globals.conn
    

    # See if we have the data needed to run and build the base part of the query
    if parms.basedate.upper().startswith('M'):
        basemonth = int(parms.basedate[1:])
        if not isMonthFinal(basemonth, curs):
            sys.exit(1)
        basepart = 'monthstart = "%s" AND entrytype = "M"' % getMonthStart(basemonth, curs)
        msgdate = getMonthEnd(basemonth)
        friendlybase = 'New Members on %s' % neaten(msgdate)
    else:
        basedate = cleandate(parms.basedate)
        if not haveDataFor(basedate, curs):
            sys.exit(1)
        basepart = 'asof = "%s"' % basedate
        msgdate = datetime.datetime.strptime(basedate, '%Y-%m-%d')
        friendlybase = 'New Members on %s' % neaten(msgdate)
    msgbase = dateAsWords(msgdate)

    # Figure out the end date and build that part of the query
    yesterday = cleandate('yesterday')
    if parms.finaldate.upper().startswith('M'):
        finalmonth = int(parms.finaldate[1:])
        msgdate = getMonthEnd(finalmonth)
        if isMonthFinal(finalmonth, curs):
            finalpart = 'monthstart = "%s" AND entrytype = "M"' % getMonthStart(finalmonth, curs)
            final = True
            reportdate = msgdate
        else:
            final = False
            finalpart = 'entrytype = "L"'
            reportdate = yesterday
    else:
        finaldate = cleandate(parms.finaldate)
        final = finaldate <= yesterday
        reportdate = min(finaldate,yesterday)
        finalpart = 'asof = "%s"' % min(reportdate)
        msgdate = datetime.datetime.strptime(finaldate, '%Y-%m-%d')
    if isinstance(reportdate,str):
    	reportdate = datetime.datetime.strptime(reportdate, '%Y-%m-%d')
    friendlyend = 'New Members on %s' % neaten(reportdate)
    msgfinal = dateAsWords(msgdate)


    # OK, now find clubs with 1 or more members added
    query = 'SELECT c.clubnumber, c.clubname, c.division, c.area, c.newmembers, b.newmembers FROM distperf c LEFT OUTER JOIN (SELECT clubnumber, newmembers FROM distperf WHERE %s) b ON b.clubnumber = c.clubnumber WHERE %s  ORDER BY c.division, c.area, c.clubnumber' % (basepart, finalpart)
    curs.execute(query)

    # Create the data for the output files.
    divmax = {}
    divisions = {}
    for (clubnumber, clubname, division, area, endnum, startnum) in curs.fetchall():
        if not startnum:
            startnum = 0      # Handle clubs added during the period
        growth = endnum - startnum

        if growth > 0:
            if division not in divisions:
                divmax[division] = 0
                divisions[division] = []
            divisions[division].append(myclub(clubnumber, clubname, division, area, endnum, startnum, growth))
            if growth > divmax[division]:
                divmax[division] = growth

    # Ensure that "Division 0D" doesn't have a leading club
    try:
        divmax['0D'] += 1
    except KeyError:
        pass
        
    

    # Open the output files
    clubfile = open(parms.outfile, 'w')

    clubfile.write("""
    <p>Clubs receive $5 in District Credit for every new member added after %s through %s.  Clubs adding five or more members receive an additional $25 in District Credit.</p>
    <p>The club or clubs in each division adding the most new members in that division will receive an additional $50 Credit; current leaders are italicized in the listing below.  These statistics are %s.</p>
    """ % (msgbase, msgfinal, 'final' if final else 'updated daily'))

    # And now, make a CSV with all of the information
    columns = ['Division', 'Area', 'Club Number', 'Club Name', 'Members Added', 'Amount Earned', 'Division Leader']
    fields = ['division', 'area', 'clubnumber', 'clubname', 'growth', 'amount', 'leader']
    csvfile = open(parms.csvfile, 'wb')
    writer = csv.DictWriter(csvfile, fieldnames=fields, extrasaction='ignore')
    csvfile.write(','.join(columns))
    csvfile.write('\n')

    for division in sorted(divisions.keys()):

        if division != '0D':
            # Mark the leader(s)
            for club in divisions[division]:
                club.leader = (club.growth == divmax[division])
               
        
            clubfile.write('<h4>Division %s</h4>\n' % division)
            clubfile.write('<p>%s.</p>\n' % createResults(final, divisions[division]))
            
            for club in sorted(divisions[division], key=lambda c: '%.2s%.2s%0.8d' % (c.division, c.area, c.clubnumber)):
                writer.writerow(club.__dict__)


    clubfile.close()
    csvfile.close()

        