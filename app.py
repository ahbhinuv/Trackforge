from flask import Flask, jsonify, request, render_template, redirect
from pathlib import Path
import sqlite3, threading, time, random
from datetime import datetime, timedelta

BASE = Path(__file__).resolve().parent
DB = BASE / "rail_drishti.db"
app = Flask(__name__, static_folder="static", template_folder="templates")

TRAINS = {
 "12301":{"number":"12301","name":"Rajdhani Express","origin":"Mumbai Central","destination":"New Delhi","delay":18,"confidence":82,"current_station":"Panipat","lat":29.3909,"lng":76.9635},
 "12002":{"number":"12002","name":"Shatabdi Express","origin":"New Delhi","destination":"Bhopal","delay":6,"confidence":91,"current_station":"Agra Cantt","lat":27.1574,"lng":77.9830},
 "12951":{"number":"12951","name":"Mumbai Rajdhani","origin":"Mumbai Central","destination":"New Delhi","delay":12,"confidence":86,"current_station":"Kota Junction","lat":25.2138,"lng":75.8648},
 "12424":{"number":"12424","name":"New Delhi Dibrugarh Rajdhani","origin":"New Delhi","destination":"Dibrugarh","delay":11,"confidence":78,"current_station":"Lucknow","lat":26.8467,"lng":80.9462}
}
STOPS = {
 "12301":[("Mumbai Central","10:25 AM","Actual · Departed"),("Surat","1:42 PM","Actual · +11 min"),("Panipat","5:41 PM","Current · +18 min"),("Karnal","5:58 PM","Expected · +19 min"),("Ambala Cantt","6:47 PM","Expected · +22 min"),("New Delhi","6:27 PM","Predicted terminal arrival")],
 "12002":[("New Delhi","6:00 AM","Actual · Departed"),("Agra Cantt","8:05 AM","Current · +6 min"),("Gwalior","9:18 AM","Expected · +6 min"),("Bhopal","2:05 PM","Predicted arrival")]
}
STATIONS=[{"name":"New Delhi","lat":28.6431,"lng":77.2197},{"name":"Panipat","lat":29.3909,"lng":76.9635},{"name":"Karnal","lat":29.6857,"lng":76.9905},{"name":"Ambala Cantt","lat":30.3684,"lng":76.8433},{"name":"Agra Cantt","lat":27.1574,"lng":77.9830},{"name":"Kota Junction","lat":25.2138,"lng":75.8648}]
CORRIDOR=[[19.076,72.8777],[21.17,72.8311],[23.2599,77.4126],[25.2138,75.8648],[27.1767,78.0081],[28.6431,77.2197]]

def init_db():
    con=sqlite3.connect(DB)
    con.execute("CREATE TABLE IF NOT EXISTS saved_journeys (id INTEGER PRIMARY KEY AUTOINCREMENT, train TEXT, label TEXT, alert_min INTEGER DEFAULT 5)")
    con.execute("CREATE TABLE IF NOT EXISTS passenger_reports (id INTEGER PRIMARY KEY AUTOINCREMENT, train TEXT, coach TEXT, category TEXT, description TEXT, location TEXT, created_at TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS journey_reviews (id INTEGER PRIMARY KEY AUTOINCREMENT, train TEXT, rating INTEGER, punctuality INTEGER, cleanliness INTEGER, comfort INTEGER, safety INTEGER, food INTEGER, staff INTEGER, comment TEXT, created_at TEXT)")
    con.commit();con.close()
init_db()

def eta_for(delay):
    # Demo: scheduled 6:00 PM plus current network impact; bounded for a believable prototype.
    mins=27 + (delay-18)
    return (datetime(2026,1,1,18,0)+timedelta(minutes=mins)).strftime("%-I:%M %p")

@app.get("/")
def home(): return render_template("index.html")

@app.get("/api/health")
def health(): return jsonify({"ok":True,"service":"Rail Drishti","mode":"Demo Live Data"})

@app.get("/api/trains")
def search():
    q=request.args.get("q","").lower().strip()
    out=[]
    for t in TRAINS.values():
        hay=f"{t['number']} {t['name']} {t['origin']} {t['destination']} {t['current_station']}".lower()
        if not q or q in hay:
            out.append({"number":t["number"],"name":t["name"],"origin":t["origin"],"destination":t["destination"],"current_station":t["current_station"],"delay_min":t["delay"],"predicted_arrival":eta_for(t["delay"])})
    return jsonify(out)

