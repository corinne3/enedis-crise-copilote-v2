"""Salle de crise — version EXPRESS (écrite par P1 pour sécuriser la démo ; P4 garde la page principale).

Lancement : streamlit run app/Accueil.py   puis menu de gauche « Salle de crise express »
Montre : KPI référence vs stratégie, courbe des clients coupés, saturation, Gantt des équipes,
décisions, et les résultats du banc d'essai s'ils existent (outputs/benchmark_kpi.csv).
"""
from __future__ import annotations

import json
import logging

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from crise.benchmark import resoudre_strategie, resumer
from crise.config import charger_config, chemin_projet
from crise.kpi import calculer_kpi
from crise.models import lister_crises
from crise.simulateur import parametres_simulation, simuler_crise
from crise.trajet import ZONE_MONTAGNE, faire_trajet_min

logging.getLogger("crise.simulateur").setLevel(logging.ERROR)
st.set_page_config(page_title="Salle de crise express", layout="wide")
st.title("Salle de crise — copilote Enedis (express)")
st.caption("L'outil recommande, le responsable décide. Données synthétiques Enedis — hackathon IA for Impact 2026.")

# --------------------------------------------------------------------------- panneau latéral
NOMS = {"R1": "R1 · premier arrivé + plus proche", "R2": "R2 · plus de clients d'abord",
        "WSPT": "WSPT + hongrois (P2)", "WSPTX": "WSPT express (secours)"}
disponibles = []
for code in ("R1", "R2", "WSPT", "WSPTX"):
    try:
        resoudre_strategie(code)
        disponibles.append(code)
    except Exception:                                      # noqa: BLE001
        pass

with st.sidebar:
    crises = lister_crises()
    crise = st.selectbox("Crise", crises, index=crises.index("CRISE_027") if "CRISE_027" in crises else 0)
    choix = st.multiselect("Stratégies à comparer", disponibles,
                           default=[c for c in disponibles if c != "WSPTX"] or disponibles,
                           format_func=lambda c: NOMS.get(c, c))
    st.subheader("Paramètres")
    alpha = st.slider("Poids client sensible α", 0.0, 20.0, 5.0, 0.5)
    beta = st.slider("Poids de l'attente β (par heure)", 0.0, 0.5, 0.1, 0.05)
    st.subheader("Stress tests")
    routes_coupees = st.checkbox("Routes coupées en montagne (vitesse ÷ 3)")
    peu_equipes = st.slider("Nombre d'équipes", 10, 63, 63)
    hs = st.slider("% d'équipes hors service à H+3", 0, 50, 0, 10)


