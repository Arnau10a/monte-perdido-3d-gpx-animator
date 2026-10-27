import os
import math
import gpxpy

GPX_FILES = [
    "Dia_1_Monte_Perdido_Valle_de_Ordesa_Refugio_Goriz_Senda_de_los_cazadores_.gpx",
    "Dia_2_Monte_Perdido_Refugio_Goriz_Cola_de_Caballo_Valle_de_Ordesa.gpx",
    "Dia_2_Monte_Perdido_Dia_2_Monte_Perdido_Refugio_Goriz_Monte_Perdido_3355m_Refugio_Goriz.gpx"
]

OUTPUT_KML = "Monte_Perdido_Ruta_Completa.kml"

def gpx_to_kml(gpx_paths, output_kml):
    points = []
    for path in gpx_paths:
        if not os.path.exists(path):
            continue
        print(f"Procesando {os.path.basename(path)}...")
        with open(path, 'r', encoding='utf-8') as f:
            gpx = gpxpy.parse(f)
            for track in gpx.tracks:
                for segment in track.segments:
                    for p in segment.points:
                        points.append({'lon': p.longitude, 'lat': p.latitude, 'ele': p.elevation})

    if not points:
        print("No se encontraron puntos.")
        return

    # Línea de coordenadas pegada al terreno
    coord_strs = [f"{p['lon']},{p['lat']},{p['ele']}" for p in points]
    
    # Identificar puntos clave
    max_p = max(points, key=lambda p: p['ele'])  # Monte Perdido
    min_p = min(points[:len(points)//2], key=lambda p: p['ele'])  # Ordesa

    # Submuestrear cámara para gx:Tour (1 punto cada 60 para vuelo fluido)
    tour_points = points[::60]
    
    kml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:gx="http://www.google.com/kml/ext/2.2" xmlns:kml="http://www.opengis.net/kml/2.2" xmlns:atom="http://www.w3.org/2005/Atom">
  <Document>
    <name>Monte Perdido - Ruta 3D Google Earth</name>
    <open>1</open>
    
    <!-- Estilo de línea de neón rojo a ras de suelo -->
    <Style id="redRoute">
      <LineStyle>
        <color>ff552dff</color>
        <width>6</width>
      </LineStyle>
    </Style>
    
    <!-- Estilos de pines marcadores -->
    <Style id="pinKey">
      <IconStyle>
        <color>ff00ffff</color>
        <scale>1.3</scale>
        <Icon>
          <href>http://maps.google.com/mapfiles/kml/pushpin/ylw-pushpin.png</href>
        </Icon>
      </IconStyle>
    </Style>

    <!-- Marcadores de Puntos Clave -->
    <Placemark>
      <name>Pradera de Ordesa (1.300m)</name>
      <styleUrl>#pinKey</styleUrl>
      <Point>
        <coordinates>{min_p['lon']},{min_p['lat']},{min_p['ele']}</coordinates>
      </Point>
    </Placemark>

    <Placemark>
      <name>MONTE PERDIDO (3.355m)</name>
      <styleUrl>#pinKey</styleUrl>
      <Point>
        <coordinates>{max_p['lon']},{max_p['lat']},{max_p['ele']}</coordinates>
      </Point>
    </Placemark>

    <!-- Trazado de la ruta pegada a la superficie 3D de Google Earth -->
    <Placemark>
      <name>Ruta Monte Perdido y Ordesa</name>
      <styleUrl>#redRoute</styleUrl>
      <LineString>
        <tessellate>1</tessellate>
        <altitudeMode>clampToGround</altitudeMode>
        <coordinates>
          {" ".join(coord_strs)}
        </coordinates>
      </LineString>
    </Placemark>

    <!-- Recorrido de Cámara Animada 3D (Tour Dron) -->
    <gx:Tour>
      <name>▶ Vuelo Dron 3D por Ordesa y Monte Perdido</name>
      <gx:Playlist>
"""

    # Añadir los frames del tour volando sobre el terreno 3D
    for i in range(len(tour_points) - 1):
        p_curr = tour_points[i]
        p_next = tour_points[i+1]
        
        # Calcular rumbo (heading) de la cámara hacia adelante
        dlon = p_next['lon'] - p_curr['lon']
        dlat = p_next['lat'] - p_curr['lat']
        heading = math.degrees(math.atan2(dlon, dlat)) % 360
        
        kml_content += f"""        <gx:FlyTo>
          <gx:duration>0.6</gx:duration>
          <gx:flyToMode>smooth</gx:flyToMode>
          <LookAt>
            <longitude>{p_curr['lon']}</longitude>
            <latitude>{p_curr['lat']}</latitude>
            <altitude>{p_curr['ele']}</altitude>
            <heading>{heading:.1f}</heading>
            <tilt>68</tilt>
            <range>450</range>
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

    print(f"Archivo KML generado con exito para Google Earth Pro: '{output_kml}'")

if __name__ == '__main__':
    gpx_to_kml(GPX_FILES, OUTPUT_KML)
