# app_singapore_complete.py - With GPS Availability Handling
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import sqlite3
from datetime import datetime, timedelta
import socket
import re
import os
import threading
import time
import random
import hashlib

# =====================================================================
# Configuration
# =====================================================================
PORT = 8080
HOST = '0.0.0.0'
MEDIA_DIR = 'media_uploads'
os.makedirs(MEDIA_DIR, exist_ok=True)

# Time filter options (in hours)
TIME_FILTERS = {
    "30min": 0.5,
    "1hour": 1,
    "3hours": 3,
    "1day": 24,
    "3days": 72
}

# =====================================================================
# Database Setup
# =====================================================================
conn = sqlite3.connect('singapore_events.db', check_same_thread=False)
conn.execute("PRAGMA journal_mode=WAL")

# Create events table
conn.execute('''CREATE TABLE IF NOT EXISTS events
             (id TEXT PRIMARY KEY, 
              type TEXT, 
              title_en TEXT, 
              title_zh TEXT,
              msg_en TEXT, 
              msg_zh TEXT, 
              location TEXT, 
              location_zh TEXT,
              lat REAL DEFAULT 1.2902, 
              lon REAL DEFAULT 103.8519,
              user_id TEXT, 
              votes INTEGER DEFAULT 0, 
              responses TEXT DEFAULT '[]',
              media_paths TEXT DEFAULT '[]',
              created REAL, 
              source TEXT DEFAULT 'user')''')

# Create requests table for user requests
conn.execute('''CREATE TABLE IF NOT EXISTS requests
             (id TEXT PRIMARY KEY,
              user_id TEXT,
              title TEXT,
              title_zh TEXT,
              description TEXT,
              description_zh TEXT,
              location TEXT,
              location_zh TEXT,
              lat REAL,
              lon REAL,
              status TEXT DEFAULT 'open',
              responses TEXT DEFAULT '[]',
              created REAL,
              expires REAL)''')

conn.commit()

# =====================================================================
# Singapore Locations
# =====================================================================
SINGAPORE_LOCATIONS = {
    "Orchard Road": {"lat": 1.3039, "lon": 103.8317, "zh": "乌节路"},
    "Jurong East": {"lat": 1.3329, "lon": 103.7433, "zh": "裕廊东"},
    "Tampines": {"lat": 1.3521, "lon": 103.9454, "zh": "淡滨尼"},
    "Woodlands": {"lat": 1.4369, "lon": 103.7869, "zh": "兀兰"},
    "Bishan": {"lat": 1.3509, "lon": 103.8486, "zh": "碧山"},
    "City Hall": {"lat": 1.2931, "lon": 103.8519, "zh": "政府大厦"},
    "Marina Bay": {"lat": 1.2839, "lon": 103.8588, "zh": "滨海湾"},
    "Changi Airport": {"lat": 1.3592, "lon": 103.9885, "zh": "樟宜机场"},
    "Little India": {"lat": 1.3069, "lon": 103.8486, "zh": "小印度"},
    "Chinatown": {"lat": 1.2837, "lon": 103.8435, "zh": "牛车水"},
    "Punggol": {"lat": 1.4045, "lon": 103.9028, "zh": "榜鹅"},
    "Serangoon": {"lat": 1.3509, "lon": 103.8731, "zh": "实龙岗"},
    "JB Checkpoint": {"lat": 1.4566, "lon": 103.7645, "zh": "新山关卡"},
    "IMM Warehouse": {"lat": 1.3329, "lon": 103.7433, "zh": "IMM仓储"},
    "ION Orchard": {"lat": 1.3039, "lon": 103.8317, "zh": "爱雍乌节"},
    "Maxwell Food": {"lat": 1.2805, "lon": 103.8445, "zh": "麦士威熟食"}
}

# Default Singapore center coordinates
DEFAULT_LAT = 1.2902
DEFAULT_LON = 103.8519

 =====================================================================
# TikTok Mock Data Generator
# =====================================================================
def generate_tiktok_feed():
    """Generate mock TikTok-style crowd-sourced content"""
    tiktok_posts = [
        {
            "id": "tt_001",
            "type": "sighting",
            "title": "Crowd at Orchard Road",
            "title_zh": "乌节路人群聚集",
            "description": "Large crowd gathering at Orchard Road shopping belt, festive atmosphere! 🎉 #Singapore #Orchard",
            "description_zh": "乌节路购物带人群聚集，节日气氛浓厚！",
            "location": "Orchard Road",
            "author": "@sg_shopper",
            "likes": 1245,
            "shares": 89,
            "comments": 34,
            "verified": False,
            "timestamp": datetime.now().timestamp() * 1000 - 10 * 60 * 1000
        },
        {
            "id": "tt_002",
            "type": "alert",
            "title": "Flash Flood Warning",
            "title_zh": "突发洪水警报",
            "description": "Heavy rain causing flash flood at Bukit Timah! Avoid the area! 🌊 #Singapore #Flood",
            "description_zh": "武吉知马暴雨导致突发洪水，请避开该区域！",
            "location": "Bukit Timah",
            "author": "@sg_weather_watch",
            "likes": 3421,
            "shares": 567,
            "comments": 89,
            "verified": True,
            "timestamp": datetime.now().timestamp() * 1000 - 25 * 60 * 1000
        },
        {
            "id": "tt_003",
            "type": "traffic",
            "title": "Accident on PIE",
            "title_zh": "泛岛高速事故",
            "description": "Multi-vehicle accident on PIE towards Changi, heavy congestion 🚗💥 #SingaporeTraffic",
            "description_zh": "泛岛高速往樟宜方向多车事故，严重拥堵",
            "location": "PIE near Toa Payoh",
            "author": "@road_watcher",
            "likes": 892,
            "shares": 234,
            "comments": 45,
            "verified": False,
            "timestamp": datetime.now().timestamp() * 1000 - 45 * 60 * 1000
        }
    ]
    return tiktok_posts

# =====================================================================
# LTA Event Generators
# =====================================================================

def generate_unique_id(prefix, location, event_type, timestamp):
    unique_str = f"{prefix}_{location}_{event_type}_{timestamp}_{random.randint(1, 99999)}"
    return hashlib.md5(unique_str.encode()).hexdigest()[:16]

