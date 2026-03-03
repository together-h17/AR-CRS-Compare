#!/usr/bin/env python3
"""
氣象站坐標系統比較分析腳本
比較氣象站API中的兩個不同坐標系統，並計算其距離差異
"""

import os
import requests
import json
import math
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from dotenv import load_dotenv
import seaborn as sns

# 設定中文字體
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False

# 載入環境變數
load_dotenv()

class CoordinateAnalyzer:
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
                        
                        # 第一個坐標系統（假設為WGS84）
                        'lat1': float(coord1['StationLatitude']),
                        'lon1': float(coord1['StationLongitude']),
                        'coord1_name': coord1.get('CoordinateName', 'Coordinate1'),
                        
                        # 第二個坐標系統（假設為WGS84）
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
    
    def plot_coordinate_comparison(self, stations_data):
        """繪製坐標比較圖"""
        if not stations_data:
            print("沒有資料可繪製")
            return
        
        # 建立圖表
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('氣象站雙坐標系統比較分析', fontsize=16, fontweight='bold')
        
        # 提取坐標資料
        lats1 = [s['lat1'] for s in stations_data]
        lons1 = [s['lon1'] for s in stations_data]
        lats2 = [s['lat2'] for s in stations_data]
        lons2 = [s['lon2'] for s in stations_data]
        distances = [s['distance_diff'] for s in stations_data]
        station_names = [s['station_name'] for s in stations_data]
        
        # 1. 坐標散佈圖比較
        ax1 = axes[0, 0]
        ax1.scatter(lons1, lats1, c='blue', alpha=0.6, label='坐標系統1', s=30)
        ax1.scatter(lons2, lats2, c='red', alpha=0.6, label='坐標系統2', s=30)
        ax1.set_xlabel('經度')
        ax1.set_ylabel('緯度')
        ax1.set_title('氣象站位置分佈比較')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 2. 距離差異直方圖
        ax2 = axes[0, 1]
        ax2.hist(distances, bins=30, alpha=0.7, color='green', edgecolor='black')
        ax2.set_xlabel('距離差異 (米)')
        ax2.set_ylabel('測站數量')
        ax2.set_title('坐標系統間距離差異分佈')
        ax2.grid(True, alpha=0.3)
        
        # 3. 緯度差異 vs 經度差異散佈圖
        ax3 = axes[1, 0]
        lat_diffs = [abs(s['lat1'] - s['lat2']) for s in stations_data]
        lon_diffs = [abs(s['lon1'] - s['lon2']) for s in stations_data]
        scatter = ax3.scatter(lon_diffs, lat_diffs, c=distances, cmap='viridis', alpha=0.6)
        ax3.set_xlabel('經度差異 (度)')
        ax3.set_ylabel('緯度差異 (度)')
        ax3.set_title('坐標差異分佈')
        plt.colorbar(scatter, ax=ax3, label='距離差異 (米)')
        ax3.grid(True, alpha=0.3)
        
        # 4. 距離差異箱型圖（按縣市分組）
        ax4 = axes[1, 1]
        # 按縣市分組
        counties = {}
        for station in stations_data:
            county = station['location'][:3]  # 取前3個字元作為縣市
            if county not in counties:
                counties[county] = []
            counties[county].append(station['distance_diff'])
        
        # 只顯示測站數量較多的縣市
        valid_counties = {k: v for k, v in counties.items() if len(v) >= 5}
        if valid_counties:
            ax4.boxplot(valid_counties.values(), labels=valid_counties.keys(), vert=False)
            ax4.set_xlabel('距離差異 (米)')
            ax4.set_title('各縣市坐標距離差異分佈')
            plt.setp(ax4.get_xticklabels(), rotation=45)
        else:
            ax4.text(0.5, 0.5, '資料不足', ha='center', va='center', transform=ax4.transAxes)
            ax4.set_title('各縣市坐標距離差異分佈')
        
        plt.tight_layout()
        
        # 儲存圖表
        output_file = 'outputs/coordinate_comparison.png'
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"比較圖已儲存至: {output_file}")
        
        plt.show()
    
    def generate_statistics_report(self, stations_data):
        """生成統計報告"""
        if not stations_data:
            return None
        
        distances = [s['distance_diff'] for s in stations_data]
        lat_diffs = [abs(s['lat1'] - s['lat2']) for s in stations_data]
        lon_diffs = [abs(s['lon1'] - s['lon2']) for s in stations_data]
        
        report = {
            'total_stations': len(stations_data),
            'distance_stats': {
                'mean': np.mean(distances),
                'median': np.median(distances),
                'std': np.std(distances),
                'min': np.min(distances),
                'max': np.max(distances),
                'q25': np.percentile(distances, 25),
                'q75': np.percentile(distances, 75)
            },
            'lat_diff_stats': {
                'mean': np.mean(lat_diffs),
                'median': np.median(lat_diffs),
                'std': np.std(lat_diffs),
                'min': np.min(lat_diffs),
                'max': np.max(lat_diffs)
            },
            'lon_diff_stats': {
                'mean': np.mean(lon_diffs),
                'median': np.median(lon_diffs),
                'std': np.std(lon_diffs),
                'min': np.min(lon_diffs),
                'max': np.max(lon_diffs)
            }
        }
        
        return report
    
    def save_detailed_data(self, stations_data, filename=None):
        """儲存詳細的坐標比較資料"""
        if not stations_data:
            print("沒有資料可儲存")
            return
        
        if filename is None:
            filename = 'outputs/coordinate_comparison_detailed.csv'
        
        df = pd.DataFrame(stations_data)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"詳細資料已儲存至: {filename}")
        return filename

