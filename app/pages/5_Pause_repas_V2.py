"""V2 — Pause repas et fatigue : l'humain comme levier de performance.

Compare, sur une crise, « sans pause / pause fixe / pause intelligente » sous une hypothèse de fatigue réglable,
et affiche la courbe de sensibilité calculée par `python -m crise.pause_analyse` si elle existe.
"""
from __future__ import annotations

import logging

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from crise.benchmark import resoudre_strategie
from crise.config import charger_config, chemin_projet
from crise.kpi import calculer_kpi
from crise.models import lister_crises
from crise.pause_analyse import MODES, params_mode
from crise.simulateur import simuler_crise

logging.getLogger("crise.simulateur").setLevel(logging.ERROR)
st.set_page_config(page_title="V2 — Pause repas", layout="wide")
st.title("V2 — Pause repas et fatigue des équipes")
st.caption("Hypothèse : au-delà de 4h de travail sans pause, chaque heure allonge les dépannages. "
           "La pause (45 min, sur place, jamais pendant un chantier) remet le compteur à zéro. "
           "Le Code du travail impose déjà une pause après 6h de travail effectif : la V1 ne la modélisait pas.")

NOMS = {"sans_pause": "Sans pause (V1)", "pause_fixe": "Pause fixe à 4h", "pause_intelligente": "Pause intelligente"}
with st.sidebar:
    crises = lister_crises()
    crise = st.selectbox("Crise", crises, index=crises.index("CRISE_024") if "CRISE_024" in crises else 0)
    strategie = st.selectbox("Stratégie", ["WSPT", "R2", "R1"])
    pente = st.slider("Perte de rendement par heure au-delà de 4h (%)", 0, 15, 5) / 100
    duree_pause = st.slider("Durée de la pause (min)", 20, 60, 45, 5)


@st.cache_data(show_spinner=False)
def simuler(crise: str, strategie: str, mode: str, pente: float, duree: int):
    p = params_mode(mode, pente)
    p["pause"] = {**p["pause"], "duree_min": duree}
    res = simuler_crise(crise, resoudre_strategie(strategie)(), p)
    return res, calculer_kpi(res)


with st.spinner("Simulation des 3 modes…"):
    resultats = {m: simuler(crise, strategie, m, pente, duree_pause) for m in MODES}

ref = resultats["sans_pause"][1]["clients_heures"]
cols = st.columns(3)
for col, m in zip(cols, MODES, strict=True):
    k = resultats[m][1]
    with col:
        st.markdown(f"**{NOMS[m]}**")
        delta = None if m == "sans_pause" else f"{100 * (k['clients_heures'] / ref - 1):+.1f} %"
        st.metric("Clients·heures de coupure", f"{k['clients_heures']:,.0f}".replace(",", " "), delta,
                  delta_color="inverse")
        st.metric("Pauses prises", k["nb_pauses"])
        st.metric("Rendement moyen des chantiers", f"{100 / k['fatigue_moyenne']:.0f} %",
                  help="100 % = sans fatigue")
        st.caption(f"Attente max sensible {k['attente_max_sensible_h']:.1f} h · "
                   f"dépassements d'amplitude : {k['depassements_amplitude']}")

st.subheader("Clients coupés au fil de la crise")
fig = go.Figure()
for m in MODES:
    s = resultats[m][0].serie
    fig.add_trace(go.Scatter(x=s["t"] / 60, y=s["clients_coupes"], mode="lines", name=NOMS[m]))
fig.update_layout(height=360, xaxis_title="Heures", yaxis_title="Clients coupés",
                  margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h"))
st.plotly_chart(fig, use_container_width=True)

mode_g = st.selectbox("Gantt des équipes", list(MODES), index=2, format_func=lambda m: NOMS[m])
act = resultats[mode_g][0].activites.copy()
act = act[act["t_fin"] > act["t_debut"]]
act["debut"] = pd.Timestamp("2026-01-01") + pd.to_timedelta(act["t_debut"], unit="m")
act["fin"] = pd.Timestamp("2026-01-01") + pd.to_timedelta(act["t_fin"], unit="m")
fig2 = px.timeline(act, x_start="debut", x_end="fin", y="id_equipe", color="type", height=900,
                   color_discrete_map={"trajet": "#f2a541", "chantier": "#d1495b", "pause": "#2a9d8f",
                                       "retour": "#9db4c0", "repos": "#5c6b73", "hors_service": "#222222"})
fig2.update_yaxes(autorange="reversed", title=None)
fig2.update_layout(margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h"))
st.plotly_chart(fig2, use_container_width=True)

st.subheader("Sensibilité : à partir de quelle fatigue la pause devient rentable ?")
fichier = chemin_projet(charger_config()["chemins"]["outputs"]) / "pause_sensibilite.csv"
if fichier.exists():
    df = pd.read_csv(fichier)
    moy = df.groupby(["pente_fatigue", "mode"])["clients_heures"].mean().unstack()
    gain = (100 * (1 - moy.div(moy["sans_pause"], axis=0))).drop(columns="sans_pause").reset_index()
    gain = gain.melt(id_vars="pente_fatigue", var_name="mode", value_name="gain_pct")
    gain["mode"] = gain["mode"].map(NOMS)
    fig3 = px.line(gain, x="pente_fatigue", y="gain_pct", color="mode", markers=True, height=360,
                   labels={"pente_fatigue": "Perte de rendement par heure au-delà de 4h",
                           "gain_pct": "Gain de clients·heures vs sans pause (%)"})
    fig3.add_hline(y=0, line_dash="dot")
    fig3.update_xaxes(tickformat=".0%")
    st.plotly_chart(fig3, use_container_width=True)
    st.caption(f"Moyenne sur {df['crise'].nunique()} crises. Au-dessus de 0 : la pause fait gagner du temps "
               "aux clients ; en dessous : elle coûte.")
else:
    st.info("Lancer `python -m crise.pause_analyse` pour calculer la courbe de sensibilité.")
