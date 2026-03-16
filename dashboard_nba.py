# -*- coding: utf-8 -*-
"""
NBA PROPS AI — DASHBOARD STREAMLIT V4
======================================
FIXES aplicados vs versiones anteriores:
  ✦ Picks de Hoy: agrupados por partido/hora, ocultando picks ya vencidos
  ✦ Efectividad Histórica: limit=5000 en Supabase (ya no muestra solo 1 día)
  ✦ Auditoría Detallada: corregido KeyError acierto_num con column_config
  ✦ Sidebar muestra hora CST real (no UTC)
"""
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────────────────────────────────────

SUPABASE_URL = st.secrets.get("SUPABASE_URL", "https://TU_PROYECTO.supabase.co")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "TU_KEY")
TZ           = ZoneInfo("America/Mexico_City")

st.set_page_config(
    page_title="NBA Props AI",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .pick-elite { border-left: 4px solid #ffd700; background: #1a1a0e; padding:14px;
                  border-radius:8px; margin:4px 0 12px 0; }
    .pick-alta  { border-left: 4px solid #ff6b35; background: #1a120e; padding:14px;
                  border-radius:8px; margin:4px 0 12px 0; }
    .pick-media { border-left: 4px solid #4caf50; background: #0e1a0e; padding:14px;
                  border-radius:8px; margin:4px 0 12px 0; }
    .badge-over  { background:#1a4a1a; color:#4caf50; padding:3px 10px;
                   border-radius:4px; font-weight:bold; }
    .badge-under { background:#4a1a1a; color:#f44336; padding:3px 10px;
                   border-radius:4px; font-weight:bold; }
    .juego-header { background:#1a1f2e; border:1px solid #2d3448; border-radius:10px;
                    padding:12px 18px; margin:18px 0 8px 0; }
    div[data-testid="metric-container"] {
        background:#1a1f2e; border-radius:10px; padding:10px;
        border:1px solid #2d3448;
    }
    h1, h2, h3, h4 { color:#e0e0e0 !important; }
    .orden-num { background:#253050; color:#7ab3f5; border-radius:50%;
                 width:24px; height:24px; display:inline-flex;
                 align-items:center; justify-content:center;
                 font-size:11px; font-weight:bold; margin-right:8px; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
#  CLIENTE SUPABASE
# ─────────────────────────────────────────────────────────────────────────────

def sb_select(table: str, query: str = "") -> list:
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    try:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}?{query}",
                         headers=headers, timeout=12)
        return r.json() if r.status_code == 200 else []
    except:
        return []


# ─────────────────────────────────────────────────────────────────────────────
#  CARGA DE DATOS
# ─────────────────────────────────────────────────────────────────────────────

def cargar_picks_hoy() -> pd.DataFrame:
    """Sin caché para que siempre esté actualizado."""
    hoy = datetime.now(TZ).strftime("%Y-%m-%d")
    datos = sb_select("picks", f"fecha=eq.{hoy}&order=hora.asc&select=*&limit=2000")
    if not datos:
        return pd.DataFrame()
    df = pd.DataFrame(datos)
    return df.drop(columns=["features_json"], errors="ignore")


@st.cache_data(ttl=300)
def cargar_historial(dias: int = 30) -> pd.DataFrame:
    """
    FIX V4: limit=5000 para no quedarse solo con los primeros 1000 rows
    (bug que hacía parecer que solo había datos de 1 día).
    """
    desde = (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%d")
    datos = sb_select(
        "picks",
        f"fecha=gte.{desde}&estado=in.(GANADO,PERDIDO,ANULADO)"
        f"&select=*&order=fecha.desc&limit=5000"
    )
    if not datos:
        return pd.DataFrame()
    df = pd.DataFrame(datos)
    return df.drop(columns=["features_json"], errors="ignore")


@st.cache_data(ttl=600)
def cargar_metricas_modelo() -> pd.DataFrame:
    datos = sb_select("metricas_modelo", "order=fecha.desc&limit=500")
    return pd.DataFrame(datos) if datos else pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────

ahora = datetime.now(TZ)

with st.sidebar:
    st.markdown("## 🏀 NBA Props AI V4")
    st.markdown(f"*{ahora.strftime('%d/%m/%Y %H:%M CST')}*")
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
    - 💎 ÉLITE  — Edge +100% y racha consistente
    - 🔥 ALTA   — Edge sólido validado
    - ✅ MEDIA  — Solo referencia interna

    **Fuente:** NBA API + The Odds API
    **DB:** Supabase PostgreSQL
    """)


# ─────────────────────────────────────────────────────────────────────────────
#  PÁGINA 1 — PICKS DE HOY (CORREGIDA)
# ─────────────────────────────────────────────────────────────────────────────

if "Picks de Hoy" in pagina:
    st.title("📋 Picks de Hoy")

    df_hoy = cargar_picks_hoy()

    if df_hoy.empty:
        st.warning("⏳ Sin picks para hoy todavía.")
        st.stop()

    # ── FIX: Filtrar picks cuya hora ya pasó ─────────────────────────────────
    # Comparamos hora del pick (string HH:MM) con la hora actual CST
    hora_actual_str = ahora.strftime("%H:%M")

    # Separar activos vs vencidos
    df_activos  = df_hoy[df_hoy["hora"] >= hora_actual_str].copy()
    df_vencidos = df_hoy[df_hoy["hora"] <  hora_actual_str].copy()

    # ── Métricas resumen (del total del día) ─────────────────────────────────
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Activos ahora",   len(df_activos))
    col2.metric("💎 Élite activos", len(df_activos[df_activos["confianza"] == "ÉLITE"]))
    col3.metric("🔥 Alta activos",  len(df_activos[df_activos["confianza"] == "ALTA"]))
    col4.metric("Generados hoy",   len(df_hoy))
    col5.metric("🕐 Ya iniciados",  len(df_vencidos))

    if df_activos.empty:
        st.info("🏀 Todos los partidos de hoy ya comenzaron. Revisa la sección Auditoría para resultados.")
        # Mostrar igual los de hoy como referencia
        df_activos = df_hoy.copy()
        st.warning("Mostrando todos los picks del día (algunos ya iniciados).")

    st.divider()

    # ── Filtros ───────────────────────────────────────────────────────────────
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        cat_filter = st.multiselect(
            "Mercado", sorted(df_activos["categoria"].unique()),
            default=sorted(df_activos["categoria"].unique())
        )
    with col_f2:
        conf_filter = st.multiselect(
            "Confianza", ["ÉLITE", "ALTA", "MEDIA"], default=["ÉLITE", "ALTA"]
        )
    with col_f3:
        dir_filter = st.multiselect(
            "Dirección", ["OVER", "UNDER"], default=["OVER", "UNDER"]
        )

    df_fil = df_activos[
        df_activos["categoria"].isin(cat_filter) &
        df_activos["confianza"].isin(conf_filter) &
        df_activos["direccion"].isin(dir_filter)
    ].copy()

    # ── Ordenar: primero ÉLITE, luego ALTA, luego MEDIA; dentro de cada grupo por hora ──
    orden_conf = {"ÉLITE": 0, "ALTA": 1, "MEDIA": 2}
    df_fil["_ord_conf"] = df_fil["confianza"].map(orden_conf).fillna(3)
    df_fil = df_fil.sort_values(["hora", "_ord_conf"]).reset_index(drop=True)

    st.markdown(f"**Mostrando {len(df_fil)} picks activos**")

    # ── FIX: Agrupación por HORA y PARTIDO (equipo vs rival) ─────────────────
    # Creamos clave de partido para agrupar
    df_fil["_partido_key"] = df_fil["hora"] + " | " + df_fil["equipo"] + " vs " + df_fil["rival"]

    partidos_ordenados = df_fil.groupby(
        ["hora", "_partido_key"], sort=True
    ).size().reset_index()[["hora", "_partido_key"]].values.tolist()

    # Eliminar duplicados manteniendo orden
    vistos = set()
    partidos_unicos = []
    for hora_j, partido_k in partidos_ordenados:
        # Normalizar: "TeamA vs TeamB" y "TeamB vs TeamA" son el mismo partido
        equipos = set(partido_k.replace(hora_j + " | ", "").split(" vs "))
        clave_norm = hora_j + "|" + "|".join(sorted(equipos))
        if clave_norm not in vistos:
            vistos.add(clave_norm)
            partidos_unicos.append((hora_j, partido_k))

    num_partido = 0
    for hora_j, partido_k in partidos_unicos:
        grupo = df_fil[df_fil["_partido_key"] == partido_k]
        if grupo.empty: continue

        num_partido += 1
        equipo_local  = grupo.iloc[0]["equipo"]
        rival_local   = grupo.iloc[0]["rival"]
        n_elite_g     = len(grupo[grupo["confianza"] == "ÉLITE"])
        n_alta_g      = len(grupo[grupo["confianza"] == "ALTA"])

        # Encabezado del partido
        st.markdown(f"""
        <div class="juego-header">
            <span style="font-size:1.15em; font-weight:bold; color:#e0e0e0;">
                🏀 Juego {num_partido} &nbsp;·&nbsp; ⏰ {hora_j} CST
            </span><br/>
            <span style="color:#aaa; font-size:0.95em;">
                {equipo_local} vs {rival_local} &nbsp;&nbsp;
                {'💎 ' + str(n_elite_g) + ' ÉLITE &nbsp;' if n_elite_g > 0 else ''}
                {'🔥 ' + str(n_alta_g) + ' ALTA' if n_alta_g > 0 else ''}
            </span>
        </div>
        """, unsafe_allow_html=True)

        # Picks del partido ordenados por confianza
        for pos, (_, r) in enumerate(grupo.iterrows(), 1):
            conf      = r.get("confianza", "MEDIA")
            clase     = {"ÉLITE": "pick-elite", "ALTA": "pick-alta"}.get(conf, "pick-media")
            emoji     = {"ÉLITE": "💎", "ALTA": "🔥"}.get(conf, "✅")
            dir_badge = "badge-over" if r["direccion"] == "OVER" else "badge-under"
            dir_arrow = "📈" if r["direccion"] == "OVER" else "📉"
            hot       = r.get("hot_streak", "")
            banca_tag = " <small style='color:#aaa'>🪑 banca</small>" if r.get("es_banca") else ""
            en_vivo   = f" <small style='color:#f44336'>🔴 Q{int(r['cuarto'])}</small>" \
                        if r.get("status_partido") == "in_progress" else ""

            if r["categoria"] in ("DD", "TD"):
                linea_info = f"Prob IA: <b>{r['proy_ia']}%</b>"
                edge_info  = f"Edge: <b>{r['edge']:+.2f}</b>"
            else:
                lv = r.get("linea_vegas", "?")
                pi = r.get("proy_ia", "?")
                linea_info = f"Vegas: <b>{lv}</b> → IA: <b>{pi}</b>"
                edge_info  = f"Edge: <b>{r['edge']:+.2f}</b>"

            st.markdown(f"""
            <div class="{clase}">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-size:1.05em; font-weight:bold; color:#e0e0e0;">
                        <span class="orden-num">{pos}</span>{emoji} {r['jugador']} {hot}{banca_tag}{en_vivo}
                    </span>
                    <span class="{dir_badge}">{dir_arrow} {r['direccion']} | {conf}</span>
                </div>
                <div style="color:#bbb; font-size:0.88em; margin-top:6px;">
                    📋 <b>{r['categoria']}</b> &nbsp;|&nbsp;
                    {linea_info} &nbsp;|&nbsp; {edge_info} &nbsp;|&nbsp;
                    ⏱ min: {r.get('min_prom','?')}
                </div>
            </div>
            """, unsafe_allow_html=True)

    # ── Tabla exportable ──────────────────────────────────────────────────────
    st.divider()
    st.subheader("📥 Tabla Completa (activos)")
    cols_show = ["hora", "jugador", "equipo", "rival", "categoria",
                 "linea_vegas", "proy_ia", "edge", "direccion",
                 "confianza", "racha", "min_prom"]
    st.dataframe(
        df_fil[[c for c in cols_show if c in df_fil.columns]],
        use_container_width=True
    )
    csv = df_fil.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "⬇️ Descargar CSV",
        csv,
        f"picks_{ahora.strftime('%Y-%m-%d')}.csv",
        "text/csv"
    )


# ─────────────────────────────────────────────────────────────────────────────
#  PÁGINA 2 — EFECTIVIDAD HISTÓRICA (CORREGIDA)
# ─────────────────────────────────────────────────────────────────────────────

elif "Efectividad Histórica" in pagina:
    st.title("📈 Efectividad Histórica")

    df_hist = cargar_historial(60)

    if df_hist.empty:
        st.warning("Sin historial disponible.")
        st.stop()

    # FIX V4: Computamos efectividad directamente del historial (no de la tabla
    # efectividad_diaria que puede estar desactualizada o incompleta).
    # Excluimos ANULADOS del conteo (no son ni ganados ni perdidos).
    df_hist["acierto_num"] = pd.to_numeric(df_hist["acierto"], errors="coerce")
    df_hist_cal = df_hist[df_hist["estado"].isin(["GANADO", "PERDIDO"])].copy()
    df_hist_cal["fecha_dt"] = pd.to_datetime(df_hist_cal["fecha"])

    df_ef = df_hist_cal.groupby(df_hist_cal["fecha_dt"].dt.date).apply(
        lambda x: pd.Series({
            "ganados":  (x["acierto_num"] == 1).sum(),
            "perdidos": (x["acierto_num"] == 0).sum(),
            "total":    len(x),
        })
    ).reset_index()
    df_ef.columns = ["fecha", "ganados", "perdidos", "total"]
    df_ef["efectividad"] = (df_ef["ganados"] / df_ef["total"] * 100).round(1)
    df_ef = df_ef.sort_values("fecha")

    # ── KPIs ─────────────────────────────────────────────────────────────────
    total_g   = int(df_ef["ganados"].sum())
    total_p   = int(df_ef["perdidos"].sum())
    total     = total_g + total_p
    ef_global = (total_g / total * 100) if total > 0 else 0

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("🎯 Efectividad Global",  f"{ef_global:.1f}%",
                delta="✅" if ef_global >= 60 else "⚠️ Bajo 60%")
    col2.metric("✅ Total Ganados",  total_g)
    col3.metric("❌ Total Perdidos", total_p)
    col4.metric("📅 Días con datos", len(df_ef))
    anulados = len(df_hist[df_hist["estado"] == "ANULADO"])
    col5.metric("🚫 Anulados (DNP)", anulados)

    st.divider()

    # ── Gráfico diario ────────────────────────────────────────────────────────
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=df_ef["fecha"], y=df_ef["ganados"],   name="Ganados",
                         marker_color="#4caf50", opacity=0.8), secondary_y=False)
    fig.add_trace(go.Bar(x=df_ef["fecha"], y=df_ef["perdidos"],  name="Perdidos",
                         marker_color="#f44336", opacity=0.8), secondary_y=False)
    fig.add_trace(go.Scatter(x=df_ef["fecha"], y=df_ef["efectividad"],
                             name="% Efectividad",
                             line=dict(color="#ffd700", width=2),
                             mode="lines+markers"), secondary_y=True)
    fig.add_hline(y=60, line_dash="dash", line_color="white",
                  annotation_text="Meta 60%", secondary_y=True)
    fig.update_layout(title="Efectividad Diaria del Modelo", barmode="stack",
                      paper_bgcolor="#1a1f2e", plot_bgcolor="#1a1f2e",
                      font_color="#e0e0e0", legend=dict(bgcolor="#252b3b"), height=400)
    fig.update_yaxes(secondary_y=True, title_text="% Efectividad", range=[0, 110])
    st.plotly_chart(fig, use_container_width=True)

    # ── Efectividad por categoría ─────────────────────────────────────────────
    st.subheader("📊 Efectividad por Mercado")
    ef_cat = df_hist_cal.groupby("categoria")["acierto_num"].agg(["mean","count"]).reset_index()
    ef_cat.columns = ["Mercado", "Efectividad", "Total"]
    ef_cat["Efectividad"] = (ef_cat["Efectividad"] * 100).round(1)
    ef_cat = ef_cat.sort_values("Efectividad", ascending=False)

    fig2 = px.bar(ef_cat, x="Mercado", y="Efectividad", text="Efectividad",
                  color="Efectividad",
                  color_continuous_scale=["#f44336","#ff9800","#4caf50"],
                  range_color=[40,80], title="% Efectividad por Tipo de Pick")
    fig2.add_hline(y=60, line_dash="dash", line_color="white", annotation_text="Meta 60%")
    fig2.update_traces(texttemplate="%{text}%", textposition="outside")
    fig2.update_layout(paper_bgcolor="#1a1f2e", plot_bgcolor="#1a1f2e",
                       font_color="#e0e0e0", height=350, coloraxis_showscale=False)
    st.plotly_chart(fig2, use_container_width=True)

    # ── Efectividad por confianza y dirección ─────────────────────────────────
    col_a, col_b = st.columns(2)
    with col_a:
        ef_conf = df_hist_cal.groupby("confianza")["acierto_num"].agg(["mean","count"]).reset_index()
        ef_conf.columns = ["Confianza","Efectividad","Picks"]
        ef_conf["Efectividad"] = (ef_conf["Efectividad"]*100).round(1)
        fig_c = px.bar(ef_conf, x="Confianza", y="Efectividad", text="Efectividad",
                       title="Efectividad por Nivel",
                       color="Confianza",
                       color_discrete_map={"ÉLITE":"#ffd700","ALTA":"#ff6b35","MEDIA":"#4caf50"})
        fig_c.update_traces(texttemplate="%{text}%", textposition="outside")
        fig_c.add_hline(y=60, line_dash="dash", line_color="white")
        fig_c.update_layout(paper_bgcolor="#1a1f2e", plot_bgcolor="#1a1f2e",
                            font_color="#e0e0e0", showlegend=False)
        st.plotly_chart(fig_c, use_container_width=True)

    with col_b:
        ef_dir = df_hist_cal.groupby("direccion")["acierto_num"].agg(["mean","count"]).reset_index()
        ef_dir.columns = ["Dirección","Efectividad","Picks"]
        ef_dir["Efectividad"] = (ef_dir["Efectividad"]*100).round(1)
        fig_d = px.pie(ef_dir, values="Picks", names="Dirección",
                       title="Distribución OVER / UNDER",
                       color_discrete_map={"OVER":"#4caf50","UNDER":"#f44336"})
        fig_d.update_layout(paper_bgcolor="#1a1f2e", font_color="#e0e0e0")
        st.plotly_chart(fig_d, use_container_width=True)

    # ── Top jugadores ─────────────────────────────────────────────────────────
    st.subheader("🏆 Mejores Jugadores (mín. 5 picks calificados)")
    ef_jug = df_hist_cal.groupby("jugador")["acierto_num"].agg(["mean","count"]).reset_index()
    ef_jug.columns = ["Jugador","Efectividad","Picks"]
    ef_jug = ef_jug[ef_jug["Picks"] >= 5].sort_values("Efectividad", ascending=False).head(15)
    ef_jug["Efectividad"] = (ef_jug["Efectividad"]*100).round(1)
    if not ef_jug.empty:
        fig_j = px.bar(ef_jug, x="Efectividad", y="Jugador", orientation="h",
                       text="Efectividad", color="Efectividad",
                       color_continuous_scale=["#f44336","#ff9800","#4caf50"],
                       range_color=[40,90])
        fig_j.update_traces(texttemplate="%{text}%", textposition="outside")
        fig_j.update_layout(paper_bgcolor="#1a1f2e", plot_bgcolor="#1a1f2e",
                            font_color="#e0e0e0", height=450, coloraxis_showscale=False,
                            yaxis={"categoryorder":"total ascending"})
        st.plotly_chart(fig_j, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
#  PÁGINA 3 — EVOLUCIÓN DEL MODELO
# ─────────────────────────────────────────────────────────────────────────────

elif "Evolución del Modelo" in pagina:
    st.title("🧠 Evolución del Modelo — Aprendizaje Continuo")

    df_met = cargar_metricas_modelo()

    if df_met.empty:
        st.info("El modelo no ha registrado métricas aún. Se generan al reentrenarse.")
        st.stop()

    df_met["fecha"] = pd.to_datetime(df_met["fecha"])
    df_met = df_met.sort_values("fecha")

    st.subheader("📉 Error Absoluto Medio (MAE) — Menor = Mejor")
    df_reg = df_met[df_met["mae"].notna()]
    if not df_reg.empty:
        fig = px.line(df_reg, x="fecha", y="mae", color="categoria",
                      title="MAE por Categoría a lo largo del tiempo", markers=True)
        fig.update_layout(paper_bgcolor="#1a1f2e", plot_bgcolor="#1a1f2e",
                          font_color="#e0e0e0", height=400, legend=dict(bgcolor="#252b3b"))
        st.plotly_chart(fig, use_container_width=True)

        ultimas = df_reg.groupby("categoria").last().reset_index()[["categoria","fecha","mae"]]
        ultimas["mae"] = ultimas["mae"].round(3)
        ultimas["Estado"] = ultimas["mae"].apply(
            lambda x: "🟢 Bueno" if x < 3.5 else ("🟡 Mejorable" if x < 5.0 else "🔴 Alto")
        )
        ultimas.columns = ["Categoría","Último Entrenamiento","MAE Actual","Estado"]
        st.dataframe(ultimas, use_container_width=True)

    df_cls = df_met[df_met["acc"].notna()]
    if not df_cls.empty:
        st.subheader("🎯 Precisión Clasificadores (DD)")
        fig2 = px.line(df_cls, x="fecha", y="acc", color="categoria",
                       title="Accuracy Doble-Doble", markers=True)
        fig2.add_hline(y=0.60, line_dash="dash", line_color="yellow", annotation_text="Meta 60%")
        fig2.update_layout(paper_bgcolor="#1a1f2e", plot_bgcolor="#1a1f2e",
                           font_color="#e0e0e0", height=350)
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    st.info("""
    **¿Cómo funciona el aprendizaje continuo?**

    1. Cada pick generado guarda sus features (variables de entrada) en Supabase
    2. Al día siguiente de madrugada la auditoría compara la predicción con el resultado real
    3. Los picks PERDIDOS se usan para reentrenar con peso x4 (aprende de sus errores)
    4. El modelo rechaza el reentrenamiento si empeora el MAE (rollback automático)
    5. Los picks ANULADOS (jugador no jugó – DNP) no afectan el entrenamiento

    **Ciclo óptimo:** genera picks a las 14:00–15:00 CST → audita a las 00:30 CST
    """)


# ─────────────────────────────────────────────────────────────────────────────
#  PÁGINA 4 — AUDITORÍA DETALLADA (CORREGIDA)
# ─────────────────────────────────────────────────────────────────────────────

elif "Auditoría Detallada" in pagina:
    st.title("📊 Auditoría Detallada de Picks")

    col_f, col_d = st.columns([2, 1])
    with col_f:
        dias_audit = st.slider("Días a revisar", 1, 60, 14)
    with col_d:
        cat_audit = st.multiselect(
            "Mercado", ["PTS","REB","AST","FGM","3PM","DD","TD"],
            default=["PTS","REB","AST"]
        )

    df_audit = cargar_historial(dias_audit)
    if df_audit.empty:
        st.warning("Sin historial para el período seleccionado.")
        st.stop()

    if cat_audit:
        df_audit = df_audit[df_audit["categoria"].isin(cat_audit)]

    # FIX V4: acierto_num se crea AQUÍ y se añade a df_show
    # La función colorear_fila puede accederlo porque df_show SÍ lo incluye.
    # Se oculta visualmente con column_config.
    df_audit = df_audit.copy()
    df_audit["acierto_num"] = pd.to_numeric(df_audit["acierto"], errors="coerce")

    cols_audit = [
        "fecha","hora","jugador","equipo","rival","categoria",
        "linea_vegas","proy_ia","edge","direccion",
        "confianza","resultado_real","estado",
        "acierto_num",   # ← incluida para el coloreo, ocultada con column_config
    ]
    df_show = df_audit[[c for c in cols_audit if c in df_audit.columns]].copy()

    def colorear_fila(row):
        # FIX: accedemos por nombre de columna (que SÍ existe en df_show)
        val = row.get("acierto_num", None)
        try:
            val = float(val)
        except (TypeError, ValueError):
            val = -1
        if val == 1:   return ["background-color: #0d2b0d"] * len(row)
        elif val == 0: return ["background-color: #2b0d0d"] * len(row)
        else:          return ["background-color: #2b2b0d"] * len(row)

    st.dataframe(
        df_show.style.apply(colorear_fila, axis=1),
        use_container_width=True,
        height=520,
        column_config={"acierto_num": None},   # ← ocultar visualmente
    )

    # ── Distribución del error de predicción ─────────────────────────────────
    df_err = df_audit.dropna(subset=["resultado_real","proy_ia","linea_vegas"]).copy()
    if not df_err.empty:
        st.subheader("📐 Distribución del Error (Real − Predicción IA)")
        df_err["error"] = df_err["resultado_real"].astype(float) - df_err["proy_ia"].astype(float)
        fig = px.histogram(df_err, x="error", color="categoria", nbins=30,
                           title="Error del modelo por categoría", opacity=0.75)
        fig.add_vline(x=0, line_dash="dash", line_color="white", annotation_text="Error 0")
        fig.update_layout(paper_bgcolor="#1a1f2e", plot_bgcolor="#1a1f2e",
                          font_color="#e0e0e0", height=350)
        st.plotly_chart(fig, use_container_width=True)

    # ── Descargar ─────────────────────────────────────────────────────────────
    st.divider()
    csv = df_audit.drop(columns=["acierto_num"], errors="ignore").to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "⬇️ Descargar Auditoría Completa",
        csv,
        f"auditoria_{datetime.now().strftime('%Y-%m-%d')}.csv",
        "text/csv",
    )
