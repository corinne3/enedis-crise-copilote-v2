"""Tests de T1.5 (simulateur) et T1.6 (stratégies de référence).

Les invariants vérifiés ici sont ceux que le jury peut contrôler : une équipe = un incident à la fois,
pas de résolution avant trajet + dépannage, amplitude respectée, tous les incidents résolus.
"""
import json

import pandas as pd
import pytest

from crise.config import chemin_projet
from crise.models import COLONNES_SIMRESULT, Affectation, Equipe, Incident, SimResult, Site
from crise.policies.base import Policy
from crise.policies.baselines import PlusDeClients, PlusProcheFCFS
from crise.simulateur import Indisponibilite, parametres_simulation, simuler, simuler_crise


# --------------------------------------------------------------------------- outils
def trajet_lineaire(lat1, lon1, lat2, lon2):
    """Trajet de test : 100 min par degré de latitude, 0 si même point (simple à calculer à la main)."""
    return abs(lat1 - lat2) * 100 + abs(lon1 - lon2) * 100


def params(**k):
    return parametres_simulation(None, **k)


def site(id_site="S1", lat=43.0, lon=1.0, n=1):
    return Site(id_site, "Ville", lat, lon, n)


def equipe(id_eq="S1_E1", id_site="S1", lat=43.0, lon=1.0):
    return Equipe(id_eq, id_site, lat, lon)


def incident(id_inc, t=0, duree=240, clients=50, lat=43.0, lon=1.0, sensible=False, poste=None):
    return Incident(id_inc, poste or f"P_{id_inc}", t, duree, duree, "test", clients, sensible, lat, lon)


def verifier_invariants(res: SimResult, amplitude: int | None = None):
    inc, act = res.incidents, res.activites
    for nom, cols in COLONNES_SIMRESULT.items():
        assert set(cols) <= set(getattr(res, nom).columns), nom
    assert res.metadata["non_resolus"] == 0
    assert (inc["t_affectation"] >= inc["t_apparition"]).all()
    assert (inc["t_arrivee"] >= inc["t_affectation"]).all()
    assert (inc["t_resolution"] == inc["t_arrivee"] + inc["duree_reelle"]).all()
    # une équipe = une activité à la fois
    for _, g in act.sort_values(["id_equipe", "t_debut"]).groupby("id_equipe"):
        assert (g["t_debut"].to_numpy()[1:] >= g["t_fin"].to_numpy()[:-1]).all()
    # chaque incident : exactement 1 trajet + 1 chantier
    travail = act[act["type"].isin(["trajet", "chantier"])]
    assert (travail.groupby("id_incident")["type"].nunique() == 2).all()
    if amplitude is not None:                       # travail dans l'amplitude (durées nominales)
        for id_eq, g in act.sort_values("t_debut").groupby("id_equipe"):
            debut_service = 0
            for r in g.itertuples():
                if r.type == "repos":
                    debut_service = r.t_fin
                elif r.type in ("trajet", "chantier"):
                    assert r.t_fin - debut_service <= amplitude, (id_eq, r)


# --------------------------------------------------------------------------- T1.5 : cas calculés à la main
def test_un_incident():
    res = simuler([site()], [equipe(lat=43.5)], [incident("A", t=10)], PlusProcheFCFS(), params(),
                  trajet_lineaire)
    r = res.incidents.set_index("id_incident").loc["A"]
    assert (r.t_affectation, r.t_arrivee, r.t_resolution) == (10, 60, 300)   # 50 min de trajet, 240 de chantier
    assert res.metadata["clients_heures"] == pytest.approx(50 * 290 / 60, abs=0.1)
    verifier_invariants(res)


def test_exemple_wspt_du_plan():
    """§5.3 : A (150 clients, 8h) puis B (50 clients, 2h) = 1 700 ; B puis A = 1 600."""
    incs = [incident("A", t=0, duree=480, clients=150), incident("B", t=0, duree=120, clients=50)]
    r1 = simuler([site()], [equipe()], incs, PlusProcheFCFS(), params(), trajet_lineaire)
    assert r1.metadata["clients_heures"] == pytest.approx(1700)

    class BdAbord(Policy):
        nom = "B_d_abord"

        def decide(self, etat, trajet_min):
            ordre = sorted(etat.incidents_en_attente, key=lambda i: i.duree_nominale)
            return [Affectation(etat.equipes_disponibles[0].id_equipe, ordre[0].id_incident)]

    incs = [incident("A", t=0, duree=480, clients=150), incident("B", t=0, duree=120, clients=50)]
    r2 = simuler([site()], [equipe()], incs, BdAbord(), params(), trajet_lineaire)
    assert r2.metadata["clients_heures"] == pytest.approx(1600)


def test_r2_plus_de_clients_d_abord():
    incs = [incident("petit", t=0, clients=10), incident("gros", t=5, clients=150)]
    res = simuler([site()], [equipe()], incs, PlusDeClients(), params(), trajet_lineaire)
    i = res.incidents.set_index("id_incident")
    assert i.loc["petit", "t_affectation"] == 0           # seul en attente à t=0
    incs = [incident("petit", t=0, clients=10), incident("gros", t=0, clients=150)]
    res = simuler([site()], [equipe()], incs, PlusDeClients(), params(), trajet_lineaire)
    i = res.incidents.set_index("id_incident")
    assert i.loc["gros", "t_affectation"] == 0 and i.loc["petit", "t_affectation"] == 240


def test_plus_proche():
    sites = [site("S1", 43.0, 1.0), site("S2", 44.0, 1.0)]
    eqs = [equipe("S1_E1", "S1", 43.0, 1.0), equipe("S2_E1", "S2", 44.0, 1.0)]
    res = simuler(sites, eqs, [incident("A", lat=43.9)], PlusProcheFCFS(), params(), trajet_lineaire)
    assert res.incidents.loc[0, "id_equipe"] == "S2_E1"


