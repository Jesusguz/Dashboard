# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║      NBA PROPS AI — DASHBOARD STREAMLIT                                     ║
║  Visualiza picks, efectividad histórica y mejora del modelo en tiempo real  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Instalar:  pip install streamlit supabase pandas plotly                    ║
║  Ejecutar:  streamlit run dashboard_nba.py                                  ║
║  Deploy:    https://share.streamlit.io  (gratis)                            ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from datetime import datetime, timedelta

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────────────────────────────────────

SUPABASE_URL = st.secrets.get("SUPABASE_URL", "https://TU_PROYECTO.supabase.co")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "TU_KEY")

st.set_page_config(
    page_title="NBA Props AI",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS personalizado
st.markdown("""
<style>
    .main { background: #0e1117; }
    .metric-card {
        background: linear-gradient(135deg, #1a1f2e, #252b3b);
        border-radius: 12px; padding: 20px;
        border: 1px solid #2d3448; text-align: center;
    }
    .pick-elite { border-left: 4px solid #ffd700; background: #1a1a0e; }
    .pick-alta  { border-left: 4px solid #ff6b35; background: #1a120e; }
    .pick-media { border-left: 4px solid #4caf50; background: #0e1a0e; }
    .badge-over  { background: #1a4a1a; color: #4caf50; padding: 2px 8px; border-radius: 4px; }
    .badge-under { background: #4a1a1a; color: #f44336; padding: 2px 8px; border-radius: 4px; }
    .badge-pending { background: #2a2a1a; color: #ffc107; padding: 2px 8px; border-radius: 4px; }
    div[data-testid="metric-container"] {
        background: #1a1f2e; border-radius: 10px; padding: 10px;
        border: 1px solid #2d3448;
    }
    .stDataFrame { background: #1a1f2e; }
    h1, h2, h3 { color: #e0e0e0 !important; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
#  CLIENTE SUPABASE (sin dependencia extra)
# ─────────────────────────────────────────────────────────────────────────────

def sb_select(table: str, query: str = "") -> list:
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
    try:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}?{query}", headers=headers, timeout=10)
        return r.json() if r.status_code == 200 else []
    except:
        return []


# ─────────────────────────────────────────────────────────────────────────────
#  CARGA DE DATOS (cacheado 5 min)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def cargar_picks_hoy() -> pd.DataFrame:
    hoy = datetime.now().strftime("%Y-%m-%d")
    datos = sb_select("picks", f"fecha=eq.{hoy}&order=created_at.desc&select=*")
    if not datos:
        return pd.DataFrame()
    df = pd.DataFrame(datos)
    df = df.drop(columns=["features_json"], errors="ignore")
    return df


@st.cache_data(ttl=300)
def cargar_historial(dias: int = 30) -> pd.DataFrame:
    desde = (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%d")
    datos = sb_select("picks", f"fecha=gte.{desde}&estado=neq.PENDIENTE&select=*&order=fecha.desc")
    if not datos:
        return pd.DataFrame()
    df = pd.DataFrame(datos)
    df = df.drop(columns=["features_json"], errors="ignore")
    return df


@st.cache_data(ttl=600)
def cargar_efectividad_diaria() -> pd.DataFrame:
    datos = sb_select("efectividad_diaria", "order=fecha.desc&limit=60")
    return pd.DataFrame(datos) if datos else pd.DataFrame()


@st.cache_data(ttl=600)
def cargar_metricas_modelo() -> pd.DataFrame:
    datos = sb_select("metricas_modelo", "order=fecha.desc&limit=200")
    return pd.DataFrame(datos) if datos else pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🏀 NBA Props AI v2")
    st.markdown(f"*{datetime.now().strftime('%d/%m/%Y %H:%M')}*")
    st.divider()

    pagina = st.radio(
        "Navegación",
        ["📋 Picks de Hoy", "📈 Efectividad Histórica",
         "🧠 Evolución del Modelo", "📊 Auditoría Detallada"],
    )

    st.divider()
    if st.button("🔄 Actualizar datos"):
        st.cache_data.clear()
        st.rerun()

    st.markdown("""
    ---
    **Confianza:**
    - 💎 ÉLITE  — Edge +60% y racha
    - 🔥 ALTA   — Edge sólido
    - ✅ MEDIA  — Edge mínimo
    
    **Fuente:** NBA API + The Odds API  
    **DB:** Supabase PostgreSQL  
    """)


# ─────────────────────────────────────────────────────────────────────────────
#  PÁGINA 1 — PICKS DE HOY
# ─────────────────────────────────────────────────────────────────────────────

if "Picks de Hoy" in pagina:
    st.title("📋 Picks de Hoy")

    df_hoy = cargar_picks_hoy()

    if df_hoy.empty:
        st.warning("⏳ Sin picks para hoy todavía. El sistema ejecuta a las 4:00 PM.")
        st.stop()

    # ── Métricas resumen ────────────────────────────────────────────────────
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Picks", len(df_hoy))
    col2.metric("💎 Élite",  len(df_hoy[df_hoy["confianza"] == "ÉLITE"]))
    col3.metric("🔥 Alta",   len(df_hoy[df_hoy["confianza"] == "ALTA"]))
    col4.metric("📈 OVER",   len(df_hoy[df_hoy["direccion"] == "OVER"]))
    col5.metric("📉 UNDER",  len(df_hoy[df_hoy["direccion"] == "UNDER"]))

    st.divider()

    # ── Filtros ─────────────────────────────────────────────────────────────
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        cat_filter = st.multiselect(
            "Mercado", sorted(df_hoy["categoria"].unique()),
            default=sorted(df_hoy["categoria"].unique())
        )
    with col_f2:
        conf_filter = st.multiselect(
            "Confianza", ["ÉLITE", "ALTA", "MEDIA"], default=["ÉLITE", "ALTA", "MEDIA"]
        )
    with col_f3:
        dir_filter = st.multiselect(
            "Dirección", ["OVER", "UNDER"], default=["OVER", "UNDER"]
        )

    df_fil = df_hoy[
        (df_hoy["categoria"].isin(cat_filter)) &
        (df_hoy["confianza"].isin(conf_filter)) &
        (df_hoy["direccion"].isin(dir_filter))
    ]

    st.markdown(f"**{len(df_fil)} picks después de filtros**")

    # ── Tarjetas de picks ───────────────────────────────────────────────────
    for _, r in df_fil.iterrows():
        conf = r.get("confianza", "MEDIA")
        clase = {"ÉLITE": "pick-elite", "ALTA": "pick-alta"}.get(conf, "pick-media")
        emoji = {"ÉLITE": "💎", "ALTA": "🔥"}.get(conf, "✅")
        dir_badge = "badge-over" if r["direccion"] == "OVER" else "badge-under"
        dir_arrow = "📈" if r["direccion"] == "OVER" else "📉"
        hot = r.get("hot_streak", "")
        banca_tag = " <small>🪑 banca emergente</small>" if r.get("es_banca") else ""
        en_vivo = f" <small>🔴 Q{int(r['cuarto'])} en vivo</small>" if r.get("status_partido") == "in_progress" else ""

        if r["categoria"] in ("DD", "TD"):
            linea_info = f"Probabilidad IA: <b>{r['proy_ia']}%</b>"
            edge_info  = f"Prob vs 50%: <b>{r['edge']:+.2f}</b>"
        else:
            linea_info = f"Vegas: <b>{r['linea_vegas']}</b> → IA: <b>{r['proy_ia']}</b>"
            edge_info  = f"Edge: <b>{r['edge']:+.2f}</b>"

        st.markdown(f"""
        <div class="{clase}" style="padding:14px; border-radius:8px; margin:8px 0;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-size:1.1em; font-weight:bold;">{emoji} {r['jugador']} {hot}{banca_tag}{en_vivo}</span>
                <span class="{dir_badge}">{dir_arrow} {r['direccion']} | {conf}</span>
            </div>
            <div style="color:#aaa; font-size:0.9em; margin-top:4px;">
                🏀 {r['equipo']} vs {r['rival']} &nbsp;|&nbsp; 
                📋 <b>{r['categoria']}</b> &nbsp;|&nbsp; 
                {linea_info} &nbsp;|&nbsp; {edge_info}
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Tabla exportable ─────────────────────────────────────────────────────
    st.divider()
    st.subheader("📥 Tabla Completa")
    cols_show = ["jugador", "equipo", "rival", "categoria", "linea_vegas",
                 "proy_ia", "edge", "direccion", "confianza", "racha", "min_prom"]
    st.dataframe(df_fil[[c for c in cols_show if c in df_fil.columns]], use_container_width=True)

    csv = df_fil.to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇️ Descargar CSV", csv, f"picks_{datetime.now().strftime('%Y-%m-%d')}.csv", "text/csv")


# ─────────────────────────────────────────────────────────────────────────────
#  PÁGINA 2 — EFECTIVIDAD HISTÓRICA
# ─────────────────────────────────────────────────────────────────────────────

elif "Efectividad Histórica" in pagina:
    st.title("📈 Efectividad Histórica")

    df_ef = cargar_efectividad_diaria()
    df_hist = cargar_historial(60)

    if df_ef.empty and df_hist.empty:
        st.warning("Sin historial disponible todavía.")
        st.stop()

    if not df_ef.empty:
        df_ef["fecha"] = pd.to_datetime(df_ef["fecha"])
        df_ef = df_ef.sort_values("fecha")

        # ── KPIs globales ────────────────────────────────────────────────────
        total_g = df_ef["ganados"].sum()
        total_p = df_ef["perdidos"].sum()
        total   = total_g + total_p
        ef_global = (total_g / total * 100) if total > 0 else 0
        racha_dias = len(df_ef)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("🎯 Efectividad Global",  f"{ef_global:.1f}%",
                    delta="✅" if ef_global >= 60 else "⚠️ Bajo 60%")
        col2.metric("✅ Total Ganados",  int(total_g))
        col3.metric("❌ Total Perdidos", int(total_p))
        col4.metric("📅 Días con datos", racha_dias)

        st.divider()

        # ── Gráfico de efectividad diaria ────────────────────────────────────
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Bar(x=df_ef["fecha"], y=df_ef["ganados"], name="Ganados",
                   marker_color="#4caf50", opacity=0.8),
            secondary_y=False,
        )
        fig.add_trace(
            go.Bar(x=df_ef["fecha"], y=df_ef["perdidos"], name="Perdidos",
                   marker_color="#f44336", opacity=0.8),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(x=df_ef["fecha"], y=df_ef["efectividad"], name="% Efectividad",
                       line=dict(color="#ffd700", width=2), mode="lines+markers"),
            secondary_y=True,
        )
        fig.add_hline(y=60, line_dash="dash", line_color="white",
                      annotation_text="Meta 60%", secondary_y=True)
        fig.update_layout(
            title="Efectividad Diaria",
            barmode="stack",
            paper_bgcolor="#1a1f2e", plot_bgcolor="#1a1f2e",
            font_color="#e0e0e0", legend=dict(bgcolor="#252b3b"),
            height=400,
        )
        fig.update_yaxes(secondary_y=True, title_text="% Efectividad", range=[0, 110])
        st.plotly_chart(fig, use_container_width=True)

    # ── Efectividad por mercado ───────────────────────────────────────────────
    if not df_hist.empty:
        st.subheader("📊 Efectividad por Mercado")

        df_hist["acierto"] = pd.to_numeric(df_hist["acierto"], errors="coerce")
        df_hist = df_hist.dropna(subset=["acierto"])

        ef_cat = (
            df_hist.groupby("categoria")["acierto"]
            .agg(["mean", "count"])
            .reset_index()
        )
        ef_cat.columns = ["Mercado", "Efectividad", "Total"]
        ef_cat["Efectividad"] = (ef_cat["Efectividad"] * 100).round(1)
        ef_cat = ef_cat.sort_values("Efectividad", ascending=False)

        fig2 = px.bar(
            ef_cat, x="Mercado", y="Efectividad",
            text="Efectividad", color="Efectividad",
            color_continuous_scale=["#f44336", "#ff9800", "#4caf50"],
            range_color=[40, 80], title="% Efectividad por Tipo de Pick",
        )
        fig2.add_hline(y=60, line_dash="dash", line_color="white",
                       annotation_text="Meta 60%")
        fig2.update_traces(texttemplate="%{text}%", textposition="outside")
        fig2.update_layout(
            paper_bgcolor="#1a1f2e", plot_bgcolor="#1a1f2e",
            font_color="#e0e0e0", height=350, coloraxis_showscale=False,
        )
        st.plotly_chart(fig2, use_container_width=True)

        # ── Efectividad por jugador (top 15) ─────────────────────────────────
        st.subheader("🏆 Mejores Jugadores (min. 10 picks)")
        ef_jug = (
            df_hist.groupby("jugador")["acierto"]
            .agg(["mean", "count"])
            .reset_index()
        )
        ef_jug.columns = ["Jugador", "Efectividad", "Picks"]
        ef_jug = ef_jug[ef_jug["Picks"] >= 10].sort_values("Efectividad", ascending=False).head(15)
        ef_jug["Efectividad"] = (ef_jug["Efectividad"] * 100).round(1)

        if not ef_jug.empty:
            fig3 = px.bar(
                ef_jug, x="Efectividad", y="Jugador", orientation="h",
                text="Efectividad", color="Efectividad",
                color_continuous_scale=["#f44336", "#ff9800", "#4caf50"],
                range_color=[40, 90],
            )
            fig3.update_traces(texttemplate="%{text}%", textposition="outside")
            fig3.update_layout(
                paper_bgcolor="#1a1f2e", plot_bgcolor="#1a1f2e",
                font_color="#e0e0e0", height=450, coloraxis_showscale=False,
                yaxis={"categoryorder": "total ascending"},
            )
            st.plotly_chart(fig3, use_container_width=True)

        # ── Efectividad OVER vs UNDER ─────────────────────────────────────────
        col_a, col_b = st.columns(2)
        with col_a:
            ef_dir = df_hist.groupby("direccion")["acierto"].agg(["mean","count"]).reset_index()
            ef_dir.columns = ["Dirección", "Efectividad", "Picks"]
            ef_dir["Efectividad"] = (ef_dir["Efectividad"]*100).round(1)
            fig4 = px.pie(ef_dir, values="Picks", names="Dirección",
                          title="Distribución OVER / UNDER",
                          color_discrete_map={"OVER":"#4caf50","UNDER":"#f44336"})
            fig4.update_layout(paper_bgcolor="#1a1f2e", font_color="#e0e0e0")
            st.plotly_chart(fig4, use_container_width=True)

        with col_b:
            ef_conf = df_hist.groupby("confianza")["acierto"].agg(["mean","count"]).reset_index()
            ef_conf.columns = ["Confianza", "Efectividad", "Picks"]
            ef_conf["Efectividad"] = (ef_conf["Efectividad"]*100).round(1)
            fig5 = px.bar(ef_conf, x="Confianza", y="Efectividad",
                          text="Efectividad", title="Efectividad por Nivel de Confianza",
                          color="Confianza",
                          color_discrete_map={"ÉLITE":"#ffd700","ALTA":"#ff6b35","MEDIA":"#4caf50"})
            fig5.update_traces(texttemplate="%{text}%", textposition="outside")
            fig5.add_hline(y=60, line_dash="dash", line_color="white")
            fig5.update_layout(paper_bgcolor="#1a1f2e", plot_bgcolor="#1a1f2e",
                               font_color="#e0e0e0", showlegend=False)
            st.plotly_chart(fig5, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
#  PÁGINA 3 — EVOLUCIÓN DEL MODELO
# ─────────────────────────────────────────────────────────────────────────────

elif "Evolución del Modelo" in pagina:
    st.title("🧠 Evolución del Modelo (Aprendizaje Continuo)")

    df_met = cargar_metricas_modelo()

    if df_met.empty:
        st.info("El modelo no ha registrado métricas todavía. Se generan al re-entrenarse.")
        st.stop()

    df_met["fecha"] = pd.to_datetime(df_met["fecha"])
    df_met = df_met.sort_values("fecha")

    # ── MAE por categoría a lo largo del tiempo ──────────────────────────────
    st.subheader("📉 Error del Modelo (MAE) — Mejora Continua")
    df_reg = df_met[df_met["mae"].notna()]

    if not df_reg.empty:
        fig = px.line(
            df_reg, x="fecha", y="mae", color="categoria",
            title="Error Absoluto Medio (MAE) por Categoría — Menor = Mejor",
            markers=True,
        )
        fig.update_layout(
            paper_bgcolor="#1a1f2e", plot_bgcolor="#1a1f2e",
            font_color="#e0e0e0", height=400,
            legend=dict(bgcolor="#252b3b"),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Tabla de últimas métricas
        ultimas = df_reg.groupby("categoria").last().reset_index()[["categoria", "fecha", "mae"]]
        ultimas["mae"] = ultimas["mae"].round(3)
        ultimas["Tendencia"] = ultimas["mae"].apply(
            lambda x: "🟢 Bueno" if x < 3.5 else ("🟡 Mejorable" if x < 5.0 else "🔴 Alto")
        )
        ultimas.columns = ["Categoría", "Último Entrenamiento", "MAE Actual", "Estado"]
        st.dataframe(ultimas, use_container_width=True)

    # ── Accuracy clasificadores ───────────────────────────────────────────────
    df_cls = df_met[df_met["acc"].notna()]
    if not df_cls.empty:
        st.subheader("🎯 Precisión Clasificadores (DD / TD)")
        fig2 = px.line(
            df_cls, x="fecha", y="acc", color="categoria",
            title="Accuracy Doble-Doble y Triple-Doble",
            markers=True,
        )
        fig2.add_hline(y=0.60, line_dash="dash", line_color="yellow", annotation_text="Meta 60%")
        fig2.update_layout(
            paper_bgcolor="#1a1f2e", plot_bgcolor="#1a1f2e",
            font_color="#e0e0e0", height=350,
        )
        st.plotly_chart(fig2, use_container_width=True)

    # ── Historial de re-entrenamientos ──────────────────────────────────────
    st.subheader("📅 Historial de Entrenamientos")
    resumen = (
        df_met.groupby("fecha")
        .agg(categorias=("categoria", "count"), mae_prom=("mae", "mean"))
        .reset_index()
    )
    resumen["fecha"] = resumen["fecha"].dt.strftime("%Y-%m-%d")
    resumen.columns = ["Fecha", "Modelos Entrenados", "MAE Promedio"]
    st.dataframe(resumen, use_container_width=True)

    # ── Explicación del aprendizaje ──────────────────────────────────────────
    st.divider()
    st.info("""
    **¿Cómo funciona el aprendizaje continuo?**
    
    1. Cada vez que el modelo se ejecuta, guarda sus predicciones en Supabase
    2. Al día siguiente, se auditan automáticamente comparando con los resultados reales
    3. Los picks donde el modelo se equivocó se marcan como `PERDIDO`
    4. Al re-entrenarse, esos registros reciben **peso 3×** en el entrenamiento
    5. Con el tiempo, el modelo aprende de sus errores y mejora su MAE
    
    **Mínimo de errores para re-entrenamiento automático:** 20 picks incorrectos acumulados.
    """)


# ─────────────────────────────────────────────────────────────────────────────
#  PÁGINA 4 — AUDITORÍA DETALLADA
# ─────────────────────────────────────────────────────────────────────────────

elif "Auditoría Detallada" in pagina:
    st.title("📊 Auditoría Detallada de Picks")

    col_f, col_d = st.columns([2, 1])
    with col_f:
        dias_audit = st.slider("Días a revisar", 1, 60, 14)
    with col_d:
        cat_audit = st.multiselect(
            "Mercado", ["PTS", "REB", "AST", "FGM", "3PM", "DD", "TD"],
            default=["PTS", "REB", "AST"]
        )

    df_audit = cargar_historial(dias_audit)
    if df_audit.empty:
        st.warning("Sin historial para el período seleccionado.")
        st.stop()

    df_audit = df_audit[df_audit["categoria"].isin(cat_audit)] if cat_audit else df_audit
    df_audit["acierto_num"] = pd.to_numeric(df_audit["acierto"], errors="coerce")

    # ── Tabla con coloreo ────────────────────────────────────────────────────
    def colorear_fila(row):
        if row["acierto_num"] == 1:
            return ["background-color: #0d2b0d"] * len(row)
        elif row["acierto_num"] == 0:
            return ["background-color: #2b0d0d"] * len(row)
        else:
            return ["background-color: #2b2b0d"] * len(row)

    cols_audit = ["fecha", "jugador", "equipo", "rival", "categoria",
                  "linea_vegas", "proy_ia", "edge", "direccion",
                  "confianza", "resultado_real", "estado"]
    df_show = df_audit[[c for c in cols_audit if c in df_audit.columns]]

    st.dataframe(
        df_show.style.apply(colorear_fila, axis=1),
        use_container_width=True,
        height=500,
    )

    # ── Distribución de errores ──────────────────────────────────────────────
    if "resultado_real" in df_audit.columns and "linea_vegas" in df_audit.columns:
        st.subheader("📐 Distribución del Error de Predicción")
        df_err = df_audit.dropna(subset=["resultado_real", "linea_vegas"])
        df_err["error"] = df_err["resultado_real"].astype(float) - df_err["proy_ia"].astype(float)

        fig = px.histogram(
            df_err, x="error", color="categoria",
            nbins=30, title="Distribución del Error (Real - IA)",
            opacity=0.75,
        )
        fig.add_vline(x=0, line_dash="dash", line_color="white", annotation_text="Error 0")
        fig.update_layout(
            paper_bgcolor="#1a1f2e", plot_bgcolor="#1a1f2e",
            font_color="#e0e0e0", height=350,
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Descargar auditoría completa ─────────────────────────────────────────
    st.divider()
    csv = df_audit.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "⬇️ Descargar Auditoría Completa",
        csv,
        f"auditoria_{datetime.now().strftime('%Y-%m-%d')}.csv",
        "text/csv",
    )
