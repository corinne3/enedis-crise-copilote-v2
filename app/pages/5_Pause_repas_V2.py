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
from crise.pause_analyse import MODES, ROTATIONS, params_mode
from crise.simulateur import simuler_crise

logging.getLogger("crise.simulateur").setLevel(logging.ERROR)
st.set_page_config(page_title="V2 — Pause repas", layout="wide")
st.title("V2 — Pause repas, fatigue et relève des équipes")
st.caption("Hypothèse : au-delà de 4h de travail sans pause, chaque heure allonge les dépannages. "
           "La pause (45 min, sur place, jamais pendant un chantier) remet le compteur à zéro. "
           "Le Code du travail impose déjà une pause après 6h de travail effectif : la V1 ne la modélisait pas.")

NOMS = {"sans_pause": "Sans pause", "pause_fixe": "Pause fixe à 4h", "pause_intelligente": "Pause intelligente"}
with st.sidebar:
    crises = lister_crises()
    crise = st.selectbox("Crise", crises, index=crises.index("CRISE_024") if "CRISE_024" in crises else 0)
    strategie = st.selectbox("Stratégie", ["WSPT", "R2", "R1"])
    pente = st.slider("Perte de rendement par heure au-delà de 4h (%)", 0, 15, 5) / 100
    duree_pause = st.slider("Durée de la pause (min)", 20, 60, 45, 5)
    rotation = st.selectbox("Relève des équipes", list(ROTATIONS), index=1,
                            help="Sans relève, toutes les équipes démarrent à H0 et se reposent en même temps.")
    mode_v2 = st.selectbox("Pause retenue pour la V2", ["pause_intelligente", "pause_fixe"],
                           format_func=lambda m: NOMS[m])


@st.cache_data(show_spinner=False)
def simuler(crise: str, strategie: str, mode: str, pente: float, duree: int, rotation: str = "aucune"):
    p = params_mode(mode, pente, rotation)
    p["pause"] = {**p["pause"], "duree_min": duree}
    res = simuler_crise(crise, resoudre_strategie(strategie)(), p)
    return res, calculer_kpi(res)


with st.spinner("Simulation des 3 modes…"):
    resultats = {m: simuler(crise, strategie, m, pente, duree_pause, rotation) for m in MODES}
    v1 = simuler(crise, strategie, "sans_pause", 0.0, duree_pause, "aucune")[1]   # V1 : ni pause, ni relève

# --------------------------------------------------------------------------- de la V1 à la V2, étape par étape
ETAPES = [
    ("① V1 (page Salle de crise express)", "sans_pause", 0.0, "aucune"),
    (f"② V1 + fatigue {pente:.0%}/h (plus réaliste)", "sans_pause", pente, "aucune"),
    (f"③ + {NOMS[mode_v2].lower()}", mode_v2, pente, "aucune"),
    (f"④ + relève « {rotation} » (sans pause)", "sans_pause", pente, rotation),
    ("⑤ V2 complète (pause + relève)", mode_v2, pente, rotation),
]
INDIC = {
    "clients_heures": ("Clients·heures", "{:,.0f}"),
    "attente_moy_sensible_h": ("Attente moy. sensible (h)", "{:.1f}"),
    "attente_p90_sensible_h": ("Attente 90 % sensibles (h)", "{:.1f}"),
    "attente_max_sensible_h": ("Attente max sensible (h)", "{:.1f}"),
    "pct_clients_retablis_4h": ("Rétablis < 4h (%)", "{:.0f}"),
    "retablis_95pct_h": ("95 % rétablis à (h)", "{:.0f}"),
    "fin_crise_h": ("Fin de crise (h)", "{:.0f}"),
    "heures_sans_equipe_active": ("Heures sans équipe active", "{:.1f}"),
}