@st.cache_data(show_spinner=False)
def simuler(crise: str, code: str, alpha: float, beta: float, routes: bool, nb_eq: int, hs_pct: int):
    from crise.simulateur import Indisponibilite

    cfg = charger_config()
    p = parametres_simulation(cfg, alpha_sensible=alpha, beta_attente_par_h=beta)
    trajet = faire_trajet_min(cfg, zones=[ZONE_MONTAGNE] if routes else ())
    scenario = {"nb_equipes_max": nb_eq} if nb_eq < 63 else None
    options = {}
    if hs_pct:
        from crise.models import charger_scenario

        _, eqs, _ = charger_scenario(crise, scenario)
        n = round(len(eqs) * hs_pct / 100)
        options["indisponibilites"] = [Indisponibilite(e.id_equipe, 180) for e in eqs[::max(1, len(eqs) // n)][:n]]
    res = simuler_crise(crise, resoudre_strategie(code)(), p, scenario=scenario, trajet_min=trajet, **options)
    return res, calculer_kpi(res)


if not choix:
    st.info("Choisir au moins une stratégie.")
    st.stop()

resultats = {}
with st.spinner("Simulation…"):
    for c in choix:
        try:
            resultats[c] = simuler(crise, c, alpha, beta, routes_coupees, peu_equipes, hs)
        except Exception as e:                             # noqa: BLE001 — la démo ne doit jamais planter
            st.warning(f"{NOMS.get(c, c)} : erreur, stratégie ignorée ({e!r})")
choix = [c for c in choix if c in resultats]
if not choix:
    st.stop()

# --------------------------------------------------------------------------- KPI
ref = "R2" if "R2" in resultats else choix[0]
st.subheader("Indicateurs")
cols = st.columns(len(choix))
for col, c in zip(cols, choix, strict=True):
    _, k = resultats[c]
    k_ref = resultats[ref][1]
    with col:
        st.markdown(f"**{NOMS.get(c, c)}**")
        delta = None if c == ref else f"{100 * (k['clients_heures'] / k_ref['clients_heures'] - 1):+.1f} % vs {ref}"
        st.metric("Clients·heures de coupure", f"{k['clients_heures']:,.0f}".replace(",", " "), delta,
                  delta_color="inverse")
        st.metric("Attente max d'un poste sensible", f"{k['attente_max_sensible_h']:.1f} h")
        st.metric("Clients rétablis en moins de 4h", f"{k['pct_clients_retablis_4h']:.0f} %")
        st.metric("Fin de crise", f"{k['fin_crise_h']:.0f} h")
        st.caption(f"Saturation {k['saturation_pct']:.0f} % du temps · Gini {k['gini_communes']:.2f} · "
                   f"dépassements d'amplitude : {k['depassements_amplitude']}")

# --------------------------------------------------------------------------- courbe phare
st.subheader("Clients coupés au fil de la crise")
fig = go.Figure()
for c in choix:
    s = resultats[c][0].serie
    fig.add_trace(go.Scatter(x=s["t"] / 60, y=s["clients_coupes"], mode="lines", name=NOMS.get(c, c)))
fig.update_layout(xaxis_title="Heures depuis le début de la crise", yaxis_title="Clients coupés",
                  height=380, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h"))
st.plotly_chart(fig, use_container_width=True)
st.caption("L'aire sous chaque courbe = clients·heures de coupure. "
           "L'écart entre deux courbes = foyers rallumés plus tôt.")

# --------------------------------------------------------------------------- détail d'une stratégie
detail = st.selectbox("Détail de la stratégie", choix, index=len(choix) - 1, format_func=lambda c: NOMS.get(c, c))
res, _ = resultats[detail]
g1, g2 = st.columns(2)
with g1:
    st.markdown("**Équipes dans le temps**")
    s = res.serie
    fig2 = go.Figure()
    for col_, nom in [("equipes_occupees", "en intervention"), ("equipes_repos", "retour / repos"),
                      ("equipes_disponibles", "disponibles"), ("equipes_hs", "hors service")]:
        fig2.add_trace(go.Scatter(x=s["t"] / 60, y=s[col_], stackgroup="a", name=nom, mode="none"))
    fig2.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="Heures",
                       legend=dict(orientation="h"))
    st.plotly_chart(fig2, use_container_width=True)
with g2:
    st.markdown("**Carte des incidents (couleur = attente avant affectation)**")
    inc = res.incidents.assign(attente_h=lambda d: (d.t_affectation - d.t_apparition) / 60)
    carte = getattr(px, "scatter_map", None)               # plotly ≥ 5.24 ; sinon ancienne API mapbox
    fn, style = (carte, "map_style") if carte else (px.scatter_mapbox, "mapbox_style")
    fig3 = fn(inc, lat="lat", lon="lon", color="attente_h", size="nb_clients", size_max=12,
              hover_name="commune", hover_data={"nb_clients": True, "sensible": True},
              color_continuous_scale="OrRd", zoom=7, height=320)
    fig3.update_layout(**{style: "carto-positron"}, margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig3, use_container_width=True)

st.markdown("**Gantt des équipes**")
act = res.activites.copy()
act["debut"] = pd.Timestamp("2026-01-01") + pd.to_timedelta(act["t_debut"], unit="m")
act["fin"] = pd.Timestamp("2026-01-01") + pd.to_timedelta(act["t_fin"], unit="m")
act = act[act["t_fin"] > act["t_debut"]]
fig4 = px.timeline(act, x_start="debut", x_end="fin", y="id_equipe", color="type", height=900,
                   color_discrete_map={"trajet": "#f2a541", "chantier": "#d1495b", "retour": "#9db4c0",
                                       "repos": "#5c6b73", "hors_service": "#222222"})
fig4.update_yaxes(autorange="reversed", title=None)
fig4.update_layout(margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h"))
st.plotly_chart(fig4, use_container_width=True)

with st.expander("Décisions (explications)"):
    dec = res.decisions.copy()
    dec["heure"] = (dec["t"] / 60).round(2)
    dec["explication"] = dec["explication"].map(lambda j: ", ".join(f"{k}={v}" for k, v in json.loads(j).items()))
    st.dataframe(dec[["heure", "id_equipe", "id_incident", "explication"]], use_container_width=True, height=300)

# --------------------------------------------------------------------------- banc d'essai
fichier = chemin_projet(charger_config()["chemins"]["outputs"]) / "benchmark_kpi.csv"
st.subheader("Banc d'essai sur toutes les crises")
if fichier.exists():
    kpi = pd.read_csv(fichier)
    st.dataframe(resumer(kpi).T, use_container_width=True)
    st.plotly_chart(px.box(kpi, x="strategie", y="clients_heures", points="all", height=380,
                           labels={"clients_heures": "Clients·heures par crise", "strategie": ""}),
                    use_container_width=True)
else:
    st.info("Lancer `python -m crise.benchmark` pour comparer les stratégies sur les 100 crises.")