@app.get("/api/trains/<number>")
def train(number):
    t=TRAINS.get(number)
    if not t:return jsonify({"error":"Train not found"}),404
    return jsonify({"number":t["number"],"name":t["name"],"origin":t["origin"],"destination":t["destination"],"delay_min":t["delay"],"confidence":t["confidence"],"current_station":t["current_station"],"lat":t["lat"],"lng":t["lng"],"predicted_arrival":eta_for(t["delay"]),"stops":[{"station":s,"expected":e,"status":st,"current":s==t["current_station"]} for s,e,st in STOPS.get(number,[(t["origin"],"—","Demo route"),(t["current_station"],"Now","Current location"),(t["destination"],eta_for(t["delay"]),"Predicted arrival")])]})

@app.get("/api/network")
def network():
    trains=[]
    for t in TRAINS.values():
        trains.append({k:t[k] for k in ["number","name","current_station","lat","lng","delay"]}|{"delay_min":t["delay"],"predicted_arrival":eta_for(t["delay"])})
    return jsonify({"stations":STATIONS,"corridor":CORRIDOR,"trains":trains})

@app.get("/api/station/recommendation")
def recommendation():
    number = request.args.get("train", "12301").strip()
    t = TRAINS.get(number, TRAINS["12301"])
    station = t["destination"] + " Railway Station"
    alternatives = {
        "12301": {"station": "Panipat Junction", "distance_km": 94.0, "travel_time": 115, "train_stops": True, "departure_in_min": 28, "reason": "A practical alternative with a direct stop on the selected train's route."},
        "12002": {"station": "Agra Cantt Railway Station", "distance_km": 232.0, "travel_time": 285, "train_stops": True, "departure_in_min": 36, "reason": "The closest listed alternative station on the selected train's route."},
        "12951": {"station": "Panipat Junction", "distance_km": 94.0, "travel_time": 115, "train_stops": True, "departure_in_min": 31, "reason": "A practical alternative to New Delhi with route compatibility."},
        "12424": {"station": "Lucknow Charbagh", "distance_km": 4.8, "travel_time": 15, "train_stops": True, "departure_in_min": 24, "reason": "A nearby alternative station around the train's current Lucknow corridor."}
    }
    alt = alternatives.get(number, {"station": "Panipat Junction", "distance_km": 94.0, "travel_time": 115, "train_stops": True, "departure_in_min": 30, "reason": "A practical nearby alternative in the demo network."})
    return jsonify({
        "station": station, "distance_km": 2.4, "travel_time": 12, "train_stops": True, "departure_in_min": 42,
        "reason": f"Best demo match for {t['number']} — {t['name']}, balancing train compatibility and access.",
        "second_best": alt
    })


@app.get("/journey")
def journey_page():
    return redirect("/features")

@app.get("/api/journey/<number>")
def journey_status(number):
    t=TRAINS.get(number)
    if not t: return jsonify({"error":"Train not found"}),404
    # Demo tunnel section: GPS temporarily drops while the train is between two route points.
    tunnel = number == "12301" and t["current_station"] == "Panipat"
    gps = {"status":"Signal lost — tunnel mode","connected":False,"accuracy_m":None,"method":"dead-reckoning from last GPS fix"} if tunnel else {"status":"GPS connected","connected":True,"accuracy_m":8,"method":"GPS"}
    weather={
      "12301":{"condition":"Heavy rain","risk":"High","delay_risk_min":12,"message":"Heavy rainfall near the Delhi corridor may add delay."},
      "12002":{"condition":"Clear","risk":"Low","delay_risk_min":0,"message":"No significant weather-related disruption expected."},
      "12951":{"condition":"Cloudy","risk":"Medium","delay_risk_min":5,"message":"Cloud cover around Kota may cause minor operational slowdown."},
      "12424":{"condition":"Thunderstorms","risk":"Medium","delay_risk_min":8,"message":"Thunderstorms near Lucknow may affect the next section."}
    }.get(number,{"condition":"Clear","risk":"Low","delay_risk_min":0,"message":"No significant weather-related disruption expected."})
    con=sqlite3.connect(DB); rows=con.execute("SELECT category,COUNT(*) FROM passenger_reports WHERE train=? GROUP BY category ORDER BY COUNT(*) DESC",(number,)).fetchall(); con.close()
    reports=[{"category":r[0],"count":r[1]} for r in rows]
    return jsonify({"train":t,"gps":gps,"weather":weather,"reports":reports,"journey_health":{"score":82,"label":"Good","rating":4.2}})

@app.post("/api/reports")
def create_report():
    d=request.get_json(silent=True) or {}
    required=["train","coach","category","description"]
    if any(not str(d.get(k,"")).strip() for k in required): return jsonify({"error":"Train, coach, category and description are required."}),400
    now=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    con=sqlite3.connect(DB); cur=con.execute("INSERT INTO passenger_reports(train,coach,category,description,location,created_at) VALUES(?,?,?,?,?,?)",(d["train"],d["coach"],d["category"],d["description"],d.get("location","Current train location"),now)); con.commit(); rid=cur.lastrowid; con.close()
    return jsonify({"ok":True,"id":rid,"message":"Passenger report submitted successfully."}),201

