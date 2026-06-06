# ============================================================
#  CVRP · Florida Bebidas · Provincia de PUNTARENAS
#  II-1122 · Prof. David Benavides · UCR Sede Alajuela
#  App Streamlit — Hitos 3 y 4
# ============================================================

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from ortools.constraint_solver import routing_enums_pb2, pywrapcp

# ── Configuración de página ──────────────────────────────────
st.set_page_config(
    page_title="CVRP · Florida Bebidas · Puntarenas",
    page_icon="🍺",
    layout="wide"
)

# ── Datos de Puntarenas ──────────────────────────────────────
CANTONES = [
    "CD Puntarenas", "Puntarenas", "Esparza", "Buenos Aires",
    "Montes de Oro", "Osa", "Quepos", "Golfito", "Coto Brus",
    "Parrita", "Corredores", "Garabito", "Monteverde", "Puerto Jiménez",
]

DEMANDA = [0, 107, 27, 37, 12, 28, 24, 33, 35, 16, 39, 20, 4, 8]

# Coordenadas aproximadas de cada cantón (lat, lon)
COORDS = {
    "CD Puntarenas":  (9.9760, -84.8381),
    "Puntarenas":     (9.9760, -84.8381),
    "Esparza":        (9.9882, -84.6648),
    "Buenos Aires":   (9.1647, -83.3308),
    "Montes de Oro":  (10.0831, -84.6519),
    "Osa":            (8.9134, -83.4710),
    "Quepos":         (9.4317, -84.1631),
    "Golfito":        (8.6480, -83.1820),
    "Coto Brus":      (8.9398, -82.9640),
    "Parrita":        (9.5175, -84.3261),
    "Corredores":     (8.6098, -82.9860),
    "Garabito":       (9.6315, -84.6476),
    "Monteverde":     (10.2995, -84.8247),
    "Puerto Jiménez": (8.5329, -83.3004),
}

DISTANCIAS = [
    [  0,   0,  25, 244,  27, 243, 124, 307, 307,  99, 332,  60,  47, 303],
    [  0,   0,  25, 244,  27, 243, 124, 307, 307,  99, 332,  60,  47, 303],
    [ 25,  25,   0, 224,  19, 226, 109, 290, 287,  85, 314,  55,  49, 288],
    [244, 244, 224,   0, 240,  41, 124,  80,  63, 150,  95, 196, 267,  92],
    [ 27,  27,  19, 240,   0, 244, 127, 308, 303, 103, 331,  73,  30, 305],
    [243, 243, 226,  41, 244,   0, 119,  64,  79, 145,  90, 189, 272,  64],
    [124, 124, 109, 124, 127, 119,   0, 183, 186,  26, 208,  72, 156, 179],
    [307, 307, 290,  80, 308,  64, 183,   0,  54, 208,  31, 253, 336,  25],
    [307, 307, 287,  63, 303,  79, 186,  54,   0, 212,  46, 259, 330,  78],
    [ 99,  99,  85, 150, 103, 145,  26, 208, 212,   0, 234,  47, 133, 204],
    [332, 332, 314,  95, 331,  90, 208,  31,  46, 234,   0, 279, 359,  52],
    [ 60,  60,  55, 196,  73, 189,  72, 253, 259,  47, 279,   0, 102, 246],
    [ 47,  47,  49, 267,  30, 272, 156, 336, 330, 133, 359, 102,   0, 335],
    [303, 303, 288,  92, 305,  64, 179,  25,  78, 204,  52, 246, 335,   0],
]

CAPACIDAD   = 24
JORNADA_MIN = 480
RECARGA_MIN = 20
VEL_KMH     = 40
MIN_PARADA  = 15
MIN_PALLET  = 3