def generate_mock_bus_events(location_filter=None):
    events = []
    bus_data = [
        {"location": "Orchard Road", "bus": "190", "eta": "2 min", "load": "Seats Available"},
        {"location": "Jurong East", "bus": "51", "eta": "5 min", "load": "Standing Available"},
        {"location": "Tampines", "bus": "27", "eta": "3 min", "load": "Seats Available"},
        {"location": "Woodlands", "bus": "950", "eta": "8 min", "load": "Limited Standing"},
        {"location": "City Hall", "bus": "131", "eta": "4 min", "load": "Standing Available"},
    ]
    
    for item in bus_data:
        if location_filter and location_filter != "all" and item["location"] != location_filter:
            continue
        if item["location"] not in SINGAPORE_LOCATIONS:
            continue
            
        loc_info = SINGAPORE_LOCATIONS[item["location"]]
        timestamp = datetime.now().timestamp() * 1000
        
        events.append({
            "id": generate_unique_id("bus", item["location"], item["bus"], timestamp),
            "type": "bus",
            "title_en": f"Bus {item['bus']} Arriving",
            "title_zh": f"{item['bus']}路巴士即将到站",
            "msg_en": f"Bus {item['bus']} arriving at {item['location']} in {item['eta']}. Load: {item['load']}",
            "msg_zh": f"{item['bus']}路巴士将在{item['eta']}后到达，{item['load']}",
            "location": item["location"],
            "location_zh": loc_info["zh"],
            "lat": loc_info["lat"],
            "lon": loc_info["lon"],
            "source": "lta_bus",
            "created": timestamp
        })
    return events

def generate_mock_train_events(location_filter=None):
    events = []
    train_data = [
        {"location": "Jurong East", "line": "North South Line", "status": "Delay", 
         "msg": "Signal fault causing 10-15 min delay", "msg_zh": "信号故障导致10-15分钟延误"},
        {"location": "City Hall", "line": "East West Line", "status": "Minor Delay", 
         "msg": "Platform crowd causing minor delays", "msg_zh": "月台拥挤导致轻微延误"},
    ]
    
    for item in train_data:
        if location_filter and location_filter != "all" and item["location"] != location_filter:
            continue
        if item["location"] not in SINGAPORE_LOCATIONS:
            continue
            
        loc_info = SINGAPORE_LOCATIONS[item["location"]]
        timestamp = datetime.now().timestamp() * 1000
        
        events.append({
            "id": generate_unique_id("train", item["location"], item["line"], timestamp),
            "type": "train",
            "title_en": f"{item['line']} {item['status']}",
            "title_zh": f"{item['line']}{item['status']}",
            "msg_en": f"{item['line']}: {item['msg']} at {item['location']} station",
            "msg_zh": f"{item['line']}：{item['msg_zh']}，{item['location']}站",
            "location": item["location"],
            "location_zh": loc_info["zh"],
            "lat": loc_info["lat"],
            "lon": loc_info["lon"],
            "source": "lta_train",
            "created": timestamp
        })
    return events

def generate_mock_traffic_events(location_filter=None):
    events = []
    traffic_data = [
        {"location": "PIE near Toa Payoh", "type": "traffic", 
         "msg": "Accident on PIE towards Changi Airport, 2 lanes blocked", "msg_zh": "事故导致2条车道被堵"},
        {"location": "CTE Ang Mo Kio", "type": "traffic", 
         "msg": "Heavy traffic on CTE towards City, standstill conditions", "msg_zh": "严重拥堵"},
    ]
    
    for item in traffic_data:
        if location_filter and location_filter != "all" and item["location"] != location_filter:
            continue
        
        lat, lon = DEFAULT_LAT, DEFAULT_LON
        for key, val in SINGAPORE_LOCATIONS.items():
            if key in item["location"]:
                lat, lon = val["lat"], val["lon"]
                break
        
        timestamp = datetime.now().timestamp() * 1000
        
        events.append({
            "id": generate_unique_id("traffic", item["location"], item["type"], timestamp),
            "type": "traffic",
            "title_en": f"Traffic Alert",
            "title_zh": f"发生{item['type']}",
            "msg_en": item["msg"],
            "msg_zh": item["msg_zh"],
            "location": item["location"].split(" ")[0] if " " in item["location"] else item["location"],
            "location_zh": item["location"],
            "lat": lat,
            "lon": lon,
            "source": "lta_traffic",
            "created": timestamp
        })
    return events

def generate_mock_flood_events(location_filter=None):
    events = []
    flood_data = [
        {"location": "Bukit Timah", "msg": "Flash flood at Bukit Timah Road near Sixth Avenue", "msg_zh": "武吉知马路突发洪水"},
        {"location": "Orchard Road", "msg": "Heavy rain causing ponding on Orchard Road underpass", "msg_zh": "暴雨导致乌节路地下通道积水"},
    ]
    
    for item in flood_data:
        if location_filter and location_filter != "all" and item["location"] != location_filter:
            continue
        
        loc_info = SINGAPORE_LOCATIONS.get(item["location"], {"lat": DEFAULT_LAT, "lon": DEFAULT_LON, "zh": item["location"]})
        timestamp = datetime.now().timestamp() * 1000
        
        events.append({
            "id": generate_unique_id("flood", item["location"], "flood", timestamp),
            "type": "flood",
            "title_en": f"Flood Alert",
            "title_zh": f"洪水警报",
            "msg_en": item["msg"],
            "msg_zh": item["msg_zh"],
            "location": item["location"],
            "location_zh": loc_info.get("zh", item["location"]),
            "lat": loc_info["lat"],
            "lon": loc_info["lon"],
            "source": "lta_flood",
            "created": timestamp
        })
    return events

def generate_mock_crowd_events(location_filter=None):
    events = []
    crowd_data = [
        {"location": "City Hall", "level": "High", "msg": "City Hall MRT station experiencing high passenger traffic", "msg_zh": "乘客流量高"},
        {"location": "Orchard Road", "level": "High", "msg": "Large crowd gathering at Orchard Road shopping belt", "msg_zh": "人群聚集"},
    ]
    
    for item in crowd_data:
        if location_filter and location_filter != "all" and item["location"] != location_filter:
            continue
        if item["location"] not in SINGAPORE_LOCATIONS:
            continue
            
        loc_info = SINGAPORE_LOCATIONS[item["location"]]
        timestamp = datetime.now().timestamp() * 1000
        
        events.append({
            "id": generate_unique_id("crowd", item["location"], item["level"], timestamp),
            "type": "crowd",
            "title_en": f"{item['level']} Crowd Density at {item['location']}",
            "title_zh": f"{item['location']}人群密度{item['level']}",
            "msg_en": item["msg"],
            "msg_zh": item["msg_zh"],
            "location": item["location"],
            "location_zh": loc_info["zh"],
            "lat": loc_info["lat"],
            "lon": loc_info["lon"],
            "source": "lta_crowd",
            "created": timestamp
        })
    return events

