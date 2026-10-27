import os
import sys
import math
import io
import urllib.request
from datetime import datetime, timezone
import gpxpy
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource
from mpl_toolkits.mplot3d import Axes3D
from PIL import Image
from moviepy import VideoClip

CACHE_DIR = ".tile_cache"

# --- UTILIDADES GEO Y MAPAS ---

def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.log(math.tan(lat_rad) + (1.0 / math.cos(lat_rad))) / math.pi) / 2.0 * n)
    return (xtile, ytile)

def num2deg(xtile, ytile, zoom):
    n = 2.0 ** zoom
    lon_deg = xtile / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
    lat_deg = math.degrees(lat_rad)
    return (lat_deg, lon_deg)

def fetch_tile(url, cache_filename):
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(CACHE_DIR, cache_filename)
    if os.path.exists(cache_path):
        with open(cache_path, 'rb') as f:
            return f.read()
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, timeout=12) as res:
            content = res.read()
            with open(cache_path, 'wb') as f:
                f.write(content)
            return content
    except Exception:
        pass
    return None

# Descarga de fototextura satélite y elevación DEM (Zoom 12)
def load_terrain_and_texture(bbox, zoom=12):
    print(f"🌍 Descargando datos de elevación 3D y ortofoto satélite en MÁXIMA RESOLUCIÓN (Zoom {zoom})...")
    x_min, y_min = deg2num(bbox['max_lat'], bbox['min_lon'], zoom)
    x_max, y_max = deg2num(bbox['min_lat'], bbox['max_lon'], zoom)
    
    x_min, x_max = min(x_min, x_max), max(x_min, x_max)
    y_min, y_max = min(y_min, y_max), max(y_min, y_max)
    
    num_x = x_max - x_min + 1
    num_y = y_max - y_min + 1
    
    tile_size = 256
    sat_img_composite = Image.new('RGB', (num_x * tile_size, num_y * tile_size))
    ele_grid = np.zeros((num_y * tile_size, num_x * tile_size))
    
    total_tiles = num_x * num_y
    tile_count = 0
    
    for i, x in enumerate(range(x_min, x_max + 1)):
        for j, y in enumerate(range(y_min, y_max + 1)):
            tile_count += 1
            sys.stdout.write(f"\r⏳ [Cargando] Descargando mapa y relieve HD... {tile_count}/{total_tiles} teselas")
            sys.stdout.flush()
            
            # 1. Satélite alta resolución (Esri World Imagery HD)
            sat_url = f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{zoom}/{y}/{x}"
            sat_data = fetch_tile(sat_url, f"sat_{zoom}_{x}_{y}.jpg")
            if sat_data:
                tile_img = Image.open(io.BytesIO(sat_data)).convert('RGB')
                sat_img_composite.paste(tile_img, (i * tile_size, j * tile_size))
                
            # 2. Elevación Terrarium (AWS)
            ele_url = f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{zoom}/{x}/{y}.png"
            ele_data = fetch_tile(ele_url, f"ele_{zoom}_{x}_{y}.png")
            if ele_data:
                ele_img = Image.open(io.BytesIO(ele_data))
                ele_arr = np.array(ele_img, dtype=np.float32)
                h = (ele_arr[:, :, 0] * 256.0 + ele_arr[:, :, 1] + ele_arr[:, :, 2] / 256.0) - 32768.0
                ele_grid[j*tile_size:(j+1)*tile_size, i*tile_size:(i+1)*tile_size] = h

    print("\n✅ Terreno 3D HD y textura satélite cargados correctamente.")
    
    nw_lat, nw_lon = num2deg(x_min, y_min, zoom)
    se_lat, se_lon = num2deg(x_max + 1, y_max + 1, zoom)
    
    lons_vec = np.linspace(nw_lon, se_lon, num_x * tile_size)
    lats_vec = np.linspace(nw_lat, se_lat, num_y * tile_size)
    
    X, Y = np.meshgrid(lons_vec, lats_vec)
    Z = ele_grid
    
    sat_colors = np.array(sat_img_composite, dtype=np.float32) / 255.0
    return X, Y, Z, sat_colors