def test_amplitude_puis_repos():
    """Amplitude 12h : après 3 chantiers de 4h l'équipe rentre, se repose 11h, puis reprend."""
    incs = [incident(f"I{k}", t=0) for k in range(4)]
    p = params()
    res = simuler([site()], [equipe()], incs, PlusProcheFCFS(), p, trajet_lineaire)
    i = res.incidents.set_index("id_incident")
    assert list(i["t_resolution"]) == [240, 480, 720, 720 + 660 + 240]
    assert "repos" in set(res.activites["type"])
    verifier_invariants(res, p["amplitude_max_min"])


def test_affectation_infaisable_refusee():
    """Une stratégie qui viole l'amplitude est bloquée par le simulateur (garde-fou sécurité)."""
    class Imprudente(Policy):
        nom = "imprudente"

        def decide(self, etat, trajet_min):
            return [Affectation(etat.equipes_disponibles[0].id_equipe, etat.incidents_en_attente[0].id_incident)]

    incs = [incident("A", t=0, duree=480, lat=46.0)]          # 300 min de trajet + 480 > 720
    res = simuler([site()], [equipe()], incs, Imprudente(), params(), trajet_lineaire)
    assert any(r["motif"] == "amplitude insuffisante" for r in res.metadata["rejets"])


def test_forcee_et_interdite():
    sites = [site("S1", 43.0, 1.0), site("S2", 44.0, 1.0)]
    eqs = lambda: [equipe("S1_E1", "S1", 43.0, 1.0), equipe("S2_E1", "S2", 44.0, 1.0)]  # noqa: E731
    inc = lambda: [incident("A", lat=43.0)]                                              # noqa: E731
    res = simuler(sites, eqs(), inc(), PlusProcheFCFS(), params(), trajet_lineaire, forcees={"S2_E1": "A"})
    assert res.incidents.loc[0, "id_equipe"] == "S2_E1"
    assert json.loads(res.decisions.loc[0, "explication"])["origine"] == "humain"
    res = simuler(sites, eqs(), inc(), PlusProcheFCFS(), params(), trajet_lineaire, interdites={("S1_E1", "A")})
    assert res.incidents.loc[0, "id_equipe"] == "S2_E1"

    class Tetue(Policy):              # ignore les interdictions : le simulateur doit quand même s'en sortir
        nom = "tetue"

        def decide(self, etat, trajet_min):
            eq = sorted(etat.equipes_disponibles, key=lambda e: e.id_equipe)[0]
            return [Affectation(eq.id_equipe, etat.incidents_en_attente[0].id_incident)]

    res = simuler(sites, eqs(), inc(), Tetue(), params(), trajet_lineaire, interdites={("S1_E1", "A")})
    assert res.incidents.loc[0, "id_equipe"] == "S2_E1"
    assert res.metadata["rejets"][0]["motif"].startswith("affectation interdite")


def test_indisponibilite_apres_chantier():
    """Indisponible à t=60 alors qu'elle est sur un chantier : elle le termine, puis hors service."""
    sites = [site("S1", 43.0, 1.0)]
    eqs = [equipe("S1_E1"), Equipe("S1_E2", "S1", 43.0, 1.0)]
    incs = [incident("A", t=0), incident("B", t=0), incident("C", t=100)]
    res = simuler(sites, eqs, incs, PlusProcheFCFS(), params(), trajet_lineaire,
                  indisponibilites=[Indisponibilite("S1_E1", 60)])
    i = res.incidents.set_index("id_incident")
    assert i.loc["A", "t_resolution"] == 240                      # chantier terminé malgré l'indisponibilité
    assert i.loc["C", "id_equipe"] == "S1_E2"
    assert "hors_service" in set(res.activites["type"])
    verifier_invariants(res)


def test_serie_compte_un_poste_une_fois():
    incs = [incident("A", t=0, clients=100, poste="P1"), incident("B", t=0, clients=100, poste="P1")]
    res = simuler([site()], [equipe()], incs, PlusProcheFCFS(), params(), trajet_lineaire)
    assert res.serie.loc[res.serie.t == 0, "clients_coupes"].item() == 100
    assert res.serie["clients_coupes"].iloc[-1] == 0


def test_monte_carlo_reproductible():
    def run(seed):
        incs = [incident(f"I{k}", t=10 * k, lat=43 + k / 10) for k in range(5)]
        p = params(seed=seed, monte_carlo={"actif": True})
        return simuler([site(n=2)], [equipe(), equipe("S1_E2")], incs, PlusProcheFCFS(), p, trajet_lineaire)
    a, b, c = run(1), run(1), run(2)
    pd.testing.assert_frame_equal(a.incidents, b.incidents)
    assert not a.incidents["duree_reelle"].equals(c.incidents["duree_reelle"])
    verifier_invariants(a)


# --------------------------------------------------------------------------- vraies données
CLEAN = chemin_projet("data", "clean")


@pytest.mark.skipif(not (CLEAN / "incidents.parquet").exists(), reason="lancer python -m crise.data.nettoyage")
@pytest.mark.parametrize("policy", [PlusProcheFCFS, PlusDeClients])
def test_vraie_crise(policy):
    p = params()
    res = simuler_crise(27, policy(), p)
    verifier_invariants(res, p["amplitude_max_min"])
    assert res.metadata["nb_incidents"] == 250 and res.metadata["nb_equipes"] == 63
    assert res.metadata["duree_calcul_s"] < 10
    assert res.incidents["commune"].notna().all()
    assert res.serie["clients_coupes"].iloc[-1] == 0
