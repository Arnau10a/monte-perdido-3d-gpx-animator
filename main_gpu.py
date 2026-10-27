import os
import sys
import math
import io
import urllib.request
from datetime import datetime, timezone
import gpxpy
import numpy as np
from PIL import Image

try:
    import pyvista as pv
except ImportError:
    print("❌ PyVista no está instalado.")
    sys.exit(1)

CACHE_DIR = ".tile_cache"

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

# Descarga de elevación Mapbox Terrain-RGB (0.1m precisión suave) y textura satélite HD (Zoom 14)
def load_terrain_and_texture(bbox, zoom=14):
    print(f"🌍 Descargando Malla 3D Ultra-Precisa (Mapbox 0.1m DEM) y Satélite HD (Zoom {zoom})...")
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
    
    # Token público Mapbox Terrain-RGB para 0.1m de precisión continua en altura
    mb_token = os.environ.get("MAPBOX_ACCESS_TOKEN", "YOUR_MAPBOX_ACCESS_TOKEN")

    for i, x in enumerate(range(x_min, x_max + 1)):
        for j, y in enumerate(range(y_min, y_max + 1)):
            tile_count += 1
            sys.stdout.write(f"\r⏳ [Cargando] Descargando relieve suave 0.1m HD... {tile_count}/{total_tiles} teselas")
            sys.stdout.flush()
            
            # 1. Satélite HD (Esri World Imagery)
            sat_url = f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{zoom}/{y}/{x}"
            sat_data = fetch_tile(sat_url, f"sat_{zoom}_{x}_{y}.jpg")
            if sat_data:
                tile_img = Image.open(io.BytesIO(sat_data)).convert('RGB')
                sat_img_composite.paste(tile_img, (i * tile_size, j * tile_size))
                
            # 2. Mapbox Terrain-RGB (0.1m precisión continua sin escalones)
            ele_url = f"https://api.mapbox.com/v4/mapbox.terrain-rgb/{zoom}/{x}/{y}.pngraw?access_token={mb_token}"
            ele_data = fetch_tile(ele_url, f"ele_mb_{zoom}_{x}_{y}.png")
            if ele_data:
                ele_img = Image.open(io.BytesIO(ele_data))
                ele_arr = np.array(ele_img, dtype=np.float32)
                # Fórmula Mapbox Terrain-RGB: -10000 + ((R * 65536 + G * 256 + B) * 0.1)
                h = -10000.0 + ((ele_arr[:, :, 0] * 65536.0 + ele_arr[:, :, 1] * 256.0 + ele_arr[:, :, 2]) * 0.1)
                ele_grid[j*tile_size:(j+1)*tile_size, i*tile_size:(i+1)*tile_size] = h

    print("\n✅ Malla 3D de alta precisión y textura satélite cargadas correctamente.")
    
    nw_lat, nw_lon = num2deg(x_min, y_min, zoom)
    se_lat, se_lon = num2deg(x_max + 1, y_max + 1, zoom)
    
    lons_vec = np.linspace(nw_lon, se_lon, num_x * tile_size)
    lats_vec = np.linspace(nw_lat, se_lat, num_y * tile_size)
    
    X, Y = np.meshgrid(lons_vec, lats_vec)
    
    sat_img_path = os.path.join(CACHE_DIR, "sat_composite.png")
    sat_img_composite.save(sat_img_path)
    
    return X, Y, ele_grid, sat_img_path

def parse_gpx_files(gpx_paths):
    all_points = []
    for path in gpx_paths:
        if not os.path.exists(path):
            continue
        with open(path, 'r', encoding='utf-8') as f:
            gpx = gpxpy.parse(f)
            for track in gpx.tracks:
                for segment in track.segments:
                    for p in segment.points:
                        t = p.time if p.time.tzinfo else p.time.replace(tzinfo=timezone.utc)
                        all_points.append({
                            'lat': p.latitude,
                            'lon': p.longitude,
                            'ele': p.elevation,
                            'time': t.timestamp()
                        })
    all_points.sort(key=lambda x: x['time'])
    return all_points