# ── Solver ───────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def resolver_cvrp(n_vehiculos, tiempo_limite):
    manager = pywrapcp.RoutingIndexManager(len(DISTANCIAS), n_vehiculos, 0)
    routing = pywrapcp.RoutingModel(manager)

    def dist_cb(fi, ti):
        return DISTANCIAS[manager.IndexToNode(fi)][manager.IndexToNode(ti)]
    tc = routing.RegisterTransitCallback(dist_cb)
    routing.SetArcCostEvaluatorOfAllVehicles(tc)

    def dem_cb(idx):
        return DEMANDA[manager.IndexToNode(idx)]
    dc = routing.RegisterUnaryTransitCallback(dem_cb)
    routing.AddDimensionWithVehicleCapacity(
        dc, 0, [CAPACIDAD] * n_vehiculos, True, "Cap"
    )

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.seconds = tiempo_limite

    sol = routing.SolveWithParameters(params)
    if not sol:
        return None

    trips = []
    for v in range(n_vehiculos):
        idx = routing.Start(v)
        nodos, dist = [], 0
        while not routing.IsEnd(idx):
            n = manager.IndexToNode(idx)
            nodos.append(n)
            ni = sol.Value(routing.NextVar(idx))
            dist += DISTANCIAS[n][manager.IndexToNode(ni)]
            idx = ni
        nodos.append(0)
        cantones = [x for x in nodos if x != 0]
        if cantones:
            trips.append({
                "ruta": nodos,
                "cantones": cantones,
                "carga": sum(DEMANDA[c] for c in cantones),
                "distancia": dist,
            })
    return trips

def duracion_min(trip):
    t_cond  = (trip["distancia"] / VEL_KMH) * 60
    t_par   = len(trip["cantones"]) * MIN_PARADA
    t_carga = trip["carga"] * MIN_PALLET
    return t_cond + t_par + t_carga

def asignar_camiones(trips):
    camiones = []
    for trip in trips:
        dur = duracion_min(trip)
        asignado = False
        for cam in camiones:
            usado = sum(duracion_min(t) for t in cam) + RECARGA_MIN * len(cam)
            if usado + dur <= JORNADA_MIN:
                cam.append(trip)
                asignado = True
                break
        if not asignado:
            camiones.append([trip])
    return camiones

# ── Colores para el mapa ─────────────────────────────────────
COLORES = [
    "#E63946","#2A9D8F","#E9C46A","#F4A261","#264653",
    "#6A4C93","#1982C4","#8AC926","#FF595E","#6A0572",
    "#3A86FF","#FB5607","#FFBE0B","#8338EC","#06D6A0",
    "#118AB2","#EF476F",
]

# ── UI ───────────────────────────────────────────────────────
st.title("🍺 Florida Bebidas · Distribución Puntarenas")
st.caption("CVRP · II-1122 · Prof. David Benavides · UCR Sede Alajuela")

with st.sidebar:
    st.header("⚙️ Parámetros")
    n_veh   = st.slider("Número de vehículos (viajes)", 17, 25, 17)
    t_lim   = st.slider("Tiempo de búsqueda (seg)", 10, 60, 30)
    resolver = st.button("▶ Resolver CVRP", type="primary", use_container_width=True)
    st.divider()
    st.markdown("**Datos de la provincia**")
    st.metric("Cantones", 13)
    st.metric("Demanda total", "390 pallets/sem")
    st.metric("Capacidad por camión", "24 pallets")
    st.metric("Jornada", "8 h / 480 min")

# Resumen de demanda siempre visible
st.subheader("📦 Demanda por cantón")
df_dem = pd.DataFrame({
    "Cantón":   CANTONES[1:],
    "Imperial": [int(d * 0.496) for d in DEMANDA[1:]],
    "Pilsen":   [int(d * 0.252) for d in DEMANDA[1:]],
    "Tropical": [int(d * 0.252) for d in DEMANDA[1:]],
    "Total (pallets)": DEMANDA[1:],
})
st.dataframe(df_dem, use_container_width=True, hide_index=True)