def tableau_etapes(kpis: list[dict]) -> pd.DataFrame:
    lignes = []
    for (nom, *_), k in zip(ETAPES, kpis, strict=True):
        ligne = {"Étape": nom}
        for cle, (lib, fmt) in INDIC.items():
            ligne[lib] = fmt.format(k[cle]).replace(",", " ")
        ligne["Écart vs V1"] = f"{100 * (k['clients_heures'] / kpis[0]['clients_heures'] - 1):+.1f} %"
        lignes.append(ligne)
    return pd.DataFrame(lignes).set_index("Étape")


st.subheader(f"De la V1 à la V2, étape par étape — {crise}, stratégie {strategie}")
kpis_etapes = [simuler(crise, strategie, m, pt, duree_pause, rot)[1] for _, m, pt, rot in ETAPES]
st.dataframe(tableau_etapes(kpis_etapes), use_container_width=True)
st.caption("La ligne ① est identique à la page Salle de crise express (mêmes règles, même stratégie). "
           "« Attente max » et « Fin de crise » dépendent d'UN seul incident (pris juste avant ou juste après "
           "un repos : ±11h) : sur une crise, préférez l'attente moyenne, l'attente à 90 % et « 95 % rétablis ».")


@st.cache_data(show_spinner=False)
def etapes_moyennes(strategie: str, pente: float, duree: int, rotation: str, mode_v2: str, n: int) -> list[dict]:
    from crise.benchmark import lancer

    cls = resoudre_strategie(strategie)
    out = []
    for _, m, pt, rot in ETAPES:
        p = params_mode(m, pt, rot)
        p["pause"] = {**p["pause"], "duree_min": duree}
        kpi, _ = lancer(list(range(1, n + 1)), {strategie: cls}, params=p, n_jobs=2)
        out.append(kpi.mean(numeric_only=True).to_dict())
    return out


if st.button("Calculer le même tableau en moyenne sur 20 crises (≈ 1 min)"):
    with st.spinner("Calcul sur 20 crises…"):
        st.dataframe(tableau_etapes(etapes_moyennes(strategie, pente, duree_pause, rotation, mode_v2, 20)),
                     use_container_width=True)
    st.caption("Moyenne des crises 1 à 20 : ce sont ces chiffres-là qu'il faut citer au jury.")

st.subheader(f"Les 3 modes de pause — fatigue {pente:.0%}/h, relève « {rotation} »")
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
        st.metric("Heures sans aucune équipe au travail", f"{k['heures_sans_equipe_active']:.1f} h",
                  f"{k['heures_sans_equipe_active'] - v1['heures_sans_equipe_active']:+.1f} h vs V1",
                  delta_color="inverse")
        st.caption(f"Attente moyenne sensible {k['attente_moy_sensible_h']:.1f} h · 95 % rétablis à "
                   f"{k['retablis_95pct_h']:.0f} h · dépassements d'amplitude : {k['depassements_amplitude']}")

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
                                       "astreinte": "#cdb4db",
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

st.subheader("Relève des équipes : comparaison des organisations")
fichier_rot = chemin_projet(charger_config()["chemins"]["outputs"]) / "rotation_comparaison.csv"
if fichier_rot.exists():
    rot = pd.read_csv(fichier_rot)
    cols = {"clients_heures": "Clients·heures", "attente_max_sensible_h": "Attente max sensible (h)",
            "heures_sans_equipe_active": "Heures sans équipe active", "fin_crise_h": "Fin de crise (h)"}
    tab = rot.groupby("rotation", sort=False)[list(cols)].mean().round(1).rename(columns=cols)
    st.dataframe(tab, use_container_width=True)
    st.caption(f"Moyenne sur {rot['crise'].nunique()} crises, pause fixe, fatigue 5 %/h. Plus de groupes = "
               "meilleure couverture de la nuit, mais moins d'équipes au pic du début : arbitrage du responsable.")
else:
    st.info("Lancer `python -m crise.pause_analyse` pour comparer les organisations de relève.")