@app.get("/api/reports")
def get_reports():
    train=request.args.get("train","")
    con=sqlite3.connect(DB)
    q="SELECT id,train,coach,category,description,location,created_at FROM passenger_reports"; args=()
    if train: q += " WHERE train=?"; args=(train,)
    q += " ORDER BY id DESC LIMIT 30"
    rows=con.execute(q,args).fetchall(); con.close()
    return jsonify([{"id":r[0],"train":r[1],"coach":r[2],"category":r[3],"description":r[4],"location":r[5],"created_at":r[6]} for r in rows])

@app.post("/api/reviews")
def create_review():
    d=request.get_json(silent=True) or {}
    try: rating=int(d.get("rating",0))
    except: rating=0
    if not d.get("train") or not 1<=rating<=5: return jsonify({"error":"Train and a 1–5 overall rating are required."}),400
    vals=[int(d.get(k, rating)) for k in ["punctuality","cleanliness","comfort","safety","food","staff"]]
    if any(not 1<=v<=5 for v in vals): return jsonify({"error":"All ratings must be between 1 and 5."}),400
    now=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    con=sqlite3.connect(DB); cur=con.execute("INSERT INTO journey_reviews(train,rating,punctuality,cleanliness,comfort,safety,food,staff,comment,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",(d["train"],rating,*vals,d.get("comment",""),now)); con.commit(); rid=cur.lastrowid; con.close()
    return jsonify({"ok":True,"id":rid,"message":"Thank you — your journey review was recorded."}),201

@app.get("/api/reviews/summary")
def review_summary():
    train=request.args.get("train","")
    con=sqlite3.connect(DB)
    q="SELECT COUNT(*),COALESCE(AVG(rating),0),COALESCE(AVG(cleanliness),0),COALESCE(AVG(comfort),0),COALESCE(AVG(safety),0) FROM journey_reviews"; args=()
    if train: q += " WHERE train=?"; args=(train,)
    row=con.execute(q,args).fetchone(); con.close()
    return jsonify({"reviews":row[0],"overall":round(row[1],1),"cleanliness":round(row[2],1),"comfort":round(row[3],1),"safety":round(row[4],1)})

@app.post("/api/guide")
def guide():
    data=request.get_json(silent=True) or {}; q=data.get("question","").lower()
    if "where" in q:return jsonify({"answer":"12301 is currently at Panipat, running 18 minutes late. The next scheduled stop is Karnal."})
    if "eta" in q or "reach" in q:return jsonify({"answer":"The predicted arrival at New Delhi is 6:27 PM, with 82% confidence. Terminal congestion is the biggest uncertainty."})
    if "station" in q:return jsonify({"answer":"New Delhi Railway Station is the best demo recommendation: 2.4 km away, about 12 minutes by road, and 12301 stops there."})
    if "late" in q:return jsonify({"answer":"Traffic ahead and terminal congestion are adding time. The demo prediction also expects about 9 minutes of recovery before arrival."})
    return jsonify({"answer":"I can help compare the demo trains by route, timing, current delay and predicted arrival."})

@app.get("/api/admin/overview")
def admin():
    causes={"12301":"Terminal congestion","12002":"Traffic ahead","12951":"Junction congestion","12424":"Weather"}
    rows=[]
    for t in TRAINS.values():
        rows.append({"number":t["number"],"name":t["name"],"eta":eta_for(t["delay"]),"priority":"High" if t["number"]=="12301" else "Normal","final_delay":t["delay"]+9 if t["number"]=="12301" else t["delay"],"confidence":t["confidence"],"cause":causes[t["number"]]})
    return jsonify({"terminal":"New Delhi","platforms":[{"number":1,"status":"Occupied"},{"number":2,"status":"Occupied"},{"number":3,"status":"Available in 8 min"},{"number":4,"status":"Occupied"}],"recommended_platform":3,"trains":rows})

@app.post("/api/journeys")
def save_journey():
    data=request.get_json(silent=True) or {}
    train=data.get("train","12301"); label=data.get("label","My Journey"); alert=int(data.get("alert_min",5))
    con=sqlite3.connect(DB); cur=con.execute("INSERT INTO saved_journeys(train,label,alert_min) VALUES(?,?,?)",(train,label,alert)); con.commit(); jid=cur.lastrowid; con.close()
    return jsonify({"id":jid,"train":train,"label":label,"alert_min":alert}),201

@app.get("/api/journeys")
def journeys():
    con=sqlite3.connect(DB); rows=con.execute("SELECT id,train,label,alert_min FROM saved_journeys ORDER BY id DESC").fetchall(); con.close()
    return jsonify([{"id":r[0],"train":r[1],"label":r[2],"alert_min":r[3]} for r in rows])

