import os
import math
import gpxpy
import numpy as np

GPX_FILES = [
    "Dia_1_Monte_Perdido_Valle_de_Ordesa_Refugio_Goriz_Senda_de_los_cazadores_.gpx",
    "Dia_2_Monte_Perdido_Dia_2_Monte_Perdido_Refugio_Goriz_Monte_Perdido_3355m_Refugio_Goriz.gpx",
    "Dia_2_Monte_Perdido_Refugio_Goriz_Cola_de_Caballo_Valle_de_Ordesa.gpx"
]

OUTPUT_KML = "Monte_Perdido_Tour_Desktop.kml"

def generate_desktop_tour_kml(gpx_paths, output_kml):
    points = []
    for path in gpx_paths:
        if not os.path.exists(path):
            continue
        print(f"Leyendo {os.path.basename(path)}...")
        with open(path, 'r', encoding='utf-8') as f:
            gpx = gpxpy.parse(f)
            for track in gpx.tracks:
                for segment in track.segments:
                    for p in segment.points:
                        points.append({'lon': p.longitude, 'lat': p.latitude, 'ele': p.elevation})

    if not points:
        print("No se encontraron puntos.")
        return

    # Submuestrear para animación fluida en la desktop (1 punto cada 45)
    tour_pts = points[::45]
    coord_strs = [f"{p['lon']},{p['lat']},{p['ele']}" for p in points]
    
    min_p = min(points[:len(points)//2], key=lambda p: p['ele'])
    max_p = max(points, key=lambda p: p['ele'])

    kml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:gx="http://www.google.com/kml/ext/2.2" xmlns:kml="http://www.opengis.net/kml/2.2" xmlns:atom="http://www.w3.org/2005/Atom">
  <Document>
    <name>Monte Perdido - 3D Cinematic Tour</name>
    <open>1</open>
    
    <!-- Estilo de trazado neón a ras de suelo -->
    <Style id="neonRedRoute">
      <LineStyle>
        <color>ff4422ff</color>
        <width>6</width>
      </LineStyle>
    </Style>

    <Style id="pinStyle">
      <IconStyle>
        <scale>1.3</scale>
        <Icon>
          <href>http://maps.google.com/mapfiles/kml/pushpin/ylw-pushpin.png</href>
        </Icon>
      </IconStyle>
    </Style>

    <!-- Marcadores clave -->
    <Placemark>
      <name>Pradera de Ordesa (1.300m)</name>
      <styleUrl>#pinStyle</styleUrl>
      <Point>
        <coordinates>{min_p['lon']},{min_p['lat']},{min_p['ele']}</coordinates>
      </Point>
    </Placemark>

    <Placemark>
      <name>MONTE PERDIDO (3.355m)</name>
      <styleUrl>#pinStyle</styleUrl>
      <Point>
        <coordinates>{max_p['lon']},{max_p['lat']},{max_p['ele']}</coordinates>
      </Point>
    </Placemark>

    <!-- Trazado de ruta a ras de suelo -->
    <Placemark>
      <name>Ruta Monte Perdido</name>
      <styleUrl>#neonRedRoute</styleUrl>
      <LineString>
        <tessellate>1</tessellate>
        <altitudeMode>clampToGround</altitudeMode>
        <coordinates>
          {" ".join(coord_strs)}
        </coordinates>
      </LineString>
    </Placemark>

    <!-- Vuelo de Cámara Animado 3D (Google Earth Pro Engine) -->
    <gx:Tour>
      <name>▶ Vuelo Dron 3D Monte Perdido</name>
      <gx:Playlist>
"""

    # Suavizado de orientación de cámara
    raw_headings = []
    for i in range(len(tour_pts) - 1):
        p_curr = tour_pts[i]
        p_next = tour_pts[i+1]
        dlon = p_next['lon'] - p_curr['lon']
        dlat = p_next['lat'] - p_curr['lat']
        h = math.degrees(math.atan2(dlon, dlat)) % 360
        raw_headings.append(h)
    raw_headings.append(raw_headings[-1])

    smooth_headings = []
    window_size = 5
    for i in range(len(raw_headings)):
        start_i = max(0, i - window_size)
        end_i = min(len(raw_headings), i + window_size + 1)
        sub_h = raw_headings[start_i:end_i]
        rads = [math.radians(angle) for angle in sub_h]
        mean_sin = np.mean([math.sin(r) for r in rads])
        mean_cos = np.mean([math.cos(r) for r in rads])
        smooth_headings.append(math.degrees(math.atan2(mean_sin, mean_cos)) % 360)

    for i in range(len(tour_pts) - 1):
        p_curr = tour_pts[i]
        heading = smooth_headings[i]
        
        tilt = 74.0 + 3.0 * math.sin(i * 0.1)
        camera_range = 150.0 + 30.0 * math.sin(i * 0.08)

        kml_content += f"""        <gx:FlyTo>
          <gx:duration>0.6</gx:duration>
          <gx:flyToMode>smooth</gx:flyToMode>
          <LookAt>
            <longitude>{p_curr['lon']}</longitude>
            <latitude>{p_curr['lat']}</latitude>
            <altitude>{p_curr['ele']}</altitude>
            <heading>{heading:.1f}</heading>
            <tilt>{tilt:.1f}</tilt>
            <range>{camera_range:.0f}</range>
            <altitudeMode>relativeToGround</altitudeMode>
          </LookAt>
        </gx:FlyTo>
"""

    kml_content += """      </gx:Playlist>
    </gx:Tour>
  </Document>
</kml>
"""

    with open(output_kml, 'w', encoding='utf-8') as f:
        f.write(kml_content)

    print(f"KML Tour Desktop generado con exito: '{output_kml}'")

if __name__ == '__main__':
    generate_desktop_tour_kml(GPX_FILES, OUTPUT_KML)