def generate_mock_taxi_events(location_filter=None):
    events = []
    areas = ["Orchard Road", "Marina Bay", "Changi Airport", "Jurong East", "City Hall"]
    
    for area in areas:
        if location_filter and location_filter != "all" and area != location_filter:
            continue
        if area not in SINGAPORE_LOCATIONS:
            continue
            
        loc_info = SINGAPORE_LOCATIONS[area]
        taxi_count = random.randint(5, 30)
        timestamp = datetime.now().timestamp() * 1000
        
        events.append({
            "id": generate_unique_id("taxi", area, str(taxi_count), timestamp),
            "type": "taxi",
            "title_en": f"Taxi Availability in {area}",
            "title_zh": f"{area}德士供应情况",
            "msg_en": f"Approximately {taxi_count} taxis available near {area}",
            "msg_zh": f"{area}附近约有{taxi_count}辆德士",
            "location": area,
            "location_zh": loc_info["zh"],
            "lat": loc_info["lat"],
            "lon": loc_info["lon"],
            "source": "lta_taxi",
            "created": timestamp
        })
    return events

def generate_all_lta_events(category=None, location=None):
    events = []
    generators = {
        "bus": generate_mock_bus_events,
        "train": generate_mock_train_events,
        "traffic": generate_mock_traffic_events,
        "flood": generate_mock_flood_events,
        "crowd": generate_mock_crowd_events,
        "taxi": generate_mock_taxi_events,
    }
    
    if category and category in generators:
        events = generators[category](location)
    else:
        for gen in generators.values():
            events.extend(gen(location))
    
    return events

