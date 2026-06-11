# app_singapore_complete.py - Full Version with Time Filters, Posts, and Requests
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
HOST = 'localhost'
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
    "Serangoon": {"lat": 1.3509, "lon": 103.8731, "zh": "实龙岗"}
}

# =====================================================================
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
        {"location": "PIE near Toa Payoh", "type": "accident", 
         "msg": "Accident on PIE towards Changi Airport, 2 lanes blocked", "msg_zh": "事故导致2条车道被堵"},
        {"location": "CTE Ang Mo Kio", "type": "traffic", 
         "msg": "Heavy traffic on CTE towards City, standstill conditions", "msg_zh": "严重拥堵"},
    ]
    
    for item in traffic_data:
        if location_filter and location_filter != "all" and item["location"] != location_filter:
            continue
        
        lat, lon = 1.2902, 103.8519
        for key, val in SINGAPORE_LOCATIONS.items():
            if key in item["location"]:
                lat, lon = val["lat"], val["lon"]
                break
        
        timestamp = datetime.now().timestamp() * 1000
        
        events.append({
            "id": generate_unique_id("traffic", item["location"], item["type"], timestamp),
            "type": item["type"],
            "title_en": f"{item['type'].upper()} Reported",
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
        
        loc_info = SINGAPORE_LOCATIONS.get(item["location"], {"lat": 1.2902, "lon": 103.8519, "zh": item["location"]})
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
# Cleanup old data (delete > 3 days)
# =====================================================================
def cleanup_old_data():
    """Delete events older than 3 days"""
    while True:
        time.sleep(3600)  # Run every hour
        cutoff_3days = datetime.now().timestamp() * 1000 - 3 * 24 * 3600 * 1000
        cutoff_3hours = datetime.now().timestamp() * 1000 - 3 * 3600 * 1000
        
        # Delete events older than 3 days
        deleted_events = conn.execute("DELETE FROM events WHERE created < ?", (cutoff_3days,)).rowcount
        
        # Delete requests older than 3 days
        deleted_requests = conn.execute("DELETE FROM requests WHERE created < ?", (cutoff_3days,)).rowcount
        
        # Also delete very old LTA events (keep only recent)
        conn.execute("DELETE FROM events WHERE source LIKE 'lta%' AND created < ?", (cutoff_3hours,))
        
        conn.commit()
        if deleted_events > 0 or deleted_requests > 0:
            print(f"🧹 Cleaned {deleted_events} events, {deleted_requests} requests (>3 days old)")

# =====================================================================
# Mobile-Friendly HTML Template
# =====================================================================
HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes, viewport-fit=cover">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <title>3rd Eye Singapore</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            -webkit-tap-highlight-color: transparent;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            overflow: hidden;
            position: fixed;
            width: 100%;
            height: 100%;
            background: #030508;
        }

        #map {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            width: 100%;
            height: 100%;
            z-index: 1;
        }

        /* Bottom Sheet Panel */
        .panel {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            z-index: 1000;
            background: rgba(3, 5, 8, 0.96);
            backdrop-filter: blur(20px);
            border-radius: 24px 24px 0 0;
            box-shadow: 0 -4px 20px rgba(0,0,0,0.4);
            max-height: 65vh;
            transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            display: flex;
            flex-direction: column;
            border-top: 1px solid rgba(0,255,200,0.2);
        }

        .panel.collapsed {
            transform: translateY(calc(100% - 70px));
        }

        .panel-handle {
            width: 40px;
            height: 4px;
            background: rgba(0,255,200,0.3);
            border-radius: 2px;
            margin: 12px auto;
            cursor: pointer;
        }

        /* Filter Bars */
        .filter-section {
            padding: 8px 16px;
            border-bottom: 1px solid rgba(0,255,200,0.1);
        }
        
        .time-filter-bar {
            display: flex;
            gap: 8px;
            overflow-x: auto;
            scrollbar-width: none;
            padding-bottom: 8px;
        }
        .time-filter-bar::-webkit-scrollbar { display: none; }
        
        .category-filter-bar {
            display: flex;
            gap: 8px;
            overflow-x: auto;
            scrollbar-width: none;
            padding-bottom: 8px;
        }
        .category-filter-bar::-webkit-scrollbar { display: none; }
        
        .filter-chip {
            white-space: nowrap;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 500;
            background: rgba(24, 33, 44, 0.9);
            color: #7aA090;
            cursor: pointer;
            border: 1px solid rgba(0,255,200,0.2);
            transition: all 0.2s;
        }
        .filter-chip.active {
            background: #00ffc8;
            color: #000;
            border-color: #00ffc8;
        }
        .filter-chip:active { transform: scale(0.96); }

        .location-select {
            padding: 6px 12px;
            border-radius: 20px;
            background: rgba(24, 33, 44, 0.9);
            color: #d4f0e8;
            border: 1px solid rgba(0,255,200,0.2);
            font-size: 12px;
            width: 100%;
            margin-top: 8px;
            font-family: inherit;
        }

        /* Tabs */
        .tabs {
            display: flex;
            padding: 0 16px;
            border-bottom: 1px solid rgba(0,255,200,0.1);
            gap: 24px;
        }
        .tab {
            padding: 12px 0;
            font-size: 14px;
            font-weight: 600;
            color: #64748b;
            cursor: pointer;
            border-bottom: 2px solid transparent;
            transition: all 0.2s;
        }
        .tab.active { color: #00ffc8; border-bottom-color: #00ffc8; }
        
        .tab-content {
            flex: 1;
            overflow-y: auto;
            padding: 12px;
            -webkit-overflow-scrolling: touch;
        }
        .tab-content.hidden { display: none; }

        /* Event Cards */
        .event-card, .request-card {
            background: rgba(24, 33, 44, 0.9);
            border-radius: 12px;
            padding: 12px;
            margin-bottom: 10px;
            border-left: 4px solid;
            cursor: pointer;
            transition: all 0.2s;
        }
        .event-card:active, .request-card:active { transform: scale(0.98); background: rgba(24, 33, 44, 1); }
        
        .event-accident { border-left-color: #ff2d55; }
        .event-fire { border-left-color: #ff6b00; }
        .event-flood { border-left-color: #0a84ff; }
        .event-traffic { border-left-color: #ffb800; }
        .event-train { border-left-color: #af52de; }
        .event-bus { border-left-color: #30d158; }
        .event-crowd { border-left-color: #64d2ff; }
        .event-taxi { border-left-color: #ff9f0a; }
        .event-sighting { border-left-color: #00ffc8; }
        .event-alert { border-left-color: #ff2d55; }
        .event-request { border-left-color: #ffb800; }

        .event-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
            flex-wrap: wrap;
            gap: 6px;
        }
        .event-title {
            font-weight: 700;
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 6px;
            flex-wrap: wrap;
        }
        .event-badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 9px;
            font-weight: 600;
        }
        .badge-lta { background: #00ffc8; color: #000; }
        .badge-user { background: #30d158; color: #000; }
        .badge-tiktok { background: #000; color: #fff; border: 1px solid #ff0050; }
        .badge-request { background: #ffb800; color: #000; }
        
        .event-desc {
            font-size: 12px;
            color: #7aA090;
            line-height: 1.4;
            margin-bottom: 8px;
        }
        .event-meta {
            font-size: 10px;
            color: #3d6058;
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
        }
        
        .response-count {
            background: rgba(0,255,200,0.1);
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 10px;
        }
        
        /* TikTok styles */
        .tiktok-stats {
            display: flex;
            gap: 12px;
            margin-top: 8px;
            padding-top: 8px;
            border-top: 1px solid rgba(0,255,200,0.1);
        }
        .tiktok-stat {
            display: flex;
            align-items: center;
            gap: 4px;
            font-size: 10px;
            color: #64748b;
        }
        .verified-badge {
            background: #00ffc8;
            color: #000;
            border-radius: 12px;
            padding: 2px 6px;
            font-size: 9px;
            font-weight: 600;
        }

        /* Media Preview */
        .media-preview {
            margin-top: 8px;
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
        }
        .media-preview img, .media-preview video {
            width: 50px;
            height: 50px;
            border-radius: 8px;
            object-fit: cover;
        }

        /* Buttons */
        .fab {
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 1001;
            background: #ff2d55;
            color: white;
            width: 56px;
            height: 56px;
            border-radius: 28px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            border: none;
            font-size: 24px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            transition: transform 0.2s;
        }
        .fab.secondary {
            bottom: 90px;
            background: #ffb800;
        }
        .fab:active { transform: scale(0.94); }

        /* Modals */
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.95);
            z-index: 2000;
            padding: 20px;
            overflow-y: auto;
        }
        .modal-content {
            background: #0c1118;
            border-radius: 20px;
            max-width: 500px;
            margin: 20px auto;
            padding: 20px;
            border: 1px solid rgba(0,255,200,0.2);
        }
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        .modal-header h3 { color: #00ffc8; font-size: 18px; }
        .close-modal {
            font-size: 28px;
            cursor: pointer;
            color: #64748b;
        }
        
        .form-group { margin-bottom: 16px; }
        .form-group label {
            display: block;
            font-size: 12px;
            font-weight: 600;
            margin-bottom: 6px;
            color: #00ffc8;
        }
        .form-group input, .form-group textarea, .form-group select {
            width: 100%;
            padding: 12px;
            border: 1px solid rgba(0,255,200,0.2);
            border-radius: 10px;
            background: #18212c;
            color: #d4f0e8;
            font-size: 14px;
            font-family: inherit;
        }
        
        .media-buttons {
            display: flex;
            gap: 10px;
            margin-bottom: 10px;
        }
        .media-btn {
            flex: 1;
            padding: 12px;
            text-align: center;
            background: #18212c;
            border: 1px solid rgba(0,255,200,0.2);
            border-radius: 10px;
            cursor: pointer;
            font-size: 14px;
        }
        .media-btn:active { background: rgba(0,255,200,0.1); }
        
        .thumb-row {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin-top: 10px;
        }
        .thumb {
            width: 70px;
            height: 70px;
            border-radius: 10px;
            background: #18212c;
            border: 1px solid rgba(0,255,200,0.2);
            position: relative;
            overflow: hidden;
        }
        .thumb img, .thumb video {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        .thumb-x {
            position: absolute;
            top: -6px;
            right: -6px;
            width: 22px;
            height: 22px;
            border-radius: 50%;
            background: #ff2d55;
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            cursor: pointer;
            border: 2px solid #0c1118;
        }
        
        .btn-submit {
            background: #00ffc8;
            color: #000;
            border: none;
            padding: 14px;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 600;
            width: 100%;
            cursor: pointer;
            margin-top: 10px;
        }
        .btn-submit:active { transform: scale(0.98); }
        
        .empty-state {
            text-align: center;
            padding: 40px 20px;
            color: #64748b;
        }

        /* Response section in detail view */
        .responses-section {
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid rgba(0,255,200,0.1);
        }
        .response-item {
            padding: 8px;
            margin-bottom: 8px;
            background: rgba(24, 33, 44, 0.6);
            border-radius: 8px;
        }
        .response-author {
            font-size: 10px;
            color: #00ffc8;
            margin-bottom: 4px;
        }
        .response-text {
            font-size: 12px;
            color: #7aA090;
        }
        .respond-btn {
            background: rgba(0,255,200,0.1);
            border: 1px solid rgba(0,255,200,0.3);
            padding: 10px;
            border-radius: 10px;
            text-align: center;
            cursor: pointer;
            margin-top: 12px;
            font-size: 12px;
            color: #00ffc8;
        }

        @media (min-width: 768px) {
            .panel {
                max-width: 400px;
                right: auto;
                border-radius: 24px;
                margin: 16px;
                max-height: 85vh;
            }
            .panel.collapsed {
                transform: translateY(calc(100% - 70px));
            }
        }
    </style>
</head>
<body>
    <div id="map"></div>
    
    <div class="panel" id="panel">
        <div class="panel-handle" id="panelHandle"></div>
        
        <!-- Time Filter Section -->
        <div class="filter-section">
            <div class="time-filter-bar" id="timeFilterBar">
                <div class="filter-chip active" data-time="30min">⏱️ 30 min</div>
                <div class="filter-chip" data-time="1hour">⏱️ 1 hour</div>
                <div class="filter-chip" data-time="3hours">⏱️ 3 hours</div>
                <div class="filter-chip" data-time="1day">📅 1 day</div>
                <div class="filter-chip" data-time="3days">📅 3 days</div>
            </div>
        </div>
        
        <!-- Category & Location Filters -->
        <div class="filter-section">
            <div class="category-filter-bar" id="categoryFilterBar">
                <div class="filter-chip active" data-category="all">📊 All</div>
                <div class="filter-chip" data-category="bus">🚌 Bus</div>
                <div class="filter-chip" data-category="train">🚇 Train</div>
                <div class="filter-chip" data-category="traffic">🚗 Traffic</div>
                <div class="filter-chip" data-category="flood">🌊 Flood</div>
                <div class="filter-chip" data-category="crowd">👥 Crowd</div>
                <div class="filter-chip" data-category="taxi">🚕 Taxi</div>
            </div>
            <select id="locationFilter" class="location-select">
                <option value="all">📍 All Locations</option>
                <option value="Orchard Road">Orchard Road</option>
                <option value="Jurong East">Jurong East</option>
                <option value="Tampines">Tampines</option>
                <option value="Woodlands">Woodlands</option>
                <option value="City Hall">City Hall</option>
                <option value="Marina Bay">Marina Bay</option>
                <option value="Changi Airport">Changi Airport</option>
            </select>
        </div>
        
        <!-- Tabs -->
        <div class="tabs">
            <div class="tab active" data-tab="feed">📡 Feed</div>
            <div class="tab" data-tab="requests">🙋 Requests</div>
            <div class="tab" data-tab="lta">🏛️ LTA</div>
            <div class="tab" data-tab="tiktok">🎵 TikTok</div>
        </div>
        
        <div id="feedTab" class="tab-content"><div id="feedList">Loading...</div></div>
        <div id="requestsTab" class="tab-content hidden"><div id="requestsList">Loading...</div></div>
        <div id="ltaTab" class="tab-content hidden"><div id="ltaList">Loading LTA data...</div></div>
        <div id="tiktokTab" class="tab-content hidden"><div id="tiktokList">Loading TikTok feed...</div></div>
    </div>
    
    <!-- Floating Action Buttons -->
    <button class="fab" id="reportBtn" title="Report Incident">+</button>
    <button class="fab secondary" id="requestBtn" title="Request Info">🙋</button>
    
    <!-- Report Modal -->
    <div id="reportModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3>📸 Report Incident</h3>
                <span class="close-modal">&times;</span>
            </div>
            <form id="reportForm">
                <div class="form-group">
                    <label>📍 Location</label>
                    <select id="reportLocation" required>
                        <option value="Orchard Road">Orchard Road</option>
                        <option value="Jurong East">Jurong East</option>
                        <option value="Tampines">Tampines</option>
                        <option value="Woodlands">Woodlands</option>
                        <option value="City Hall">City Hall</option>
                        <option value="Marina Bay">Marina Bay</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>🏷️ Type</label>
                    <select id="reportType">
                        <option value="accident">Accident</option>
                        <option value="fire">Fire</option>
                        <option value="flood">Flood</option>
                        <option value="traffic">Traffic</option>
                        <option value="crowd">Crowd</option>
                        <option value="sighting">Sighting</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>📝 Description</label>
                    <textarea id="reportDesc" rows="3" placeholder="What's happening?" required></textarea>
                </div>
                <div class="media-buttons">
                    <div class="media-btn" onclick="document.getElementById('photoInput').click()">📸 Photo</div>
                    <div class="media-btn" onclick="document.getElementById('videoInput').click()">🎥 Video</div>
                </div>
                <input type="file" id="photoInput" accept="image/*" capture="environment" style="display:none">
                <input type="file" id="videoInput" accept="video/*" capture="environment" style="display:none">
                <div id="thumbRow" class="thumb-row"></div>
                <button type="submit" class="btn-submit">🚀 Submit Report</button>
            </form>
        </div>
    </div>
    
    <!-- Request Modal -->
    <div id="requestModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3>🙋 Request Information</h3>
                <span class="close-modal">&times;</span>
            </div>
            <form id="requestForm">
                <div class="form-group">
                    <label>📍 Location</label>
                    <select id="requestLocation" required>
                        <option value="Orchard Road">Orchard Road</option>
                        <option value="Jurong East">Jurong East</option>
                        <option value="Tampines">Tampines</option>
                        <option value="Woodlands">Woodlands</option>
                        <option value="City Hall">City Hall</option>
                        <option value="Marina Bay">Marina Bay</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>📝 What do you want to know?</label>
                    <input type="text" id="requestTitle" placeholder="e.g., Traffic conditions on PIE?" required>
                </div>
                <div class="form-group">
                    <label>📝 Details (optional)</label>
                    <textarea id="requestDesc" rows="3" placeholder="More details about what you need..."></textarea>
                </div>
                <button type="submit" class="btn-submit">📡 Post Request</button>
            </form>
        </div>
    </div>
    
    <!-- Response Modal -->
    <div id="responseModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3>💬 Respond to Request</h3>
                <span class="close-modal">&times;</span>
            </div>
            <div id="responseRequestInfo" style="background:rgba(0,255,200,0.1);padding:10px;border-radius:10px;margin-bottom:15px;"></div>
            <form id="responseForm">
                <div class="form-group">
                    <label>📝 Your Response</label>
                    <textarea id="responseText" rows="3" placeholder="What information can you provide?" required></textarea>
                </div>
                <button type="submit" class="btn-submit">📤 Send Response</button>
            </form>
        </div>
    </div>

    <script>
        var map = L.map('map').setView([1.2902, 103.8519], 12);
        L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; OpenStreetMap | Singapore'
        }).addTo(map);
        
        var markers = {};
        var currentTimeFilter = '3hours';
        var currentCategory = 'all';
        var currentLocation = 'all';
        var mediaFiles = [];
        var currentRequestId = null;
        
        // Panel collapse
        var panelCollapsed = false;
        document.getElementById('panelHandle').onclick = () => {
            document.getElementById('panel').classList.toggle('collapsed');
            panelCollapsed = !panelCollapsed;
        };
        
        // Time filter chips
        document.querySelectorAll('#timeFilterBar .filter-chip').forEach(chip => {
            chip.onclick = function() {
                document.querySelectorAll('#timeFilterBar .filter-chip').forEach(c => c.classList.remove('active'));
                this.classList.add('active');
                currentTimeFilter = this.dataset.time;
                loadCurrentTab();
            };
        });
        
        // Category filter chips
        document.querySelectorAll('#categoryFilterBar .filter-chip').forEach(chip => {
            chip.onclick = function() {
                document.querySelectorAll('#categoryFilterBar .filter-chip').forEach(c => c.classList.remove('active'));
                this.classList.add('active');
                currentCategory = this.dataset.category;
                loadCurrentTab();
            };
        });
        
        // Location filter
        document.getElementById('locationFilter').onchange = function() {
            currentLocation = this.value;
            loadCurrentTab();
        };
        
        // Tabs
        document.querySelectorAll('.tab').forEach(tab => {
            tab.onclick = function() {
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                this.classList.add('active');
                document.querySelectorAll('.tab-content').forEach(c => c.classList.add('hidden'));
                document.getElementById(this.dataset.tab + 'Tab').classList.remove('hidden');
                loadCurrentTab();
            };
        });
        
        function loadCurrentTab() {
            var activeTab = document.querySelector('.tab.active').dataset.tab;
            if (activeTab === 'feed') loadFeed();
            else if (activeTab === 'requests') loadRequests();
            else if (activeTab === 'lta') loadLTA();
            else if (activeTab === 'tiktok') loadTikTok();
        }
        
        function getSourceBadge(source) {
            if (source && source.startsWith('lta')) return '<span class="event-badge badge-lta">LTA</span>';
            if (source === 'tiktok') return '<span class="event-badge badge-tiktok">🎵 TikTok</span>';
            return '<span class="event-badge badge-user">User</span>';
        }
        
        function getEventIcon(type) {
            const icons = {
                'accident': '🚨', 'fire': '🔥', 'flood': '🌊', 'traffic': '🚗',
                'train': '🚇', 'bus': '🚌', 'crowd': '👥', 'taxi': '🚕',
                'sighting': '👁️', 'alert': '⚠️', 'request': '📡'
            };
            return icons[type] || '📌';
        }
        
        function formatTime(ms) {
            var diff = Date.now() - ms;
            var minutes = Math.floor(diff / 60000);
            if (minutes < 60) return minutes + ' min ago';
            var hours = Math.floor(minutes / 60);
            if (hours < 24) return hours + ' hours ago';
            return Math.floor(hours / 24) + ' days ago';
        }
        
        function loadFeed() {
            var url = `/api/events?time=${currentTimeFilter}&category=${currentCategory}&location=${encodeURIComponent(currentLocation)}`;
            fetch(url).then(r => r.json()).then(events => {
                var container = document.getElementById('feedList');
                if (!events.length) {
                    container.innerHTML = '<div class="empty-state">✨ No events matching filters</div>';
                    return;
                }
                container.innerHTML = events.map(e => `
                    <div class="event-card event-${e.type}" onclick="map.setView([${e.lat}, ${e.lon}], 15)">
                        <div class="event-header">
                            <div class="event-title">
                                ${getEventIcon(e.type)} ${e.titleEn || e.type.toUpperCase()}
                                ${getSourceBadge(e.source)}
                            </div>
                            <div class="event-meta">👍 ${e.votes || 0} · 🕒 ${formatTime(e.created)}</div>
                        </div>
                        <div class="event-desc">${e.msgEn || e.msgZh || ''}</div>
                        <div class="event-meta">📍 ${e.loc}</div>
                        ${e.mediaPaths && e.mediaPaths.length ? `<div class="media-preview">${e.mediaPaths.map(m => m.type === 'video' ? `<video src="/media/${m.path}" muted></video>` : `<img src="/media/${m.path}">`).join('')}</div>` : ''}
                    </div>
                `).join('');
                updateMarkers(events);
            });
        }
        
        function loadRequests() {
            var url = `/api/requests?time=${currentTimeFilter}&location=${encodeURIComponent(currentLocation)}`;
            fetch(url).then(r => r.json()).then(requests => {
                var container = document.getElementById('requestsList');
                if (!requests.length) {
                    container.innerHTML = '<div class="empty-state">🙋 No active requests. Tap the 🙋 button to ask for information!</div>';
                    return;
                }
                container.innerHTML = requests.map(r => `
                    <div class="request-card event-request" onclick="openRequestDetail('${r.id}')">
                        <div class="event-header">
                            <div class="event-title">
                                📡 ${r.title}
                                <span class="event-badge badge-request">Request</span>
                            </div>
                            <div class="event-meta">🕒 ${formatTime(r.created)}</div>
                        </div>
                        <div class="event-desc">${r.description || 'No additional details'}</div>
                        <div class="event-meta">📍 ${r.location} · 💬 ${r.responses?.length || 0} responses</div>
                        <div class="respond-btn" onclick="event.stopPropagation(); openResponseModal('${r.id}', '${r.title.replace(/'/g, "\\'")}')">💬 Respond to this request</div>
                    </div>
                `).join('');
            });
        }
        
        function openRequestDetail(requestId) {
            fetch(`/api/requests/${requestId}`).then(r => r.json()).then(request => {
                var responsesHtml = '';
                if (request.responses && request.responses.length) {
                    responsesHtml = '<div class="responses-section"><strong>💬 Responses:</strong>';
                    request.responses.forEach(r => {
                        responsesHtml += `
                            <div class="response-item">
                                <div class="response-author">👤 ${r.userId}</div>
                                <div class="response-text">${r.text}</div>
                                <div class="event-meta">🕒 ${formatTime(r.timestamp)}</div>
                            </div>
                        `;
                    });
                    responsesHtml += '</div>';
                }
                
                var detailHtml = `
                    <div class="event-card event-request" style="margin-bottom:0;">
                        <div class="event-header">
                            <div class="event-title">📡 ${request.title}</div>
                        </div>
                        <div class="event-desc">${request.description || 'No additional details'}</div>
                        <div class="event-meta">📍 ${request.location} · Posted ${formatTime(request.created)}</div>
                        ${responsesHtml}
                        <div class="respond-btn" onclick="openResponseModal('${request.id}', '${request.title.replace(/'/g, "\\'")}')">💬 Add Your Response</div>
                    </div>
                `;
                
                document.getElementById('responseRequestInfo').innerHTML = detailHtml;
                document.getElementById('responseModal').style.display = 'block';
                currentRequestId = request.id;
            });
        }
        
        function openResponseModal(requestId, requestTitle) {
            currentRequestId = requestId;
            document.getElementById('responseRequestInfo').innerHTML = `<strong>Responding to:</strong> ${requestTitle}`;
            document.getElementById('responseText').value = '';
            document.getElementById('responseModal').style.display = 'block';
        }
        
        function loadLTA() {
            var url = `/api/lta?category=${currentCategory}&location=${encodeURIComponent(currentLocation)}`;
            fetch(url).then(r => r.json()).then(events => {
                var container = document.getElementById('ltaList');
                if (!events.length) {
                    container.innerHTML = '<div class="empty-state">🏛️ No LTA data available</div>';
                    return;
                }
                container.innerHTML = events.map(e => `
                    <div class="event-card event-${e.type}" onclick="map.setView([${e.lat}, ${e.lon}], 15)">
                        <div class="event-header">
                            <div class="event-title">
                                ${getEventIcon(e.type)} ${e.titleEn}
                                <span class="event-badge badge-lta">LTA</span>
                            </div>
                        </div>
                        <div class="event-desc">${e.msgEn}</div>
                        <div class="event-meta">📍 ${e.loc}</div>
                    </div>
                `).join('');
                updateMarkers(events);
            });
        }
        
        function loadTikTok() {
            fetch('/api/tiktok').then(r => r.json()).then(posts => {
                var container = document.getElementById('tiktokList');
                if (!posts.length) {
                    container.innerHTML = '<div class="empty-state">🎵 No TikTok posts available</div>';
                    return;
                }
                container.innerHTML = posts.map(p => `
                    <div class="event-card event-${p.type}">
                        <div class="event-header">
                            <div class="event-title">
                                ${getEventIcon(p.type)} ${p.title}
                                <span class="event-badge badge-tiktok">🎵 TikTok</span>
                                ${p.verified ? '<span class="verified-badge">✓ Verified</span>' : ''}
                            </div>
                            <div class="event-meta">👤 ${p.author}</div>
                        </div>
                        <div class="event-desc">${p.description}</div>
                        <div class="tiktok-stats">
                            <span class="tiktok-stat">❤️ ${p.likes}</span>
                            <span class="tiktok-stat">🔄 ${p.shares}</span>
                            <span class="tiktok-stat">💬 ${p.comments}</span>
                        </div>
                        <div class="event-meta">📍 ${p.location}</div>
                    </div>
                `).join('');
            });
        }
        
        function updateMarkers(events) {
            Object.keys(markers).forEach(id => map.removeLayer(markers[id]));
            markers = {};
            
            events.forEach(event => {
                var colorMap = {
                    'accident': '#ff2d55', 'fire': '#ff6b00', 'flood': '#0a84ff',
                    'traffic': '#ffb800', 'train': '#af52de', 'bus': '#30d158',
                    'crowd': '#64d2ff', 'taxi': '#ff9f0a', 'sighting': '#00ffc8'
                };
                var color = colorMap[event.type] || '#6b7280';
                
                var marker = L.marker([event.lat, event.lon], {
                    icon: L.divIcon({
                        html: `<div style="background:${color}; width:24px;height:24px;border-radius:50%;border:2px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.3);display:flex;align-items:center;justify-content:center;font-size:12px;">${getEventIcon(event.type)}</div>`,
                        iconSize: [24, 24],
                        className: 'custom-marker'
                    })
                }).bindPopup(`<b>${event.titleEn || event.type}</b><br>${(event.msgEn || '').substring(0, 80)}<br><small>${event.loc}</small>`);
                
                marker.addTo(map);
                markers[event.id] = marker;
            });
        }
        
        // Media handling
        function handleMediaSelect(file, type) {
            if (!file) return;
            var reader = new FileReader();
            reader.onload = function(e) {
                mediaFiles.push({file: file, type: type});
                var thumbRow = document.getElementById('thumbRow');
                var div = document.createElement('div');
                div.className = 'thumb';
                var idx = mediaFiles.length - 1;
                if (type === 'video') {
                    div.innerHTML = `<video src="${e.target.result}" muted></video><div class="thumb-x" onclick="this.parentElement.remove(); mediaFiles.splice(${idx},1)">✕</div>`;
                } else {
                    div.innerHTML = `<img src="${e.target.result}"><div class="thumb-x" onclick="this.parentElement.remove(); mediaFiles.splice(${idx},1)">✕</div>`;
                }
                thumbRow.appendChild(div);
            };
            reader.readAsDataURL(file);
        }
        
        document.getElementById('photoInput').onchange = function(e) {
            if (e.target.files[0]) handleMediaSelect(e.target.files[0], 'photo');
            this.value = '';
        };
        
        document.getElementById('videoInput').onchange = function(e) {
            if (e.target.files[0]) handleMediaSelect(e.target.files[0], 'video');
            this.value = '';
        };
        
        // Submit report
        document.getElementById('reportForm').onsubmit = async (e) => {
            e.preventDefault();
            var formData = new FormData();
            formData.append('loc', document.getElementById('reportLocation').value);
            formData.append('type', document.getElementById('reportType').value);
            formData.append('titleEn', document.getElementById('reportType').value);
            formData.append('msgEn', document.getElementById('reportDesc').value);
            formData.append('userId', 'user_' + Math.random().toString(36).substr(2, 6));
            
            for (var i = 0; i < mediaFiles.length; i++) {
                formData.append('media', mediaFiles[i].file);
            }
            
            var response = await fetch('/api/events', { method: 'POST', body: formData });
            if (response.ok) {
                alert('✅ Report submitted!');
                document.getElementById('reportModal').style.display = 'none';
                document.getElementById('reportForm').reset();
                document.getElementById('thumbRow').innerHTML = '';
                mediaFiles = [];
                loadFeed();
            } else {
                alert('❌ Failed to submit');
            }
        };
        
        // Submit request
        document.getElementById('requestForm').onsubmit = async (e) => {
            e.preventDefault();
            var data = {
                location: document.getElementById('requestLocation').value,
                title: document.getElementById('requestTitle').value,
                description: document.getElementById('requestDesc').value,
                userId: 'user_' + Math.random().toString(36).substr(2, 6)
            };
            
            var response = await fetch('/api/requests', { 
                method: 'POST', 
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });
            
            if (response.ok) {
                alert('✅ Request posted! Others can now respond.');
                document.getElementById('requestModal').style.display = 'none';
                document.getElementById('requestForm').reset();
                loadRequests();
            } else {
                alert('❌ Failed to post request');
            }
        };
        
        // Submit response
        document.getElementById('responseForm').onsubmit = async (e) => {
            e.preventDefault();
            var data = {
                requestId: currentRequestId,
                text: document.getElementById('responseText').value,
                userId: 'user_' + Math.random().toString(36).substr(2, 6)
            };
            
            var response = await fetch('/api/responses', { 
                method: 'POST', 
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });
            
            if (response.ok) {
                alert('✅ Response sent!');
                document.getElementById('responseModal').style.display = 'none';
                document.getElementById('responseForm').reset();
                loadRequests();
            } else {
                alert('❌ Failed to send response');
            }
        };
        
        // Modals
        var reportModal = document.getElementById('reportModal');
        var requestModal = document.getElementById('requestModal');
        var responseModal = document.getElementById('responseModal');
        
        document.getElementById('reportBtn').onclick = () => reportModal.style.display = 'block';
        document.getElementById('requestBtn').onclick = () => requestModal.style.display = 'block';
        
        document.querySelectorAll('.close-modal').forEach(btn => {
            btn.onclick = () => {
                reportModal.style.display = 'none';
                requestModal.style.display = 'none';
                responseModal.style.display = 'none';
            };
        });
        
        window.onclick = (event) => {
            if (event.target === reportModal) reportModal.style.display = 'none';
            if (event.target === requestModal) requestModal.style.display = 'none';
            if (event.target === responseModal) responseModal.style.display = 'none';
        };
        
        // Initial load and auto-refresh
        loadFeed();
        setInterval(() => loadCurrentTab(), 30000);
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
            
            time_filter = params.get('time', '3hours')
            category = params.get('category', 'all')
            location = params.get('location', 'all')
            
            # Calculate cutoff based on time filter
            time_map = {
                '30min': 0.5, '1hour': 1, '3hours': 3, '1day': 24, '3days': 72
            }
            hours = time_map.get(time_filter, 3)
            cutoff = datetime.now().timestamp() * 1000 - hours * 3600 * 1000
            
            query_sql = "SELECT id, type, title_en, title_zh, msg_en, msg_zh, location, location_zh, lat, lon, source, votes, media_paths, created FROM events WHERE created > ?"
            query_params = [cutoff]
            
            if category != 'all':
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
                    "titleEn": row[2] or '', "titleZh": row[3] or '',
                    "msgEn": row[4] or '', "msgZh": row[5] or '',
                    "loc": row[6] or 'Singapore', "locZh": row[7] or '新加坡',
                    "lat": row[8] or 1.2902, "lon": row[9] or 103.8519,
                    "source": row[10] or 'user', "votes": row[11] or 0,
                    "mediaPaths": json.loads(row[12]) if row[12] else [],
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
            
            # Check if getting single request
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
                        "titleZh": row[3], "description": row[4], "descriptionZh": row[5],
                        "location": row[6], "locationZh": row[7], "lat": row[8], "lon": row[9],
                        "status": row[10], "responses": json.loads(row[11]) if row[11] else [],
                        "created": row[12]
                    }).encode())
                return
            
            # List requests
            time_filter = params.get('time', '3hours')
            location = params.get('location', 'all')
            
            time_map = {'30min': 0.5, '1hour': 1, '3hours': 3, '1day': 24, '3days': 72}
            hours = time_map.get(time_filter, 3)
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
                    "titleZh": row[3], "description": row[4], "descriptionZh": row[5],
                    "location": row[6], "locationZh": row[7], "lat": row[8], "lon": row[9],
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
            
            lta_events = generate_all_lta_events(category, location if location != 'all' else None)
            
            for event in lta_events:
                event.pop('id', None)
                event.pop('created', None)
            
            self.wfile.write(json.dumps(lta_events).encode())
        
        elif self.path == '/api/tiktok':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            tiktok_posts = generate_tiktok_feed()
            
            for post in tiktok_posts:
                loc_name = post['location'].split(" ")[0]
                if loc_name in SINGAPORE_LOCATIONS:
                    post['lat'] = SINGAPORE_LOCATIONS[loc_name]['lat']
                    post['lon'] = SINGAPORE_LOCATIONS[loc_name]['lon']
                else:
                    post['lat'] = 1.2902
                    post['lon'] = 103.8519
            
            self.wfile.write(json.dumps(tiktok_posts).encode())
        
        elif self.path.startswith('/media/'):
            filename = self.path.split('/')[-1]
            filepath = os.path.join(MEDIA_DIR, filename)
            if os.path.exists(filepath):
                self.send_response(200)
                if filename.endswith(('.mp4', '.mov', '.webm', '.avi')):
                    self.send_header('Content-type', 'video/mp4')
                else:
                    self.send_header('Content-type', 'image/jpeg')
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
                    content_length = int(self.headers['Content-Length'])
                    post_data = self.rfile.read(content_length)
                    boundary = content_type.split('boundary=')[1].encode()
                    parts = post_data.split(boundary)
                    
                    form_data = {}
                    media_files = []
                    
                    for part in parts:
                        if b'Content-Disposition: form-data' in part:
                            name_match = re.search(b'name="([^"]+)"', part)
                            if name_match:
                                field_name = name_match.group(1).decode()
                                value_start = part.find(b'\r\n\r\n') + 4
                                value_end = part.rfind(b'\r\n')
                                if value_end > value_start:
                                    value = part[value_start:value_end].decode().strip()
                                    form_data[field_name] = value
                            
                            if b'filename=' in part:
                                filename_match = re.search(b'filename="([^"]+)"', part)
                                if filename_match:
                                    file_start = part.find(b'\r\n\r\n') + 4
                                    file_end = part.rfind(b'\r\n')
                                    if file_end > file_start:
                                        file_data = part[file_start:file_end]
                                        original_name = filename_match.group(1).decode()
                                        ext = original_name.split('.')[-1] if '.' in original_name else 'jpg'
                                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                                        filename = f"media_{timestamp}_{random.randint(100,999)}.{ext}"
                                        filepath = os.path.join(MEDIA_DIR, filename)
                                        with open(filepath, 'wb') as f:
                                            f.write(file_data)
                                        
                                        media_type = 'video' if ext.lower() in ['mp4', 'mov', 'avi', 'webm', 'mkv'] else 'photo'
                                        media_files.append({"path": filename, "type": media_type})
                    
                    now_ms = datetime.now().timestamp() * 1000
                    event_id = f"U{int(now_ms)}{random.randint(10, 99)}"
                    
                    loc_name = form_data.get('loc', 'Orchard Road')
                    loc_info = SINGAPORE_LOCATIONS.get(loc_name, {"lat": 1.2902, "lon": 103.8519, "zh": loc_name})
                    
                    conn.execute("""
                        INSERT INTO events 
                        (id, type, title_en, title_zh, msg_en, msg_zh,
                         location, location_zh, lat, lon, user_id, source, created, votes, responses, media_paths)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (event_id, form_data.get('type', 'sighting'), 
                          form_data.get('titleEn', ''), form_data.get('titleZh', ''),
                          form_data.get('msgEn', ''), form_data.get('msgZh', ''),
                          loc_name, loc_info.get("zh", loc_name),
                          loc_info["lat"], loc_info["lon"],
                          form_data.get('userId', 'anonymous'), 'user',
                          now_ms, 0, '[]', json.dumps(media_files)))
                    conn.commit()
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "ok", "id": event_id}).encode())
                    print(f"📸 User report: {form_data.get('type')} at {loc_name}")
                else:
                    # JSON fallback
                    length = int(self.headers['Content-Length'])
                    data = json.loads(self.rfile.read(length))
                    now_ms = datetime.now().timestamp() * 1000
                    event_id = f"U{int(now_ms)}{random.randint(10, 99)}"
                    
                    loc_name = data.get('loc', 'Orchard Road')
                    loc_info = SINGAPORE_LOCATIONS.get(loc_name, {"lat": 1.2902, "lon": 103.8519, "zh": loc_name})
                    
                    conn.execute("""
                        INSERT INTO events 
                        (id, type, title_en, title_zh, msg_en, msg_zh,
                         location, location_zh, lat, lon, user_id, source, created, votes, responses, media_paths)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (event_id, data.get('type', 'sighting'), 
                          data.get('titleEn', ''), data.get('titleZh', ''),
                          data.get('msgEn', ''), data.get('msgZh', ''),
                          loc_name, loc_info.get("zh", loc_name),
                          loc_info["lat"], loc_info["lon"],
                          data.get('userId', 'anonymous'), 'user',
                          now_ms, 0, '[]', '[]'))
                    conn.commit()
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "ok"}).encode())
                    print(f"📡 User report: {data.get('type')} at {loc_name}")
                    
            except Exception as e:
                print(f"Error: {e}")
                self.send_response(500)
                self.end_headers()
        
        elif self.path == '/api/requests':
            try:
                length = int(self.headers['Content-Length'])
                data = json.loads(self.rfile.read(length))
                
                now_ms = datetime.now().timestamp() * 1000
                request_id = f"REQ{int(now_ms)}{random.randint(10, 99)}"
                expires_ms = now_ms + 3 * 24 * 3600 * 1000  # Expires in 3 days
                
                loc_name = data.get('location', 'Orchard Road')
                loc_info = SINGAPORE_LOCATIONS.get(loc_name, {"lat": 1.2902, "lon": 103.8519, "zh": loc_name})
                
                conn.execute("""
                    INSERT INTO requests 
                    (id, user_id, title, title_zh, description, description_zh,
                     location, location_zh, lat, lon, status, responses, created, expires)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (request_id, data.get('userId', 'anonymous'), data.get('title', ''), '',
                      data.get('description', ''), '', loc_name, loc_info.get("zh", loc_name),
                      loc_info["lat"], loc_info["lon"], 'open', '[]', now_ms, expires_ms))
                conn.commit()
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok", "id": request_id}).encode())
                print(f"🙋 New request: {data.get('title')} at {loc_name}")
                
            except Exception as e:
                print(f"Error: {e}")
                self.send_response(500)
                self.end_headers()
        
        elif self.path == '/api/responses':
            try:
                length = int(self.headers['Content-Length'])
                data = json.loads(self.rfile.read(length))
                
                cursor = conn.execute("SELECT responses FROM requests WHERE id = ?", (data['requestId'],))
                row = cursor.fetchone()
                
                if row:
                    responses = json.loads(row[0]) if row[0] else []
                    responses.append({
                        "userId": data.get('userId', 'anonymous'),
                        "text": data.get('text', ''),
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
                print(f"Error: {e}")
                self.send_response(500)
                self.end_headers()
        
        elif self.path == '/api/vote':
            try:
                length = int(self.headers['Content-Length'])
                data = json.loads(self.rfile.read(length))
                conn.execute("UPDATE events SET votes = votes + 1 WHERE id = ?", (data['event_id'],))
                conn.commit()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode())
            except Exception as e:
                print(f"Vote error: {e}")
                self.send_response(500)
                self.end_headers()
        
        else:
            self.send_response(404)
            self.end_headers()

# =====================================================================
# Server Startup
# =====================================================================
def seed_initial_data():
    cursor = conn.execute("SELECT COUNT(*) FROM events WHERE source LIKE 'lta%'")
    if cursor.fetchone()[0] > 0:
        return
    
    print("🌱 Seeding initial LTA data...")
    for cat in ["bus", "train", "traffic", "flood", "crowd", "taxi"]:
        events = generate_all_lta_events(cat, None)
        save_events_to_db(events)
        time.sleep(0.1)
    print("✅ Seeded LTA data")

def find_port():
    for port in [8080, 3000, 5000, 8888, 9000]:
        try:
            server = HTTPServer((HOST, port), Handler)
            return port, server
        except:
            continue
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('localhost', 0))
    port = s.getsockname()[1]
    s.close()
    return port, HTTPServer((HOST, port), Handler)

if __name__ == "__main__":
    PORT, server = find_port()
    
    seed_initial_data()
    threading.Thread(target=cleanup_old_data, daemon=True).start()
    threading.Thread(target=lta_poller, daemon=True).start()
    
    print(f"\n{'='*60}")
    print(f"👁️ 3RD EYE SINGAPORE - Complete Version")
    print(f"{'='*60}")
    print(f"📍 Dashboard: http://{HOST}:{PORT}")
    print(f"\n📱 Mobile Optimized Features:")
    print(f"   • Bottom sheet panel (swipe up/down)")
    print(f"   • Time filters: 30min, 1hr, 3hrs, 1day, 3days")
    print(f"   • Category filters: All, Bus, Train, Traffic, Flood, Crowd, Taxi")
    print(f"   • Location filter")
    print(f"\n📊 Core Features:")
    print(f"   • 📸 Photo/Video Upload")
    print(f"   • 🙋 Post Information Requests")
    print(f"   • 💬 Respond to Requests")
    print(f"   • 🚌 LTA Bus Arrivals")
    print(f"   • 🚇 LTA Train Alerts")
    print(f"   • 🚗 LTA Traffic")
    print(f"   • 🌊 LTA Flood Alerts")
    print(f"   • 👥 LTA Crowd Density")
    print(f"   • 🚕 LTA Taxi Availability")
    print(f"   • 🎵 TikTok Crowdsourced Feed")
    print(f"\n🗑️ Auto Cleanup: Events > 3 days old are deleted")
    print(f"\n🛑 Press Ctrl+C to stop\n")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
        print("\n👋 Shutting down...")