# 1. Parsear GPX y calcular distancia acumulada
def parse_gpx_files(gpx_paths):
    all_points = []
    
    for path in gpx_paths:
        if not os.path.exists(path):
            print(f"⚠️ Archivo no encontrado: {path}")
            continue
            
        print(f"⏳ Cargando ruta GPX: {os.path.basename(path)}...")
        with open(path, 'r', encoding='utf-8') as f:
            gpx = gpxpy.parse(f)
        
        file_points = []
        for track in gpx.tracks:
            for segment in track.segments:
                for p in segment.points:
                    t = p.time if p.time.tzinfo else p.time.replace(tzinfo=timezone.utc)
                    file_points.append({
                        'lat': p.latitude,
                        'lon': p.longitude,
                        'ele': p.elevation,
                        'time': t.timestamp()
                    })
        
        if file_points:
            file_points.sort(key=lambda x: x['time'])
            all_points.extend(file_points)

    all_points.sort(key=lambda x: x['time'])
    
    # Calcular distancia acumulada en km (Haversine)
    cum_dist = [0.0]
    R = 6371.0  # Radio terrestre en km
    for i in range(1, len(all_points)):
        lat1, lon1 = math.radians(all_points[i-1]['lat']), math.radians(all_points[i-1]['lon'])
        lat2, lon2 = math.radians(all_points[i]['lat']), math.radians(all_points[i]['lon'])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        cum_dist.append(cum_dist[-1] + R * c)
        
    for p, d in zip(all_points, cum_dist):
        p['dist_km'] = d

    return all_points