def save_events_to_db(events):
    if not events:
        return 0
    
    saved = 0
    for event in events:
        try:
            cursor = conn.execute("""
                SELECT id FROM events 
                WHERE source = ? AND location = ? AND type = ? 
                AND created > ? LIMIT 1
            """, (event['source'], event['location'], event['type'], event['created'] - 30 * 60 * 1000))
            
            if cursor.fetchone():
                continue
            
            conn.execute("""
                INSERT INTO events 
                (id, type, title_en, title_zh, msg_en, msg_zh, 
                 location, location_zh, lat, lon, source, created, votes, responses, media_paths)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (event['id'], event['type'], event['title_en'], event['title_zh'],
                  event['msg_en'], event['msg_zh'], event['location'], event['location_zh'],
                  event['lat'], event['lon'], event['source'], event['created'], 0, '[]', '[]'))
            saved += 1
        except Exception as e:
            continue
    
    conn.commit()
    return saved

def lta_poller():
    print("🔄 LTA event generator started")
    poll_count = 0
    
    while True:
        try:
            poll_count += 1
            categories = ["bus", "train", "traffic", "flood", "crowd", "taxi"]
            category = categories[poll_count % len(categories)]
            events = generate_all_lta_events(category, None)
            saved = save_events_to_db(events)
            if saved > 0:
                print(f"✅ Generated {saved} {category} events")
        except Exception as e:
            print(f"❌ LTA error: {e}")
        time.sleep(90)

# =====================================================================
# Cleanup old data
# =====================================================================
def cleanup_old_data():
    """Delete events older than 3 days"""
    while True:
        time.sleep(3600)
        cutoff_3days = datetime.now().timestamp() * 1000 - 3 * 24 * 3600 * 1000
        
        deleted_events = conn.execute("DELETE FROM events WHERE created < ?", (cutoff_3days,)).rowcount
        deleted_requests = conn.execute("DELETE FROM requests WHERE created < ?", (cutoff_3days,)).rowcount
        
        # Clean up old media files
        for filename in os.listdir(MEDIA_DIR):
            filepath = os.path.join(MEDIA_DIR, filename)
            try:
                if os.path.getmtime(filepath) < time.time() - 3 * 24 * 3600:
                    os.remove(filepath)
            except:
                pass
        
        conn.commit()
        if deleted_events > 0 or deleted_requests > 0:
            print(f"🧹 Cleaned {deleted_events} events, {deleted_requests} requests")

# =====================================================================
# HTML Template - With GPS Availability Handling
# =====================================================================
HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes">
    <title>3rd Eye Singapore</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0a0a;
            color: #fff;
            max-width: 500px;
            margin: 0 auto;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 16px;
            text-align: center;
        }
        .header h1 { font-size: 20px; }
        #map {
            height: 250px;
            width: 100%;
            z-index: 1;
        }
        .tabs {
            display: flex;
            background: #1a1a2e;
            padding: 8px;
            gap: 8px;
        }
        .tab-btn {
            flex: 1;
            padding: 10px;
            background: #16213e;
            border: none;
            color: #fff;
            cursor: pointer;
            border-radius: 8px;
            font-size: 13px;
        }
        .tab-btn.active {
            background: #667eea;
        }
        .panel {
            display: none;
            flex: 1;
            overflow-y: auto;
            padding: 12px;
        }
        .panel.active {
            display: block;
        }
        
        /* Feed Card - Horizontal Layout with fixed media size */
        .feed-card {
            background: #1a1a2e;
            border-radius: 12px;
            margin-bottom: 12px;
            border-left: 3px solid #667eea;
            display: flex;
            flex-direction: row;
            overflow: hidden;
            cursor: pointer;
            transition: transform 0.1s;
        }
        .feed-card:active { transform: scale(0.98); }
        .feed-card.request { border-left-color: #f39c12; }
        .feed-card.alert { border-left-color: #e74c3c; }
        
        /* Media section - fixed 100x100 size for both images and videos */
        .feed-media {
            width: 100px;
            height: 100px;
            flex-shrink: 0;
            background: #0f0f1a;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }
        .feed-media img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        .feed-media video {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        .feed-media .no-media {
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #16213e;
            color: #888;
            font-size: 32px;
        }
        
        /* Content section - takes remaining space */
        .feed-content {
            flex: 1;
            padding: 10px;
            display: flex;
            flex-direction: column;
            gap: 6px;
            min-width: 0;
        }
        .feed-location {
            font-weight: bold;
            font-size: 14px;
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 6px;
        }
        .feed-desc {
            font-size: 12px;
            color: #ccc;
            line-height: 1.3;
            overflow: hidden;
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
        }
        .feed-meta {
            font-size: 10px;
            color: #888;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 9px;
            font-weight: 600;
        }
        .badge-lta { background: #667eea; }
        .badge-user { background: #2ecc71; }
        .badge-request { background: #f39c12; }
        .no-gps-badge {
            background: #e74c3c;
            color: white;
            font-size: 8px;
            padding: 2px 6px;
            border-radius: 10px;
            margin-left: 6px;
        }
        
        .form-group { margin-bottom: 16px; }
        label {
            display: block;
            font-size: 12px;
            margin-bottom: 6px;
            color: #aaa;
        }
        input, textarea, select {
            width: 100%;
            padding: 12px;
            background: #1a1a2e;
            border: 1px solid #333;
            border-radius: 8px;
            color: #fff;
            font-size: 14px;
        }
        button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: bold;
            cursor: pointer;
            width: 100%;
        }
        button:active { transform: scale(0.98); }
        .media-zone {
            border: 2px dashed #333;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
            cursor: pointer;
            background: #1a1a2e;
            margin: 12px 0;
        }
        .thumb-row { display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap; }
        .thumb {
            position: relative;
            width: 80px;
            height: 80px;
            border-radius: 8px;
            overflow: hidden;
            background: #333;
        }
        .thumb img { width: 100%; height: 100%; object-fit: cover; }
        .thumb-x {
            position: absolute;
            top: -8px;
            right: -8px;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            background: #e74c3c;
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            cursor: pointer;
        }
        .empty { text-align: center; padding: 40px; color: #888; }
        .toast {
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: #333;
            padding: 10px 20px;
            border-radius: 8px;
            z-index: 1000;
            animation: fadeOut 2s ease;
        }
        @keyframes fadeOut {
            0% { opacity: 0; transform: translateX(-50%) translateY(20px); }
            15% { opacity: 1; transform: translateX(-50%) translateY(0); }
            85% { opacity: 1; }
            100% { opacity: 0; transform: translateX(-50%) translateY(-20px); }
        }
        .filter-row {
            display: flex;
            gap: 8px;
            margin-bottom: 12px;
            overflow-x: auto;
        }
        .filter-chip {
            padding: 6px 14px;
            background: #1a1a2e;
            border: none;
            border-radius: 20px;
            color: #fff;
            font-size: 12px;
            cursor: pointer;
        }
        .filter-chip.active {
            background: #667eea;
        }
        .lta-dropdown {
            margin-bottom: 12px;
        }
        .lta-dropdown select {
            background: #1a1a2e;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 10px;
            color: #fff;
            font-size: 14px;
            cursor: pointer;
            width: 100%;
        }
        .gps-warning {
            position: fixed;
            bottom: 80px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(231, 76, 60, 0.9);
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 11px;
            z-index: 1000;
            white-space: nowrap;
            pointer-events: none;
            animation: fadeOut 2s ease;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>👁️ 3RD EYE · Singapore</h1>
    </div>
    
    <div id="map"></div>
    
    <div class="tabs">
        <button class="tab-btn active" data-tab="feed">📡 Feed</button>
        <button class="tab-btn" data-tab="post">📸 Post</button>
        <button class="tab-btn" data-tab="requests">📋 Requests</button>
        <button class="tab-btn" data-tab="lta">🏛️ LTA</button>
    </div>
    
    <div id="feed-panel" class="panel active">
        <div class="filter-row">
            <button class="filter-chip active" data-filter="all">All</button>
            <button class="filter-chip" data-filter="sighting">Sightings</button>
            <button class="filter-chip" data-filter="alert">Alerts</button>
            <button class="filter-chip" data-filter="request">Requests</button>
        </div>
        <div id="feed-list"></div>
    </div>
    
    <div id="post-panel" class="panel">
        <div class="form-group">
            <label>📍 Location</label>
            <input type="text" id="post-location" placeholder="e.g., Orchard Road, JB Checkpoint">
        </div>
        <div class="form-group">
            <label>📝 Description</label>
            <textarea id="post-desc" rows="3" placeholder="What's happening? Queue length, wait time..."></textarea>
        </div>
        <div class="form-group">
            <label>🏷️ Type</label>
            <select id="post-type">
                <option value="sighting">👁 Sighting</option>
                <option value="alert">🚨 Alert</option>
            </select>
        </div>
        <div class="media-zone" id="media-zone">
            📸 Tap to add photo or video
            <input type="file" id="media-input" accept="image/*,video/*" style="display:none">
        </div>
        <div id="preview-row" class="thumb-row" style="display:none;"></div>
        <button id="publish-btn">Publish Intel</button>
    </div>
    
    <div id="requests-panel" class="panel">
        <div class="form-group">
            <label>📍 Location</label>
            <input type="text" id="req-location" placeholder="e.g., Jewel Changi, ION Orchard">
        </div>
        <div class="form-group">
            <label>📋 What do you want to know?</label>
            <textarea id="req-desc" rows="2" placeholder="e.g., How long is the queue now?"></textarea>
        </div>
        <button id="create-req-btn">Post Request</button>
        <div style="margin-top: 20px;">
            <h4 style="margin-bottom: 12px;">Active Requests</h4>
            <div id="requests-list"></div>
        </div>
    </div>
    
    <div id="lta-panel" class="panel">
        <div class="lta-dropdown">
            <select id="lta-category">
                <option value="all">🏛️ All LTA Updates</option>
                <option value="bus">🚌 Bus Arrivals</option>
                <option value="train">🚇 Train Alerts</option>
                <option value="traffic">🚗 Traffic Incidents</option>
                <option value="flood">🌊 Flood Alerts</option>
                <option value="crowd">👥 Crowd Density</option>
                <option value="taxi">🚕 Taxi Availability</option>
            </select>
        </div>
        <div id="lta-list"></div>
    </div>

<script>
    let map = null;
    let markers = {};
    let currentFilter = 'all';
    let selectedFile = null;
    let currentUser = 'user_' + Math.random().toString(36).substr(2, 8);
    const DEFAULT_LAT = 1.2902;
    const DEFAULT_LON = 103.8519;
    
    function initMap() {
        map = L.map('map').setView([DEFAULT_LAT, DEFAULT_LON], 12);
        L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
            subdomains: 'abcd',
            maxZoom: 19,
            minZoom: 11
        }).addTo(map);
    }
    
    // Function to show GPS warning
    function showGPSWarning() {
        let warning = document.createElement('div');
        warning.className = 'gps-warning';
        warning.textContent = '⚠️ No GPS available for this location. Showing Singapore map.';
        document.body.appendChild(warning);
        setTimeout(() => warning.remove(), 2500);
    }
    
    // Function to check if coordinates are valid (not default)
    function hasValidGPS(lat, lon) {
        return lat && lon && lat !== DEFAULT_LAT && lon !== DEFAULT_LON && 
               Math.abs(lat - DEFAULT_LAT) > 0.001 && Math.abs(lon - DEFAULT_LON) > 0.001;
    }
    
    // Function to pan map to a location
    function panToLocation(lat, lon, locationName, hasGPS) {
        if (!map) initMap();
        
        if (hasGPS && lat && lon && lat !== DEFAULT_LAT && lon !== DEFAULT_LON) {
            map.setView([lat, lon], 15);
            L.popup()
                .setLatLng([lat, lon])
                .setContent(`📍 <b>${locationName}</b><br><small>GPS available</small>`)
                .openOn(map);
        } else {
            // No GPS - show default Singapore map
            map.setView([DEFAULT_LAT, DEFAULT_LON], 12);
            L.popup()
                .setLatLng([DEFAULT_LAT, DEFAULT_LON])
                .setContent(`📍 <b>Singapore Map</b><br><small>No GPS data for "${locationName}"</small>`)
                .openOn(map);
            showGPSWarning();
        }
    }
    
    function updateMarkers(events) {
        if (!map) initMap();
        Object.keys(markers).forEach(id => map.removeLayer(markers[id]));
        markers = {};
        
        events.forEach(e => {
            if (hasValidGPS(e.lat, e.lon)) {
                let color = e.type === 'alert' ? '#e74c3c' : (e.type === 'request' ? '#f39c12' : '#2ecc71');
                let icon = L.divIcon({
                    html: `<div style="background:${color}; width:12px; height:12px; border-radius:50%; border:2px solid white; box-shadow:0 0 4px rgba(0,0,0,0.5);"></div>`,
                    iconSize: [12, 12],
                    className: 'custom-marker'
                });
                let marker = L.marker([e.lat, e.lon], { icon: icon })
                    .bindPopup(`<b>${e.location || e.loc}</b><br>${(e.msg_en || e.title_en || '').substring(0, 80)}<br><small>✓ GPS available</small>`);
                marker.addTo(map);
                markers[e.id] = marker;
            }
        });
    }
    
    function showToast(msg) {
        let toast = document.createElement('div');
        toast.className = 'toast';
        toast.textContent = msg;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 2000);
    }
    
    function formatTime(timestamp) {
        let diff = Date.now() - timestamp;
        if (diff < 60000) return 'just now';
        if (diff < 3600000) return Math.floor(diff/60000) + ' min ago';
        if (diff < 86400000) return Math.floor(diff/3600000) + ' hours ago';
        return new Date(timestamp).toLocaleDateString();
    }
    
    function loadFeed() {
        fetch('/api/events?time=3days&category=all&location=all')
            .then(r => r.json())
            .then(events => {
                let filtered = events;
                if (currentFilter !== 'all') {
                    filtered = events.filter(e => e.type === currentFilter);
                }
                filtered.sort((a,b) => b.created - a.created);
                let container = document.getElementById('feed-list');
                if (!filtered.length) {
                    container.innerHTML = '<div class="empty">✨ No posts yet. Be the first!</div>';
                    return;
                }
                container.innerHTML = filtered.map(e => {
                    let badgeClass = e.source === 'lta' ? 'badge-lta' : (e.type === 'request' ? 'badge-request' : 'badge-user');
                    let badgeText = e.source === 'lta' ? 'LTA' : (e.type === 'request' ? 'REQUEST' : (e.type === 'alert' ? 'ALERT' : 'SIGHTING'));
                    let hasGPS = hasValidGPS(e.lat, e.lon);
                    let gpsBadge = hasGPS ? '<span class="no-gps-badge" style="background:#2ecc71;">📍 GPS</span>' : '<span class="no-gps-badge">⚠️ No GPS</span>';
                    
                    let mediaHtml = '';
                    if (e.media_paths && e.media_paths.length) {
                        let m = e.media_paths[0];
                        if (m.type === 'photo') {
                            mediaHtml = `<div class="feed-media"><img src="/media/${m.path}" onclick="event.stopPropagation()"></div>`;
                        } else if (m.type === 'video') {
                            mediaHtml = `<div class="feed-media"><video src="/media/${m.path}" controls onclick="event.stopPropagation()"></video></div>`;
                        }
                    } else {
                        mediaHtml = `<div class="feed-media"><div class="no-media">📷</div></div>`;
                    }
                    
                    let locationName = e.location || e.loc || 'Singapore';
                    let lat = e.lat || DEFAULT_LAT;
                    let lon = e.lon || DEFAULT_LON;
                    
                    return `
                        <div class="feed-card ${e.type}" onclick="panToLocation(${lat}, ${lon}, '${locationName.replace(/'/g, "\\'")}', ${hasGPS})">
                            ${mediaHtml}
                            <div class="feed-content">
                                <div class="feed-location">
                                    📍 ${locationName}
                                    ${gpsBadge}
                                    <span class="badge ${badgeClass}">${badgeText}</span>
                                </div>
                                <div class="feed-desc">${(e.msg_en || e.title_en || '').substring(0, 150)}</div>
                                <div class="feed-meta">
                                    <span>🕒 ${formatTime(e.created)}</span>
                                    <span>👍 ${e.votes || 0}</span>
                                    <span>👤 ${e.source === 'lta' ? 'LTA' : 'User'}</span>
                                </div>
                            </div>
                        </div>
                    `;
                }).join('');
                updateMarkers(filtered);
            })
            .catch(err => console.error('Feed error:', err));
    }
    
    function loadLTA() {
        let category = document.getElementById('lta-category').value;
        fetch('/api/lta?category=' + category + '&location=all')
            .then(r => r.json())
            .then(events => {
                let container = document.getElementById('lta-list');
                if (!events.length) {
                    container.innerHTML = '<div class="empty">No LTA updates for this category</div>';
                    return;
                }
                container.innerHTML = events.map(e => {
                    let icon = '';
                    if (e.type === 'bus') icon = '🚌';
                    else if (e.type === 'train') icon = '🚇';
                    else if (e.type === 'traffic') icon = '🚗';
                    else if (e.type === 'flood') icon = '🌊';
                    else if (e.type === 'crowd') icon = '👥';
                    else if (e.type === 'taxi') icon = '🚕';
                    else icon = '🏛️';
                    
                    let hasGPS = hasValidGPS(e.lat, e.lon);
                    let lat = e.lat || DEFAULT_LAT;
                    let lon = e.lon || DEFAULT_LON;
                    let locationName = e.location || 'Singapore';
                    
                    return `
                        <div class="feed-card" onclick="panToLocation(${lat}, ${lon}, '${locationName.replace(/'/g, "\\'")}', ${hasGPS})">
                            <div class="feed-media"><div class="no-media">${icon}</div></div>
                            <div class="feed-content">
                                <div class="feed-location">
                                    ${e.title_en || e.type.toUpperCase()}
                                    ${hasGPS ? '<span class="no-gps-badge" style="background:#2ecc71;">📍 GPS</span>' : '<span class="no-gps-badge">⚠️ No GPS</span>'}
                                    <span class="badge badge-lta">LTA</span>
                                </div>
                                <div class="feed-desc">${e.msg_en || ''}</div>
                                <div class="feed-meta">📍 ${locationName}</div>
                            </div>
                        </div>
                    `;
                }).join('');
            });
    }
    
    function loadRequests() {
        fetch('/api/requests?time=3days&location=all')
            .then(r => r.json())
            .then(requests => {
                let container = document.getElementById('requests-list');
                if (!requests.length) {
                    container.innerHTML = '<div class="empty">No active requests</div>';
                    return;
                }
                container.innerHTML = requests.map(r => {
                    let hasGPS = hasValidGPS(r.lat, r.lon);
                    let lat = r.lat || DEFAULT_LAT;
                    let lon = r.lon || DEFAULT_LON;
                    let locationName = r.location || 'Singapore';
                    return `
                        <div class="feed-card request" onclick="panToLocation(${lat}, ${lon}, '${locationName.replace(/'/g, "\\'")}', ${hasGPS})">
                            <div class="feed-media"><div class="no-media">📡</div></div>
                            <div class="feed-content">
                                <div class="feed-location">
                                    ${r.title || 'Information Request'}
                                    ${hasGPS ? '<span class="no-gps-badge" style="background:#2ecc71;">📍 GPS</span>' : '<span class="no-gps-badge">⚠️ No GPS</span>'}
                                </div>
                                <div class="feed-desc">📍 ${locationName}<br>${r.description || ''}</div>
                                <div class="feed-meta">🕒 ${formatTime(r.created)}</div>
                            </div>
                        </div>
                    `;
                }).join('');
            });
    }
    
    function publishPost() {
        let location = document.getElementById('post-location').value.trim();
        let desc = document.getElementById('post-desc').value.trim();
        let type = document.getElementById('post-type').value;
        
        if (!location) { showToast('Please enter a location'); return; }
        if (!desc && !selectedFile) { showToast('Please add a description or media'); return; }
        
        let formData = new FormData();
        formData.append('loc', location);
        formData.append('type', type);
        formData.append('titleEn', desc.substring(0, 100));
        formData.append('msgEn', desc);
        formData.append('userId', currentUser);
        if (selectedFile) {
            formData.append('media', selectedFile);
        }
        
        fetch('/api/events', { method: 'POST', body: formData })
            .then(res => res.json())
            .then(() => {
                showToast('✅ Published!');
                document.getElementById('post-location').value = '';
                document.getElementById('post-desc').value = '';
                clearMedia();
                loadFeed();
                document.querySelector('[data-tab="feed"]').click();
            })
            .catch(() => showToast('Failed to publish'));
    }
    
    function createRequest() {
        let location = document.getElementById('req-location').value.trim();
        let desc = document.getElementById('req-desc').value.trim();
        
        if (!location) { showToast('Please enter a location'); return; }
        
        fetch('/api/requests', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                location: location,
                title: desc.substring(0, 100) || 'Queue Information',
                description: desc,
                userId: currentUser
            })
        })
        .then(res => res.json())
        .then(() => {
            showToast('✅ Request posted!');
            document.getElementById('req-location').value = '';
            document.getElementById('req-desc').value = '';
            loadRequests();
            loadFeed();
            document.querySelector('[data-tab="feed"]').click();
        })
        .catch(() => showToast('Failed to post request'));
    }
    
    function clearMedia() {
        selectedFile = null;
        document.getElementById('preview-row').style.display = 'none';
        document.getElementById('preview-row').innerHTML = '';
        document.getElementById('media-input').value = '';
    }
    
    // Setup media upload
    document.getElementById('media-zone').onclick = () => document.getElementById('media-input').click();
    document.getElementById('media-input').onchange = (e) => {
        let file = e.target.files[0];
        if (!file) return;
        selectedFile = file;
        let reader = new FileReader();
        reader.onload = (ev) => {
            let preview = document.getElementById('preview-row');
            preview.style.display = 'flex';
            preview.innerHTML = `<div class="thumb"><img src="${ev.target.result}"><div class="thumb-x" onclick="clearMedia()">✕</div></div>`;
        };
        reader.readAsDataURL(file);
    };
    
    // Tab switching
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.onclick = () => {
            let tabId = btn.dataset.tab;
            document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
            document.getElementById(`${tabId}-panel`).classList.add('active');
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            if (tabId === 'feed') loadFeed();
            if (tabId === 'requests') loadRequests();
            if (tabId === 'lta') loadLTA();
        };
    });
    
    // Filter chips
    document.querySelectorAll('.filter-chip').forEach(chip => {
        chip.onclick = () => {
            document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            currentFilter = chip.dataset.filter;
            loadFeed();
        };
    });
    
    // LTA dropdown change
    document.getElementById('lta-category').onchange = () => loadLTA();
    
    document.getElementById('publish-btn').onclick = publishPost;
    document.getElementById('create-req-btn').onclick = createRequest;
    
    // Initialize
    initMap();
    loadFeed();
    loadLTA();
    loadRequests();
    
    setInterval(() => {
        if (document.getElementById('feed-panel').classList.contains('active')) loadFeed();
    }, 30000);
</script>
</body>
</html>
'''

# =====================================================================
# HTTP Handler
# =====================================================================
class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode('utf-8'))
        
        elif self.path.startswith('/api/events'):
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            params = {}
            if '?' in self.path:
                query = self.path.split('?')[1]
                for p in query.split('&'):
                    if '=' in p:
                        k, v = p.split('=', 1)
                        params[k] = v
            
            time_filter = params.get('time', '3days')
            category = params.get('category', 'all')
            location = params.get('location', 'all')
            
            time_map = {'30min': 0.5, '1hour': 1, '3hours': 3, '1day': 24, '3days': 72}
            hours = time_map.get(time_filter, 72)
            cutoff = datetime.now().timestamp() * 1000 - hours * 3600 * 1000
            
            query_sql = "SELECT id, type, title_en, title_zh, msg_en, msg_zh, location, location_zh, lat, lon, source, votes, media_paths, created FROM events WHERE created > ?"
            query_params = [cutoff]
            
            if category != 'all' and category != 'lta':
                query_sql += " AND type = ?"
                query_params.append(category)
            
            if location != 'all':
                query_sql += " AND location = ?"
                query_params.append(location)
            
            query_sql += " ORDER BY created DESC LIMIT 500"
            
            cursor = conn.execute(query_sql, query_params)
            
            events = []
            for row in cursor.fetchall():
                events.append({
                    "id": row[0], "type": row[1],
                    "title_en": row[2] or '', "title_zh": row[3] or '',
                    "msg_en": row[4] or '', "msg_zh": row[5] or '',
                    "location": row[6] or 'Singapore', "loc": row[6] or 'Singapore',
                    "location_zh": row[7] or '新加坡',
                    "lat": row[8] or DEFAULT_LAT, "lon": row[9] or DEFAULT_LON,
                    "source": row[10] or 'user', "votes": row[11] or 0,
                    "media_paths": json.loads(row[12]) if row[12] else [],
                    "created": row[13]
                })
            
            self.wfile.write(json.dumps(events).encode())
        
        elif self.path.startswith('/api/requests'):
            params = {}
            if '?' in self.path:
                query = self.path.split('?')[1]
                for p in query.split('&'):
                    if '=' in p:
                        k, v = p.split('=', 1)
                        params[k] = v
            
            path_parts = self.path.split('/')
            if len(path_parts) > 3 and path_parts[3]:
                request_id = path_parts[3]
                cursor = conn.execute("SELECT * FROM requests WHERE id = ?", (request_id,))
                row = cursor.fetchone()
                if row:
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "id": row[0], "userId": row[1], "title": row[2],
                        "description": row[4], "location": row[6],
                        "lat": row[8] or DEFAULT_LAT, "lon": row[9] or DEFAULT_LON,
                        "status": row[10], "responses": json.loads(row[11]) if row[11] else [],
                        "created": row[12]
                    }).encode())
                return
            
            time_filter = params.get('time', '3days')
            location = params.get('location', 'all')
            
            time_map = {'30min': 0.5, '1hour': 1, '3hours': 3, '1day': 24, '3days': 72}
            hours = time_map.get(time_filter, 72)
            cutoff = datetime.now().timestamp() * 1000 - hours * 3600 * 1000
            
            query_sql = "SELECT * FROM requests WHERE status = 'open' AND created > ?"
            query_params = [cutoff]
            
            if location != 'all':
                query_sql += " AND location = ?"
                query_params.append(location)
            
            query_sql += " ORDER BY created DESC LIMIT 100"
            
            cursor = conn.execute(query_sql, query_params)
            
            requests_list = []
            for row in cursor.fetchall():
                requests_list.append({
                    "id": row[0], "userId": row[1], "title": row[2],
                    "description": row[4], "location": row[6],
                    "lat": row[8] or DEFAULT_LAT, "lon": row[9] or DEFAULT_LON,
                    "status": row[10], "responses": json.loads(row[11]) if row[11] else [],
                    "created": row[12]
                })
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(requests_list).encode())
        
        elif self.path.startswith('/api/lta'):
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            params = {}
            if '?' in self.path:
                query = self.path.split('?')[1]
                for p in query.split('&'):
                    if '=' in p:
                        k, v = p.split('=', 1)
                        params[k] = v
            
            category = params.get('category', 'all')
            location = params.get('location', 'all')
            
            lta_events = generate_all_lta_events(category if category != 'all' else None, location if location != 'all' else None)
            
            self.wfile.write(json.dumps(lta_events).encode())
        
        elif self.path.startswith('/media/'):
            filename = self.path.split('/')[-1]
            filepath = os.path.join(MEDIA_DIR, filename)
            if os.path.exists(filepath):
                self.send_response(200)
                if filename.endswith(('.mp4', '.mov', '.webm', '.avi', '.mp4', '.m4v')):
                    self.send_header('Content-type', 'video/mp4')
                elif filename.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                    self.send_header('Content-type', 'image/jpeg')
                else:
                    self.send_header('Content-type', 'application/octet-stream')
                self.end_headers()
                with open(filepath, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/api/events':
            try:
                content_type = self.headers.get('Content-Type', '')
                
                if 'multipart/form-data' in content_type:
                    # Parse multipart form data manually
                    content_length = int(self.headers['Content-Length'])
                    post_data = self.rfile.read(content_length)
                    
                    # Get boundary
                    boundary = content_type.split('boundary=')[1].encode()
                    parts = post_data.split(boundary)
                    
                    form_data = {}
                    media_files = []
                    
                    for part in parts:
                        if b'Content-Disposition: form-data' not in part:
                            continue
                        
                        # Parse field name
                        name_match = re.search(b'name="([^"]+)"', part)
                        if not name_match:
                            continue
                        field_name = name_match.group(1).decode()
                        
                        # Check if it's a file
                        if b'filename=' in part:
                            filename_match = re.search(b'filename="([^"]+)"', part)
                            if filename_match:
                                # Find file data
                                file_start = part.find(b'\r\n\r\n')
                                if file_start != -1:
                                    file_start += 4
                                    # Find end of file data
                                    file_end = part.find(b'\r\n--', file_start)
                                    if file_end == -1:
                                        file_end = len(part)
                                    
                                    file_data = part[file_start:file_end]
                                    
                                    if file_data:
                                        original_name = filename_match.group(1).decode()
                                        ext = original_name.split('.')[-1] if '.' in original_name else 'jpg'
                                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                                        random_suffix = random.randint(100, 999)
                                        filename = f"media_{timestamp}_{random_suffix}.{ext}"
                                        filepath = os.path.join(MEDIA_DIR, filename)
                                        
                                        with open(filepath, 'wb') as f:
                                            f.write(file_data)
                                        print(f"✅ Saved media: {filename} ({len(file_data)} bytes)")
                                        
                                        media_type = 'video' if ext.lower() in ['mp4', 'mov', 'avi', 'webm', 'mkv', 'm4v'] else 'photo'
                                        media_files.append({"path": filename, "type": media_type})
                        else:
                            # Regular text field
                            value_start = part.find(b'\r\n\r\n')
                            if value_start != -1:
                                value_start += 4
                                value_end = part.find(b'\r\n--', value_start)
                                if value_end == -1:
                                    value_end = len(part)
                                value = part[value_start:value_end].decode('utf-8', errors='ignore').strip()
                                form_data[field_name] = value
                    
                    now_ms = datetime.now().timestamp() * 1000
                    event_id = f"U{int(now_ms)}{random.randint(10, 99)}"
                    
                    loc_name = form_data.get('loc', 'Orchard Road')
                    # Find matching location
                    matched_loc = loc_name
                    for key in SINGAPORE_LOCATIONS:
                        if key.lower() in loc_name.lower():
                            matched_loc = key
                            break
                    
                    loc_info = SINGAPORE_LOCATIONS.get(matched_loc, {"lat": DEFAULT_LAT, "lon": DEFAULT_LON, "zh": matched_loc})
                    
                    conn.execute("""
                        INSERT INTO events 
                        (id, type, title_en, title_zh, msg_en, msg_zh,
                         location, location_zh, lat, lon, user_id, source, created, votes, responses, media_paths)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (event_id, form_data.get('type', 'sighting'), 
                          form_data.get('titleEn', '')[:200], '',
                          form_data.get('msgEn', '')[:1000], '',
                          matched_loc, loc_info.get("zh", matched_loc),
                          loc_info["lat"], loc_info["lon"],
                          form_data.get('userId', 'anonymous'), 'user',
                          now_ms, 0, '[]', json.dumps(media_files)))
                    conn.commit()
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "ok", "id": event_id}).encode())
                    print(f"📸 User report: {form_data.get('type')} at {matched_loc} with {len(media_files)} media files")
                else:
                    # JSON fallback
                    length = int(self.headers['Content-Length'])
                    raw_data = self.rfile.read(length)
                    data = json.loads(raw_data.decode('utf-8'))
                    now_ms = datetime.now().timestamp() * 1000
                    event_id = f"U{int(now_ms)}{random.randint(10, 99)}"
                    
                    loc_name = data.get('loc', 'Orchard Road')
                    matched_loc = loc_name
                    for key in SINGAPORE_LOCATIONS:
                        if key.lower() in loc_name.lower():
                            matched_loc = key
                            break
                    
                    loc_info = SINGAPORE_LOCATIONS.get(matched_loc, {"lat": DEFAULT_LAT, "lon": DEFAULT_LON, "zh": matched_loc})
                    
                    conn.execute("""
                        INSERT INTO events 
                        (id, type, title_en, title_zh, msg_en, msg_zh,
                         location, location_zh, lat, lon, user_id, source, created, votes, responses, media_paths)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (event_id, data.get('type', 'sighting'), 
                          data.get('titleEn', '')[:200], '',
                          data.get('msgEn', '')[:1000], '',
                          matched_loc, loc_info.get("zh", matched_loc),
                          loc_info["lat"], loc_info["lon"],
                          data.get('userId', 'anonymous'), 'user',
                          now_ms, 0, '[]', '[]'))
                    conn.commit()
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "ok"}).encode())
                    print(f"📡 User report: {data.get('type')} at {matched_loc}")
                    
            except Exception as e:
                print(f"Error in POST /api/events: {e}")
                import traceback
                traceback.print_exc()
                self.send_response(500)
                self.end_headers()
        
        elif self.path == '/api/requests':
            try:
                length = int(self.headers['Content-Length'])
                raw_data = self.rfile.read(length)
                data = json.loads(raw_data.decode('utf-8'))
                
                now_ms = datetime.now().timestamp() * 1000
                request_id = f"REQ{int(now_ms)}{random.randint(10, 99)}"
                expires_ms = now_ms + 3 * 24 * 3600 * 1000
                
                loc_name = data.get('location', 'Orchard Road')
                matched_loc = loc_name
                for key in SINGAPORE_LOCATIONS:
                    if key.lower() in loc_name.lower():
                        matched_loc = key
                        break
                
                loc_info = SINGAPORE_LOCATIONS.get(matched_loc, {"lat": DEFAULT_LAT, "lon": DEFAULT_LON, "zh": matched_loc})
                
                conn.execute("""
                    INSERT INTO requests 
                    (id, user_id, title, title_zh, description, description_zh,
                     location, location_zh, lat, lon, status, responses, created, expires)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (request_id, data.get('userId', 'anonymous'), data.get('title', '')[:200], '',
                      data.get('description', '')[:1000], '', matched_loc, loc_info.get("zh", matched_loc),
                      loc_info["lat"], loc_info["lon"], 'open', '[]', now_ms, expires_ms))
                conn.commit()
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok", "id": request_id}).encode())
                print(f"🙋 New request: {data.get('title')} at {matched_loc}")
                
            except Exception as e:
                print(f"Error in POST /api/requests: {e}")
                self.send_response(500)
                self.end_headers()
        
        elif self.path == '/api/responses':
            try:
                length = int(self.headers['Content-Length'])
                raw_data = self.rfile.read(length)
                data = json.loads(raw_data.decode('utf-8'))
                
                cursor = conn.execute("SELECT responses FROM requests WHERE id = ?", (data['requestId'],))
                row = cursor.fetchone()
                
                if row:
                    responses = json.loads(row[0]) if row[0] else []
                    responses.append({
                        "userId": data.get('userId', 'anonymous'),
                        "text": data.get('text', '')[:500],
                        "timestamp": datetime.now().timestamp() * 1000
                    })
                    conn.execute("UPDATE requests SET responses = ? WHERE id = ?", (json.dumps(responses), data['requestId']))
                    conn.commit()
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "ok"}).encode())
                    print(f"💬 Response added to request {data['requestId']}")
                else:
                    self.send_response(404)
                    self.end_headers()
                    
            except Exception as e:
                print(f"Error in POST /api/responses: {e}")
                self.send_response(500)
                self.end_headers()
        
        else:
            self.send_response(404)
            self.end_headers()