def render_gpu_video(track_points, output_file="animacion_ruta_gpu_2k.mp4", duration=30, fps=30, interactive=False):
    # 1. Filtrado de puntos saturados/agrupados por distancia (distancia mínima de 5m entre puntos)
    raw_lons = np.array([p['lon'] for p in track_points])
    raw_lats = np.array([p['lat'] for p in track_points])
    raw_eles = np.array([p['ele'] for p in track_points])

    center_lon = raw_lons.mean()
    center_lat = raw_lats.mean()
    lat_rad = math.radians(center_lat)
    
    m_per_deg_lat = 111139.0
    m_per_deg_lon = 111139.0 * math.cos(lat_rad)

    raw_x = (raw_lons - center_lon) * m_per_deg_lon
    raw_y = (raw_lats - center_lat) * m_per_deg_lat
    
    # Filtrar puntos que están demasiado cerca (menos de 5m del anterior) para eliminar pausas/saturación
    filtered_x = [raw_x[0]]
    filtered_y = [raw_y[0]]
    filtered_z = [raw_eles[0]]
    
    for i in range(1, len(raw_x)):
        dist = math.hypot(raw_x[i] - filtered_x[-1], raw_y[i] - filtered_y[-1])
        if dist >= 5.0:  # Mínimo 5 metros de separación
            filtered_x.append(raw_x[i])
            filtered_y.append(raw_y[i])
            filtered_z.append(raw_eles[i])

    route_x = np.array(filtered_x)
    route_y = np.array(filtered_y)
    eles = np.array(filtered_z)
    total_pts = len(route_x)

    # Bounding box amplio
    margin_x = max(np.ptp(route_x) * 0.15, 500)
    margin_y = max(np.ptp(route_y) * 0.15, 500)
    
    bbox = {
        'min_lat': (route_y.min() - margin_y) / m_per_deg_lat + center_lat,
        'max_lat': (route_y.max() + margin_y) / m_per_deg_lat + center_lat,
        'min_lon': (route_x.min() - margin_x) / m_per_deg_lon + center_lon,
        'max_lon': (route_x.max() + margin_x) / m_per_deg_lon + center_lon
    }

    X_deg, Y_deg, Z, sat_tex_path = load_terrain_and_texture(bbox, zoom=14)

    print("⚡ Inicializando renderizado 3D acelerado por GPU (PyVista/OpenGL)...")
    try:
        gpu_info = pv.GPUInfo()
        print(f"🎮 GPU Detectada: {gpu_info.renderer} ({gpu_info.vendor})")
    except Exception:
        pass

    # Coordenadas en metros
    X_m = (X_deg - center_lon) * m_per_deg_lon
    Y_m = (Y_deg - center_lat) * m_per_deg_lat

    # Suavizado de terreno
    Z_pad = np.pad(Z, 1, mode='edge')
    Z_smooth = (Z_pad[:-2, :-2] + Z_pad[:-2, 1:-1] + Z_pad[:-2, 2:] +
                Z_pad[1:-1, :-2] + Z_pad[1:-1, 1:-1] + Z_pad[1:-1, 2:] +
                Z_pad[2:, :-2] + Z_pad[2:, 1:-1] + Z_pad[2:, 2:]) / 9.0

    grid = pv.StructuredGrid(X_m, Y_m, Z_smooth)
    
    ny, nx = Z_smooth.shape
    x_min_m, x_max_m = X_m[0, 0], X_m[0, -1]
    y_min_m, y_max_m = Y_m[0, 0], Y_m[-1, 0]
    
    cols = np.clip(np.int32((route_x - x_min_m) / (x_max_m - x_min_m + 1e-6) * (nx - 1)), 0, nx - 1)
    rows = np.clip(np.int32((route_y - y_min_m) / (y_max_m - y_min_m + 1e-6) * (ny - 1)), 0, ny - 1)
    
    terrain_at_route = Z_smooth[rows, cols]
    route_z = np.maximum(eles, terrain_at_route) + 14.0
    
    u, v = np.meshgrid(np.linspace(0, 1, nx), np.linspace(1, 0, ny))
    grid.active_texture_coordinates = np.column_stack((u.ravel(), v.ravel()))
    
    texture = pv.read_texture(sat_tex_path)

    plotter = pv.Plotter(off_screen=not interactive, window_size=[2560, 1440])
    plotter.set_background("#0B0E14")
    plotter.add_mesh(grid, texture=texture, smooth_shading=True, specular=0.1)

    points_3d = np.column_stack((route_x, route_y, route_z))
    step_tube = max(1, len(points_3d) // 800)
    sub_points_3d = points_3d[::step_tube]
    route_tube = pv.Spline(sub_points_3d, n_points=1400).tube(radius=3.5)
    plotter.add_mesh(route_tube, color="#FF2D55", smooth_shading=True)

    max_idx = np.argmax(route_z)
    min_idx = np.argmin(route_z[:len(route_z)//2])
    
    goriz_candidates = np.where((eles > 2150) & (eles < 2250))[0]
    goriz_idx = goriz_candidates[len(goriz_candidates)//2] if len(goriz_candidates) > 0 else len(route_z)//3
    
    cola_candidates = np.where((eles > 1700) & (eles < 1850))[0]
    cola_idx = cola_candidates[0] if len(cola_candidates) > 0 else len(route_z)//5

    landmark_indices = [min_idx, cola_idx, goriz_idx, max_idx]
    landmark_names = [
        "Pradera de Ordesa (1.300m)",
        "Cascada Cola de Caballo",
        "Refugio de Goriz (2.200m)",
        "MONTE PERDIDO (3.355m)"
    ]

    landmarks_pos = []
    for idx, name in zip(landmark_indices, landmark_names):
        p_ground = points_3d[idx].copy()
        p_top = p_ground + [0, 0, 110]
        landmarks_pos.append(p_top)
        
        line_post = pv.Line(p_ground, p_top)
        plotter.add_mesh(line_post.tube(radius=1.8), color="#FFD700")
        
        sphere_base = pv.Sphere(radius=7, center=p_ground)
        plotter.add_mesh(sphere_base, color="#FFD700")

    plotter.add_point_labels(
        np.array(landmarks_pos), 
        [f"  {n}  " for n in landmark_names], 
        font_size=22, 
        text_color="white", 
        shape="rounded_rect", 
        shape_color="#181E2A", 
        shape_opacity=0.9,
        always_visible=True,
        shadow=True
    )

    if interactive:
        print("🎮 Abriendo ventana interactiva 3D con la GPU...")
        plotter.show()
        return

    print(f"🎬 Renderizando seguimiento con pausas en puntos clave por GPU ({duration}s a {fps} fps)...")
    plotter.open_movie(output_file, framerate=fps)

    total_frames = duration * fps
    landmark_progress = [idx / (total_pts - 1) for idx in landmark_indices]
    
    t_samples = np.linspace(0, 1, total_frames)
    progress_samples = []
    
    current_p = 0.0
    for t_i in range(total_frames):
        p = t_i / (total_frames - 1)
        near_landmark = any(abs(p - lp) < 0.03 for lp in landmark_progress)
        speed = 0.25 if near_landmark else 1.0
        
        if t_i > 0:
            current_p += (1.0 / total_frames) * speed
        progress_samples.append(current_p)

    progress_samples = np.array(progress_samples)
    progress_samples = progress_samples / progress_samples[-1]

    curr_cam_pos = None
    curr_target_pos = None
    alpha = 0.86

    for frame in range(total_frames):
        t_factor = progress_samples[frame]
        curr_idx = min(int(t_factor * total_pts), total_pts - 1)
        look_idx = min(curr_idx + max(15, int(total_pts * 0.03)), total_pts - 1)
        
        curr_p = points_3d[curr_idx]
        look_p = points_3d[look_idx]
        
        dir_v = look_p - curr_p
        dir_len = np.linalg.norm(dir_v[:2])
        if dir_len < 0.001:
            dir_v = np.array([1.0, 0.0, 0.0])
        else:
            dir_v = dir_v / dir_len
            
        target_cam_x = curr_p[0] - dir_v[0] * 320
        target_cam_y = curr_p[1] - dir_v[1] * 320
        target_cam_z = curr_p[2] + 200
        raw_cam = np.array([target_cam_x, target_cam_y, target_cam_z])
        
        raw_target = np.array([look_p[0], look_p[1], look_p[2] + 35])

        if curr_cam_pos is None:
            curr_cam_pos = raw_cam
            curr_target_pos = raw_target
        else:
            curr_cam_pos = curr_cam_pos * alpha + raw_cam * (1.0 - alpha)
            curr_target_pos = curr_target_pos * alpha + raw_target * (1.0 - alpha)
        
        plotter.camera_position = [
            (curr_cam_pos[0], curr_cam_pos[1], curr_cam_pos[2]),
            (curr_target_pos[0], curr_target_pos[1], curr_target_pos[2]),
            (0, 0, 1)
        ]
        
        sys.stdout.write(f"\r🚀 GPU Frame {frame+1}/{total_frames} ({(frame+1)/total_frames*100:.1f}%)")
        sys.stdout.flush()
        
        plotter.write_frame()

    plotter.close()
    print(f"\n✨ ¡VÍDEO 2K CON PAUSAS EN PUNTOS CLAVE Y LÍNEAS 3D COMPLETADO! Guardado como '{output_file}'.")

if __name__ == '__main__':
    GPX_FILES = [
        "Dia_1_Monte_Perdido_Valle_de_Ordesa_Refugio_Goriz_Senda_de_los_cazadores_.gpx",
        "Dia_2_Monte_Perdido_Dia_2_Monte_Perdido_Refugio_Goriz_Monte_Perdido_3355m_Refugio_Goriz.gpx",
        "Dia_2_Monte_Perdido_Refugio_Goriz_Cola_de_Caballo_Valle_de_Ordesa.gpx"
    ]
    
    track = parse_gpx_files(GPX_FILES)
    render_gpu_video(track, duration=30, fps=30, interactive=False)