# Renderizado Profesional 3D en Calidad 2K (2560x1440 px)
def render_3d_route_video(track_points, output_file="animacion_ruta_3d_2k.mp4", duration=30, fps=30):
    lons = np.array([p['lon'] for p in track_points])
    lats = np.array([p['lat'] for p in track_points])
    eles = np.array([p['ele'] for p in track_points])
    dists = np.array([p['dist_km'] for p in track_points])
    
    total_points = len(track_points)
    total_frames = duration * fps

    # Bounding box ajustado con margen óptimo
    dlat = lats.max() - lats.min()
    dlon = lons.max() - lons.min()
    margin_lat = max(dlat * 0.08, 0.003)
    margin_lon = max(dlon * 0.08, 0.003)
    
    bbox = {
        'min_lat': lats.min() - margin_lat,
        'max_lat': lats.max() + margin_lat,
        'min_lon': lons.min() - margin_lon,
        'max_lon': lons.max() + margin_lon
    }

    # Cargar mapa HD en Zoom 13 (equilibrio perfecto entre fluidez y detalle fotorrealista)
    X_terrain, Y_terrain, Z_terrain, sat_colors = load_terrain_and_texture(bbox, zoom=13)

    # Submuestreo suave (step=4 para terreno continuo y definido)
    step = 4
    X_s = X_terrain[::step, ::step]
    Y_s = Y_terrain[::step, ::step]
    Z_s = Z_terrain[::step, ::step]
    colors_s = sat_colors[::step, ::step]

    # Sombras de luz profesional (LightSource)
    ls = LightSource(azdeg=315, altdeg=45)
    shaded_colors = ls.shade_rgb(colors_s, Z_s, blend_mode='overlay', vert_exag=0.00004)

    # Configuración de figura 2K elegante con encuadre amplio
    fig = plt.figure(figsize=(25.6, 14.4), dpi=100, facecolor='#0B0E14')
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0], projection='3d', facecolor='#0B0E14')

    frame_count = [0]

    def make_frame(t):
        frame_count[0] += 1
        pct = (frame_count[0] / total_frames) * 100
        sys.stdout.write(f"\r🎬 [Cargando] Renderizando 3D 2K Nítido (2560x1440)... Frame {frame_count[0]}/{total_frames} ({pct:.1f}%)")
        sys.stdout.flush()

        # Limpiar figura y textos previos para evitar solapamientos borrosos
        fig.texts.clear()
        ax.clear()
        ax.set_facecolor('#0B0E14')
        
        progress = t / duration
        current_idx = max(1, int(progress * total_points))
        
        # 1. Renderizar terreno 3D fotorrealista continuo
        ax.plot_surface(X_s, Y_s, Z_s, facecolors=shaded_colors, rstride=1, cstride=1, 
                        shade=False, antialiased=True, alpha=0.98)
        
        # 2. Trazado de ruta completo (línea guía blanca punteada)
        ax.plot(lons, lats, eles + 18, color='#FFFFFF', linestyle=':', alpha=0.5, linewidth=2.5, zorder=8)
        
        # 3. Trazado activo recorrido (línea de neón rojo vívido #FF2D55)
        ax.plot(lons[:current_idx], lats[:current_idx], eles[:current_idx] + 18, color='#FF2D55', linewidth=5.5, zorder=10)
        
        # 4. Marcador de posición actual (badge dorado iluminado)
        if current_idx > 0:
            c_lon, c_lat, c_ele = lons[current_idx-1], lats[current_idx-1], eles[current_idx-1]
            ax.scatter(c_lon, c_lat, c_ele + 28, color='#FFD700', s=220, edgecolors='#FFFFFF', linewidth=2.0, zorder=12)
        
        # 5. Encuadre de cámara cercano y dinámico (ocupando la pantalla completa)
        elev_angle = 32 + 4 * math.sin(t * 0.1)
        azim_angle = (t * 8) % 360
        ax.view_init(elev=elev_angle, azim=azim_angle)
        
        # Escalar proporciones para que la montaña llene la pantalla
        ax.set_box_aspect((np.ptp(X_s), np.ptp(Y_s), np.ptp(Z_s) * 0.00005))
        ax.axis('off')
        
        # 6. Textos HUD limpios y legibles
        curr_dist = dists[current_idx-1] if current_idx > 0 else 0.0
        curr_ele = int(eles[current_idx-1]) if current_idx > 0 else 0
        
        fig.text(0.04, 0.93, "MONTE PERDIDO 3.355m | VALLE DE ORDESA", 
                 color='#FFFFFF', fontsize=26, fontweight='bold', alpha=0.95, family='sans-serif')
        fig.text(0.04, 0.89, f"DISTANCIA: {curr_dist:.1f} KM  |  ALTITUD: {curr_ele} M", 
                 color='#FF2D55', fontsize=18, fontweight='bold', alpha=0.95, family='sans-serif')
        
        fig.canvas.draw()
        rgba = np.asarray(fig.canvas.buffer_rgba())
        return rgba[:, :, :3]

    video = VideoClip(make_frame, duration=duration)

    print("\n⚙️ Generando archivo MP4 en resolución 2K nítida (2560x1440)...")
    num_threads = max(2, (os.cpu_count() or 4) - 1)
    video.write_videofile(output_file, fps=fps, codec='libx264', threads=num_threads)
    plt.close(fig)
    print(f"\n✨ ¡Animación 3D 2K Nítida lista! Guardada como '{output_file}'.")

if __name__ == '__main__':
    GPX_FILES = [
        "Dia_1_Monte_Perdido_Valle_de_Ordesa_Refugio_Goriz_Senda_de_los_cazadores_.gpx",
        "Dia_2_Monte_Perdido_Refugio_Goriz_Cola_de_Caballo_Valle_de_Ordesa.gpx",
        "Dia_2_Monte_Perdido_Dia_2_Monte_Perdido_Refugio_Goriz_Monte_Perdido_3355m_Refugio_Goriz.gpx"
    ]
    
    print("🚀 Generando clip 3D Nítido 2K para tu editor de vídeo...\n")
    track = parse_gpx_files(GPX_FILES)
    
    if not track:
        print("❌ No se pudieron cargar puntos de las rutas GPX.")
        sys.exit(1)
        
    print(f"\n🗺️ Puntos totales unificados: {len(track)}")
    render_3d_route_video(track, output_file="animacion_ruta_3d_2k.mp4", duration=30, fps=30)