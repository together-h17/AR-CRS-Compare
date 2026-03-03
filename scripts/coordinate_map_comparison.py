#!/usr/bin/env python3
"""
氣象站坐標系統HTML地圖比較分析腳本
比較氣象站API中的兩個不同坐標系統，並生成互動式HTML地圖
"""

import os
import requests
import json
import math
import pandas as pd
from dotenv import load_dotenv
import folium
from folium.plugins import MarkerCluster
import branca.colormap as cm

# 載入環境變數
load_dotenv()

class CoordinateMapAnalyzer:
    def __init__(self):
        self.api_key = os.getenv('CWA_API_KEY')
        self.base_url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore"
        self.dataset_id = "O-A0003-001"
        
        if not self.api_key:
            raise ValueError("CWA_API_KEY not found in environment variables")
    
    def fetch_weather_data(self):
        """獲取全台自動氣象站觀測資料"""
        url = f"{self.base_url}/{self.dataset_id}"
        params = {
            'Authorization': self.api_key,
            'format': 'JSON'
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API 請求失敗: {e}")
            return None
    
    def haversine_distance(self, lat1, lon1, lat2, lon2):
        """計算兩點間的哈弗辛距離（米）"""
        R = 6371000  # 地球半徑（米）
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat/2)**2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def parse_dual_coordinates(self, data):
        """解析雙坐標系統資料"""
        if not data or 'records' not in data:
            return None
        
        stations = []
        records = data['records']['Station']
        
        for record in records:
            try:
                # 獲取兩個坐標系統的資料
                coords = record['GeoInfo']['Coordinates']
                
                # 假設有兩個坐標系統
                if len(coords) >= 2:
                    coord1 = coords[0]  # 第一個坐標系統
                    coord2 = coords[1]  # 第二個坐標系統
                    
                    station_info = {
                        'station_id': record['StationId'],
                        'station_name': record['StationName'],
                        'location': record['GeoInfo']['CountyName'] + record['GeoInfo']['TownName'],
                        
                        # 第一個坐標系統（當作WGS84）
                        'lat1': float(coord1['StationLatitude']),
                        'lon1': float(coord1['StationLongitude']),
                        'coord1_name': coord1.get('CoordinateName', 'Coordinate1'),
                        
                        # 第二個坐標系統（當作WGS84）
                        'lat2': float(coord2['StationLatitude']),
                        'lon2': float(coord2['StationLongitude']),
                        'coord2_name': coord2.get('CoordinateName', 'Coordinate2'),
                        
                        # 計算距離差異
                        'distance_diff': self.haversine_distance(
                            float(coord1['StationLatitude']), float(coord1['StationLongitude']),
                            float(coord2['StationLatitude']), float(coord2['StationLongitude'])
                        ),
                        
                        # 其他氣象資料
                        'temperature': float(record['WeatherElement']['AirTemperature']) if record['WeatherElement']['AirTemperature'] else None,
                        'humidity': float(record['WeatherElement']['RelativeHumidity']) if record['WeatherElement']['RelativeHumidity'] else None,
                        'observation_time': record['ObsTime']['DateTime']
                    }
                    
                    stations.append(station_info)
                    
            except (KeyError, ValueError, TypeError, IndexError) as e:
                print(f"解析站點資料時發生錯誤 {record.get('StationId', 'Unknown')}: {e}")
                continue
        
        return stations
    
    def create_interactive_map(self, stations_data):
        """創建互動式HTML地圖"""
        if not stations_data:
            print("沒有資料可繪製")
            return None
        
        # 計算台灣中心點作為地圖初始中心
        all_lats = [s['lat1'] for s in stations_data] + [s['lat2'] for s in stations_data]
        all_lons = [s['lon1'] for s in stations_data] + [s['lon2'] for s in stations_data]
        
        center_lat = sum(all_lats) / len(all_lats)
        center_lon = sum(all_lons) / len(all_lons)
        
        # 創建地圖
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=7,
            tiles='OpenStreetMap'
        )
        
        # 添加不同的圖層
        feature_group1 = folium.FeatureGroup(name=f"坐標系統1 (TWD67作為WGS84)", show=True)
        feature_group2 = folium.FeatureGroup(name=f"坐標系統2 (WGS84)", show=True)
        connection_group = folium.FeatureGroup(name="坐標連接線", show=False)
        
        # 創建距離差異的顏色映射
        distances = [s['distance_diff'] for s in stations_data]
        min_dist, max_dist = min(distances), max(distances)
        
        colormap = cm.LinearColormap(
            colors=['blue', 'green', 'yellow', 'red'],
            vmin=min_dist,
            vmax=max_dist,
            caption='坐標距離差異 (米)'
        )
        
        # 添加標記和連接線
        for station in stations_data:
            # 坐標系統1的標記（藍色圓形）
            popup1 = folium.Popup(f"""
            <b>{station['station_name']}</b><br>
            <b>坐標系統1 ({station['coord1_name']})</b><br>
            坐標: ({station['lat1']:.6f}, {station['lon1']:.6f})<br>
            溫度: {station['temperature']}°C<br>
            濕度: {station['humidity']}%<br>
            觀測時間: {station['observation_time']}
            """, max_width=300)
            
            folium.CircleMarker(
                location=[station['lat1'], station['lon1']],
                radius=6,
                popup=popup1,
                color='blue',
                fill=True,
                fillColor='blue',
                fillOpacity=0.7,
                weight=2
            ).add_to(feature_group1)
            
            # 坐標系統2的標記（紅色方形）
            popup2 = folium.Popup(f"""
            <b>{station['station_name']}</b><br>
            <b>坐標系統2 ({station['coord2_name']})</b><br>
            坐標: ({station['lat2']:.6f}, {station['lon2']:.6f})<br>
            溫度: {station['temperature']}°C<br>
            濕度: {station['humidity']}%<br>
            <b>距離差異: {station['distance_diff']:.2f} 米</b><br>
            觀測時間: {station['observation_time']}
            """, max_width=300)
            
            folium.RegularPolygonMarker(
                location=[station['lat2'], station['lon2']],
                popup=popup2,
                number_of_sides=4,
                radius=6,
                rotation=45,
                color='red',
                fill=True,
                fillColor=colormap(station['distance_diff']),
                fillOpacity=0.7,
                weight=2
            ).add_to(feature_group2)
            
            # 連接兩個坐標的線條
            folium.PolyLine(
                locations=[[station['lat1'], station['lon1']], [station['lat2'], station['lon2']]],
                color=colormap(station['distance_diff']),
                weight=2,
                opacity=0.6,
                popup=f"{station['station_name']} - 距離差異: {station['distance_diff']:.2f}米"
            ).add_to(connection_group)
        
        # 添加圖層到地圖
        feature_group1.add_to(m)
        feature_group2.add_to(m)
        connection_group.add_to(m)
        
        # 添加圖層控制
        folium.LayerControl().add_to(m)
        
        # 添加顏色條
        colormap.add_to(m)
        
        # 添加圖例
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 50px; left: 50px; width: 200px; height: 120px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:14px; padding: 10px">
        <h4>圖例</h4>
        <p><i class="fa fa-circle" style="color:blue"></i> 坐標系統1 (TWD67)</p>
        <p><i class="fa fa-square" style="color:red"></i> 坐標系統2 (WGS84)</p>
        <p><i class="fa fa-minus" style="color:green"></i> 連接線 (距離差異)</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
        
        return m
    
    def generate_statistics_summary(self, stations_data):
        """生成統計摘要"""
        if not stations_data:
            return None
        
        distances = [s['distance_diff'] for s in stations_data]
        
        summary = {
            'total_stations': len(stations_data),
            'avg_distance': sum(distances) / len(distances),
            'min_distance': min(distances),
            'max_distance': max(distances),
            'median_distance': sorted(distances)[len(distances)//2]
        }
        
        return summary
    
    def save_map_with_stats(self, stations_data, filename=None):
        """儲存帶有統計資訊的HTML地圖"""
        if not stations_data:
            print("沒有資料可儲存")
            return None
        
        # 創建地圖
        m = self.create_interactive_map(stations_data)
        
        if m is None:
            return None
        
        # 生成統計摘要
        stats = self.generate_statistics_summary(stations_data)
        
        # 添加統計資訊到地圖
        stats_html = f'''
        <div style="position: fixed; 
                    top: 10px; right: 10px; width: 250px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:12px; padding: 10px; box-shadow: 3px 3px 3px rgba(0,0,0,0.3);">
        <h4>坐標差異統計</h4>
        <p><b>總測站數:</b> {stats['total_stations']}</p>
        <p><b>平均距離差異:</b> {stats['avg_distance']:.2f} 米</p>
        <p><b>中位數距離:</b> {stats['median_distance']:.2f} 米</p>
        <p><b>最小距離:</b> {stats['min_distance']:.2f} 米</p>
        <p><b>最大距離:</b> {stats['max_distance']:.2f} 米</p>
        <hr>
        <p><small>藍色圓形 = TWD67坐標</small></p>
        <p><small>紅色方形 = WGS84坐標</small></p>
        <p><small>連接線顏色 = 距離差異</small></p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(stats_html))
        
        # 儲存檔案
        if filename is None:
            filename = 'outputs/coordinate_comparison_map.html'
        
        m.save(filename)
        print(f"互動式地圖已儲存至: {filename}")
        return filename

def main():
    """主程式"""
    print("開始生成氣象站坐標系統互動式地圖...")
    
    try:
        # 初始化分析器
        analyzer = CoordinateMapAnalyzer()
        
        # 獲取資料
        print("正在從 CWA API 獲取資料...")
        raw_data = analyzer.fetch_weather_data()
        
        if raw_data:
            print("成功獲取資料，正在解析雙坐標系統...")
            
            # 解析雙坐標資料
            stations_data = analyzer.parse_dual_coordinates(raw_data)
            
            if stations_data:
                print(f"成功解析 {len(stations_data)} 個測站的雙坐標資料")
                
                # 生成統計摘要
                stats = analyzer.generate_statistics_summary(stations_data)
                if stats:
                    print(f"\n=== 坐標差異統計摘要 ===")
                    print(f"總測站數: {stats['total_stations']}")
                    print(f"平均距離差異: {stats['avg_distance']:.2f} 米")
                    print(f"中位數距離: {stats['median_distance']:.2f} 米")
                    print(f"最小距離: {stats['min_distance']:.2f} 米")
                    print(f"最大距離: {stats['max_distance']:.2f} 米")
                
                # 生成並儲存互動式地圖
                print("正在生成互動式HTML地圖...")
                map_file = analyzer.save_map_with_stats(stations_data)
                
                if map_file:
                    print(f"\n✅ 完成！請在瀏覽器中開啟: {map_file}")
                    print("📌 地圖功能:")
                    print("   - 藍色圓形標記: TWD67坐標（當作WGS84顯示）")
                    print("   - 紅色方形標記: WGS84坐標")
                    print("   - 連接線顏色表示距離差異大小")
                    print("   - 可點擊標記查看詳細資訊")
                    print("   - 右上角圖層控制可切換顯示")
                
            else:
                print("解析雙坐標資料失敗")
        else:
            print("獲取資料失敗")
            
    except Exception as e:
        print(f"程式執行發生錯誤: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
