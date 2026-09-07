from app import correlation, patterns, scheduling

def test_emergency_squawk_transition_only_once():
    a={'abc123':{'icao':'abc123','callsign':'TEST1','squawk':'7700'}}
    first=patterns.check_squawk_7700(a)
    second=patterns.check_squawk_7700(a)
    assert len(first)==1 and first[0][1]=='CRITICAL'
    assert second==[]

def test_correlation_intersection():
    s={'satellites':{'SAT':{'subpoint_lat':0,'subpoint_lon':0,'_provenance':{'confidence':.9}}},'aircraft':{'A':{'lat':0.1,'lon':0.1,'_provenance':{'confidence':.8}}},'vessels':{}}
    c=correlation.correlate(s,max_distance_km=30)
    assert c and c[0]['domain']=='aircraft'

def test_station_selection():
    stations=[{'id':'A','online':True,'capabilities':['sdr'],'visibility_score':90,'load_pct':10,'link_quality':90,'priority':70},{'id':'B','online':True,'capabilities':['sdr'],'visibility_score':20,'load_pct':5,'link_quality':90,'priority':70}]
    assert scheduling.select_station(stations,['sdr'])['station']['id']=='A'

def test_risk_bounds():
    assert 0 <= correlation.risk_score('CRITICAL',1,3,5,4) <= 100