# =====================================================================
# Server Startup
# =====================================================================
def seed_initial_data():
    cursor = conn.execute("SELECT COUNT(*) FROM events")
    count = cursor.fetchone()[0]
    if count == 0:
        # Add sample data
        now_ms = datetime.now().timestamp() * 1000
        sample_events = [
            ("101", "sighting", "Crowd at Orchard", "", "Large crowd at Orchard Road shopping area", "", "Orchard Road", "乌节路", 1.3039, 103.8317, "system", now_ms - 3600000),
            ("102", "alert", "Long Queue at JB", "", "Estimated 2 hour wait at JB Checkpoint", "", "JB Checkpoint", "新山关卡", 1.4566, 103.7645, "system", now_ms - 7200000),
        ]
        for event in sample_events:
            try:
                conn.execute("INSERT INTO events (id, type, title_en, title_zh, msg_en, msg_zh, location, location_zh, lat, lon, user_id, source, created, votes, responses, media_paths) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", event + ('anonymous', 'user', 0, '[]', '[]'))
            except:
                pass
        conn.commit()
        print("📊 Added sample data")

if __name__ == "__main__":
    PORT = 8080
    server = HTTPServer((HOST, PORT), Handler)
    
    print(f"\n{'='*50}")
    print(f"👁️ 3RD EYE SINGAPORE - GPS Enhanced Version")
    print(f"{'='*50}")
    print(f"📍 Server: http://{HOST}:{PORT}")
    print(f"📁 Media directory: {os.path.abspath(MEDIA_DIR)}")
    print(f"\n✅ Side-by-side layout (media left, content right)")
    print(f"✅ GPS badges show if location has coordinates")
    print(f"✅ Click posts with GPS → Map centers on exact location")
    print(f"✅ Click posts without GPS → Shows default Singapore map with warning")
    print(f"✅ LTA dropdown filter (Bus, Train, Traffic, Flood, Crowd, Taxi)")
    print(f"\n🛑 Press Ctrl+C to stop\n")
    
    seed_initial_data()
    threading.Thread(target=cleanup_old_data, daemon=True).start()
    threading.Thread(target=lta_poller, daemon=True).start()
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
        print("\n👋 Shutting down...")
