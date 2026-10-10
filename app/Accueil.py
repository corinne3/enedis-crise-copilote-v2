"""Salle de crise — page d'accueil Streamlit (T4.1, propriétaire : P4).

Lancement : streamlit run app/Accueil.py
Présente l'ambition Enedis (VOIR, PRÉVOIR, OPTIMISER), les chiffres clés,
et permet de lancer la démonstration sur données réelles ou factices (T4.1).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from crise.factice import generer_sim_result_factice
from crise.kpi import calculer_kpi

st.set_page_config(
    page_title="Salle de crise Enedis — Copilote IA",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------------------------------------------------------------------------- En-tête & Défi
st.title("⚡ Enedis — Copilote de Crise Climatique")
st.subheader("Optimiser le placement des ressources pour rétablir l'électricité toujours plus vite")

st.markdown(
    """
    > **Ressource → Incident → Clients rétablis.**  
    > Lors d'un événement climatique majeur (tempête, neige, inondations, orages, canicule), 
    > des dizaines d'incidents surviennent en parallèle sur les territoires d'Ariège, Haute-Garonne et Gers.  
    > **Le copilote Enedis aide le responsable de crise à arbitrer en temps réel avec explicabilité.**
    """
)

# --------------------------------------------------------------------------- Les 3 Piliers Enedis
col_voir, col_prevoir, col_optim = st.columns(3)

with col_voir:
    st.markdown("### 👁️ VOIR")
    st.markdown(
        """
        - **Consolider la situation** : incidents, réseau, clients impactés et moyens mobilisables.
        - **Cartographie animée** au pas de 30 min (Folium, Pydeck, Plotly).
        - Suivi en temps réel des chantiers et des trajets des équipes.
        """
    )

with col_prevoir:
    st.markdown("### 🔮 PRÉVOIR")
    st.markdown(
        """
        - **Projeter l'évolution** de la crise sur plusieurs pas de temps.
        - **Détecter les zones de tension** et les goulets de saturation territoriale.
        - Anticiper les fins d'amplitude et les relèves d'équipes.
        """
    )

with col_optim:
    st.markdown("### ⚙️ OPTIMISER")
    st.markdown(
        """
        - **Recommander le meilleur placement** et les affectations d'équipes (WSPT + hongrois).
        - **Prioriser les clients sensibles** (cliniques, EHPAD) et réduire les durées de coupure.
        - **Explicabilité transparente** de chaque arbitrage proposé.
        """
    )

st.divider()

# --------------------------------------------------------------------------- Chiffres Clés du Projet
st.subheader("📊 Résultats & Performance vs Stratégies de référence")

resume_path = Path("outputs/benchmark_resume.csv")
if resume_path.exists():
    try:
        df_resume = pd.read_csv(resume_path)
        st.dataframe(df_resume, use_container_width=True)
    except Exception:
        pass

c1, c2, c3, c4 = st.columns(4)
c1.metric(
    "Volume de coupure",
    "−11,3 %",
    "vs R1 (premier arrivé)",
    delta_color="inverse",
)
c2.metric(
    "Attente clients sensibles",
    "2,3 h",
    "−59 % (vs 5,6 h R1)",
    delta_color="inverse",
)
c3.metric(
    "Rétablis en < 4h",
    "21 %",
    "+7 pts vs R1 (14 %)",
)
c4.metric(
    "Sécurité & Dépassements",
    "0",
    "Amplitude 12h & repos 11h garantis",
    delta_color="off",
)

st.divider()

# --------------------------------------------------------------------------- Navigation & Modules
st.subheader("🧭 Modules de la Salle de Crise")

col_m1, col_m2 = st.columns(2)

with col_m1:
    st.info(
        """
        **🚨 Salle de crise express (Recommandée)**  
        *Accès : Menu de gauche → `Salle de crise express`*  
        - Rejeu dynamique d'une crise avec carte animée (Folium & Pydeck).
        - Comparaison R1, R2, WSPT et curseur temporel à pas de 30 min.
        - Explications détaillées de chaque affectation et arbitrage humain.
        """
    )
    st.info(
        """
        **📊 Banc d'essai & Benchmark**  
        *Accès : Menu de gauche → `Benchmark`*  
        - Analyse des performances sur 100 crises synthétiques.
        - Distributions statistiques et robustesse Monte Carlo.
        """
    )

with col_m2:
    st.info(
        """
        **🗺️ Préparation & Prépositionnement**  
        *Accès : Menu de gauche → `Preparation`*  
        - Carte de risque spatialisée (K-Means 200 zones).
        - Prépositionnement capacitaire p-médiane avant tempête.
        """
    )
    st.info(
        """
        **⚡ Stress Tests & Robustesse**  
        *Accès : Menu de gauche → `Stress tests`*  
        - Évaluation sous contraintes extrêmes : routes coupées (÷ 3),
          seconde vague à H+6, et indisponibilité de 50 % des équipes après 48h.
        """
    )

st.divider()

# --------------------------------------------------------------------------- Test Rapide : Données Factices (T4.1)
st.subheader("🧪 Mode Factice T4.1 — Démarrage Immédiat Sans Données Externes")
st.caption(
    "Permet de valider la chaîne complète du copilote (30 incidents, 6 équipes sur la zone Ariège/Garonne/Gers) "
    "de façon 100 % autonome."
)

if st.button("🚀 Générer et simuler un scénario factice (T4.1)"):
    with st.spinner("Simulation du scénario factice en cours..."):
        res_factice = generer_sim_result_factice(n_incidents=30, n_equipes=6, seed=42)
        kpi_factice = calculer_kpi(res_factice)

        st.success("✅ Scénario factice simulé avec succès !")
        sf1, sf2, sf3, sf4 = st.columns(4)
        sf1.metric("Incidents simulés", f"{len(res_factice.incidents)}")
        sf2.metric("Équipes mobilisées", f"{len(res_factice.activites['id_equipe'].unique())}")
        sf3.metric("Clients·heures totales", f"{kpi_factice['clients_heures']:,.0f}".replace(",", " "))
        sf4.metric("Dépassements d'amplitude", f"{kpi_factice['depassements_amplitude']}")

        with st.expander("Voir les 5 premières décisions du scénario factice"):
            st.dataframe(res_factice.decisions.head(5), use_container_width=True)

st.divider()

# --------------------------------------------------------------------------- Garde-fous éthiques & métier
st.caption(
    """
    🛡️ **Garde-fous métier et éthiques :**  
    1. **La sécurité prime** : amplitudes horaires 12h et repos obligatoires 11h incompressibles.  
    2. **L'outil recommande, le responsable métier décide** : suggestions contestables et modifiables.  
    3. **Données synthétiques** : aucune donnée personnelle. 100 % open source et exécutable sur CPU.
    """
)