def demo_updater():
    random.seed(7)
    while True:
        time.sleep(12)
        # Small state changes keep the demo visibly alive; never claim this is live railway data.
        t=TRAINS["12301"]
        change=random.choice([-1,0,0,1,1])
        t["delay"]=max(15,min(31,t["delay"]+change))
        t["confidence"]=max(72,min(92,t["confidence"]+random.choice([-1,0,1])))
        t["lat"] += random.uniform(0.005,0.018)
        t["lng"] += random.uniform(-0.006,0.006)


# -------------------- Page routes --------------------
@app.route("/", methods=["GET"])
def home_page():
    return render_template("index.html", page="home")

@app.route("/track", methods=["GET"])
def track_page():
    return render_template("track.html", page="track")

@app.route("/network", methods=["GET"])
def network_page():
    return render_template("network.html", page="network")

@app.route("/station", methods=["GET"])
def station_page():
    return render_template("station.html", page="station")

@app.route("/guide", methods=["GET"])
def guide_page():
    return render_template("guide.html", page="guide")

@app.route("/about", methods=["GET"])
def about_page():
    return render_template("about.html", page="about")


# -------------------- Separate smart-feature pages --------------------
@app.get("/features")
def features_page():
    return render_template("features.html")

@app.get("/weather")
def weather_page():
    return render_template("weather.html")

@app.get("/gps")
def gps_page():
    return render_template("gps.html")

@app.get("/reports")
def reports_page():
    return render_template("reports.html")

@app.get("/review")
def review_page():
    return render_template("review.html")

@app.get("/api/weather/<number>")
def weather_api(number):
    if number not in TRAINS:
        return jsonify({"error":"Train not found"}),404
    data={
      "12301":{"condition":"Heavy rain","risk":"High","delay_risk_min":12,"message":"Heavy rainfall on the route can slow operations and station movement.","alert":True},
      "12002":{"condition":"Clear","risk":"Low","delay_risk_min":0,"message":"No significant weather-related disruption in the demo route.","alert":False},
      "12951":{"condition":"Cloudy","risk":"Medium","delay_risk_min":5,"message":"Cloudy conditions may create a small operational risk in the demo.","alert":True},
      "12424":{"condition":"Thunderstorms","risk":"Medium","delay_risk_min":8,"message":"Thunderstorms may affect the next section of the route.","alert":True}
    }
    return jsonify(data[number])

GPS_START=time.monotonic()
GPS_ROUTES={
 "12301":[("Mumbai Central",19.0760,72.8777),("Surat",21.1702,72.8311),("Kota Junction",25.2138,75.8648),("Panipat",29.3909,76.9635),("New Delhi",28.6431,77.2197)],
 "12002":[("New Delhi",28.6431,77.2197),("Agra Cantt",27.1574,77.9830),("Gwalior",26.2183,78.1828),("Bhopal",23.2599,77.4126)],
 "12951":[("Mumbai Central",19.0760,72.8777),("Kota Junction",25.2138,75.8648),("New Delhi",28.6431,77.2197)],
 "12424":[("New Delhi",28.6431,77.2197),("Lucknow",26.8467,80.9462),("Dibrugarh",27.4728,94.9120)]
}

def interpolate_route(points, progress):
    if progress<=0:return points[0]
    if progress>=1:return points[-1]
    x=progress*(len(points)-1); i=min(int(x),len(points)-2); f=x-i
    a,b=points[i],points[i+1]
    return (a[0],a[1]+(b[1]-a[1])*f,a[2]+(b[2]-a[2])*f)

@app.get("/api/gps/<number>")
def gps_api(number):
    if number not in TRAINS:return jsonify({"error":"Train not found"}),404
    # A repeatable moving demo: one full route every 90 seconds.
    progress=((time.monotonic()-GPS_START)%90)/90
    route=GPS_ROUTES[number]
    location,lat,lng=interpolate_route(route,progress)
    # Tunnel window is deliberately visible for ~20% of the cycle.
    tunnel=0.42<=progress<=0.62
    if tunnel:
        return jsonify({"location":location,"lat":lat,"lng":lng,"speed_kmph":82,"progress":round(progress*100,1),"gps":{"connected":False,"status":"GPS signal lost — tunnel mode","method":"Dead-reckoning from last GPS fix","accuracy_m":None},"message":"Tunnel detected. GPS is unavailable, so the app is estimating position until the signal returns."})
    return jsonify({"location":location,"lat":lat,"lng":lng,"speed_kmph":96,"progress":round(progress*100,1),"gps":{"connected":True,"status":"GPS connected","method":"GPS position feed","accuracy_m":8},"message":"GPS position received. The train marker is moving along the demo route."})


if __name__=="__main__":
    threading.Thread(target=demo_updater,daemon=True).start()
    app.run(host="0.0.0.0",port=5001,debug=False)