def main():
    """主程式"""
    print("開始分析氣象站雙坐標系統...")
    
    try:
        # 初始化分析器
        analyzer = CoordinateAnalyzer()
        
        # 獲取資料
        print("正在從 CWA API 獲取資料...")
        raw_data = analyzer.fetch_weather_data()
        
        if raw_data:
            print("成功獲取資料，正在解析雙坐標系統...")
            
            # 解析雙坐標資料
            stations_data = analyzer.parse_dual_coordinates(raw_data)
            
            if stations_data:
                print(f"成功解析 {len(stations_data)} 個測站的雙坐標資料")
                
                # 生成統計報告
                report = analyzer.generate_statistics_report(stations_data)
                if report:
                    print("\n=== 坐標差異統計報告 ===")
                    print(f"總測站數: {report['total_stations']}")
                    print(f"\n距離差異統計 (米):")
                    print(f"  平均值: {report['distance_stats']['mean']:.2f}")
                    print(f"  中位數: {report['distance_stats']['median']:.2f}")
                    print(f"  標準差: {report['distance_stats']['std']:.2f}")
                    print(f"  最小值: {report['distance_stats']['min']:.2f}")
                    print(f"  最大值: {report['distance_stats']['max']:.2f}")
                    print(f"  第25百分位: {report['distance_stats']['q25']:.2f}")
                    print(f"  第75百分位: {report['distance_stats']['q75']:.2f}")
                    
                    print(f"\n緯度差異統計 (度):")
                    print(f"  平均值: {report['lat_diff_stats']['mean']:.6f}")
                    print(f"  中位數: {report['lat_diff_stats']['median']:.6f}")
                    print(f"  標準差: {report['lat_diff_stats']['std']:.6f}")
                    print(f"  範圍: {report['lat_diff_stats']['min']:.6f} - {report['lat_diff_stats']['max']:.6f}")
                    
                    print(f"\n經度差異統計 (度):")
                    print(f"  平均值: {report['lon_diff_stats']['mean']:.6f}")
                    print(f"  中位數: {report['lon_diff_stats']['median']:.6f}")
                    print(f"  標準差: {report['lon_diff_stats']['std']:.6f}")
                    print(f"  範圍: {report['lon_diff_stats']['min']:.6f} - {report['lon_diff_stats']['max']:.6f}")
                
                # 顯示距離差異最大的前10個測站
                sorted_stations = sorted(stations_data, key=lambda x: x['distance_diff'], reverse=True)
                print("\n=== 距離差異最大的前10個測站 ===")
                for i, station in enumerate(sorted_stations[:10]):
                    print(f"{i+1}. {station['station_name']} ({station['location']})")
                    print(f"   距離差異: {station['distance_diff']:.2f} 米")
                    print(f"   坐標1: ({station['lat1']:.6f}, {station['lon1']:.6f}) - {station['coord1_name']}")
                    print(f"   坐標2: ({station['lat2']:.6f}, {station['lon2']:.6f}) - {station['coord2_name']}")
                    print()
                
                # 儲存詳細資料
                analyzer.save_detailed_data(stations_data)
                
                # 繪製比較圖
                print("正在生成坐標比較圖...")
                analyzer.plot_coordinate_comparison(stations_data)
                
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