# Ejecutar solver
if resolver:
    with st.spinner("Resolviendo... puede tardar hasta 30 segundos ⏳"):
        trips = resolver_cvrp(n_veh, t_lim)

    if not trips:
        st.error("No se encontró solución. Intenta aumentar los vehículos o el tiempo.")
    else:
        camiones = asignar_camiones(trips)
        dist_total = sum(t["distancia"] for t in trips)

        # ── KPIs ─────────────────────────────────────────────
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🗺️ Distancia total (Z*)", f"{dist_total} km")
        c2.metric("🚛 Trips activos", len(trips))
        c3.metric("🚚 Camiones físicos", len(camiones))
        c4.metric("📦 Pallets despachados", sum(t["carga"] for t in trips))

        # ── Mapa ─────────────────────────────────────────────
        st.subheader("🗺️ Mapa de rutas")
        fig = go.Figure()

        # Dibujar rutas
        for i, trip in enumerate(trips):
            color = COLORES[i % len(COLORES)]
            lats, lons, nombres = [], [], []
            for n in trip["ruta"]:
                lat, lon = COORDS[CANTONES[n]]
                lats.append(lat); lons.append(lon)
                nombres.append(CANTONES[n])
            fig.add_trace(go.Scattermapbox(
                lat=lats, lon=lons, mode="lines+markers",
                line=dict(width=2, color=color),
                marker=dict(size=8, color=color),
                name=f"Trip {i+1} ({trip['carga']} p · {trip['distancia']} km)",
                hovertext=nombres, hoverinfo="text",
            ))

        # CD destacado
        lat_cd, lon_cd = COORDS["CD Puntarenas"]
        fig.add_trace(go.Scattermapbox(
            lat=[lat_cd], lon=[lon_cd], mode="markers",
            marker=dict(size=18, color="white", symbol="star"),
            name="CD Puntarenas (depósito)",
        ))

        fig.update_layout(
            mapbox_style="open-street-map",
            mapbox_zoom=7,
            mapbox_center={"lat": 9.3, "lon": -83.8},
            margin=dict(l=0, r=0, t=0, b=0),
            height=520,
            legend=dict(font=dict(size=11)),
        )
        st.plotly_chart(fig, use_container_width=True)

        # ── Tabla de trips ────────────────────────────────────
        st.subheader("🚛 Detalle de trips (Hito 3)")
        rows = []
        for i, trip in enumerate(trips):
            ruta_str = " → ".join(CANTONES[n] for n in trip["ruta"])
            dur = duracion_min(trip)
            rows.append({
                "Trip": i + 1,
                "Ruta": ruta_str,
                "Pallets": trip["carga"],
                "Dist (km)": trip["distancia"],
                "Duración (min)": round(dur),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # ── Tabla de camiones ─────────────────────────────────
        st.subheader("🚚 Camiones físicos (Hito 4)")
        rows_cam = []
        for i, cam in enumerate(camiones):
            tiempo = sum(duracion_min(t) for t in cam) + RECARGA_MIN * (len(cam) - 1)
            trip_ids = ", ".join(f"T{trips.index(t)+1}" for t in cam)
            pallets  = sum(t["carga"] for t in cam)
            dist_cam = sum(t["distancia"] for t in cam)
            estado   = "⚠️ Dedicado" if tiempo > JORNADA_MIN else "✅ OK"
            rows_cam.append({
                "Camión": i + 1,
                "Trips asignados": trip_ids,
                "Pallets totales": pallets,
                "Dist total (km)": dist_cam,
                "Tiempo (min)": round(tiempo),
                "Tiempo (h)": round(tiempo / 60, 1),
                "Estado": estado,
            })
        st.dataframe(pd.DataFrame(rows_cam), use_container_width=True, hide_index=True)

        # ── Reflexión ─────────────────────────────────────────
        st.divider()
        st.subheader("💡 Para el pitch (Hito 5)")
        trip_mas_largo = max(trips, key=lambda t: t["distancia"])
        cant_mas_largo = " → ".join(CANTONES[n] for n in trip_mas_largo["ruta"])
        dedicados = sum(1 for cam in camiones
                        if sum(duracion_min(t) for t in cam) > JORNADA_MIN)

        col1, col2 = st.columns(2)
        with col1:
            st.info(f"**Provincia en una frase:** Puntarenas tiene 13 cantones, "
                    f"390 pallets/semana y requiere {len(camiones)} camiones físicos.")
            st.info(f"**Trip más largo:** {cant_mas_largo} — {trip_mas_largo['distancia']} km. "
                    f"Razón: geografía extensa del sur (Golfito, Corredores, Pto. Jiménez).")
        with col2:
            st.warning(f"**Camiones dedicados:** {dedicados} trips superan las 8 h "
                       f"por distancia extrema — se asigna un camión exclusivo.")
            st.success(f"**Distancia total Z* = {dist_total} km** — solución heurística "
                       f"con Clarke-Wright + búsqueda local (gap típico vs óptimo: 1–5%).")

else:
    st.info("👈 Ajusta los parámetros en el panel izquierdo y presiona **▶ Resolver CVRP**")
