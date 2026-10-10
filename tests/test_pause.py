"""Tests V2 — pause repas et fatigue. La V1 (pause et fatigue désactivées) doit rester identique."""
import pytest

from crise.kpi import calculer_kpi
from crise.models import Equipe, Incident, Site
from crise.policies.baselines import PlusProcheFCFS
from crise.simulateur import facteur_fatigue, parametres_simulation, simuler


def trajet(lat1, lon1, lat2, lon2):
    return abs(lat1 - lat2) * 100 + abs(lon1 - lon2) * 100


def scenario(n=3, duree=120, lat=43.0):
    incs = [Incident(f"I{k}", f"P{k}", 0, duree, duree, "x", 50, False, lat, 1.0) for k in range(n)]
    return [Site("S1", "V", 43.0, 1.0, 1)], [Equipe("S1_E1", "S1", 43.0, 1.0)], incs


def run(**p):
    return simuler(*scenario(), PlusProcheFCFS(), parametres_simulation(**p), trajet)


def test_v1_inchangee_par_defaut():
    a = run()
    b = run(pause={"actif": False}, fatigue={"actif": False})
    assert a.metadata["clients_heures"] == b.metadata["clients_heures"]
    assert list(a.incidents["t_resolution"]) == [120, 240, 360]
    assert "pause" not in set(a.activites["type"])


def test_pause_fixe_apres_4h():
    r = run(pause={"actif": True, "mode": "fixe", "seuil_min": 240, "duree_min": 45})
    assert list(r.incidents["t_resolution"]) == [120, 240, 240 + 45 + 120]
    assert r.metadata["nb_pauses"] == 1 and "pause" in set(r.activites["type"])


def test_fatigue_allonge_et_plafonne():
    p = parametres_simulation(fatigue={"actif": True, "seuil_h": 0, "pente_par_h": 0.5, "max": 1.5})
    assert facteur_fatigue(0, p) == 1.0
    assert facteur_fatigue(60, p) == pytest.approx(1.5)
    assert facteur_fatigue(600, p) == pytest.approx(1.5)
    r = simuler(*scenario(), PlusProcheFCFS(), p, trajet)
    assert list(r.incidents["duree_reelle"]) == [120, 180, 180]


def test_pause_remet_la_fatigue_a_zero():
    fat = {"actif": True, "seuil_h": 0, "pente_par_h": 0.5, "max": 1.5}
    r = run(fatigue=fat, pause={"actif": True, "mode": "fixe", "seuil_min": 120, "duree_min": 30})
    assert list(r.incidents["duree_reelle"]) == [120, 120, 120]     # une pause après chaque chantier


def test_pause_intelligente_opportuniste():
    base = {"actif": True, "mode": "intelligente", "seuil_opportuniste_min": 100, "seuil_force_min": 1000,
            "rayon_min": 30, "part_max_site": 1.0}
    r = run(pause=base)                     # incidents sur place : pas de pause tant qu'il y a du travail à côté
    pauses = r.activites[r.activites["type"] == "pause"]
    assert list(pauses["t_debut"]) == [360]                  # seulement quand plus rien n'attend
    r = simuler(*scenario(n=2, lat=43.5), PlusProcheFCFS(), parametres_simulation(pause=base), trajet)
    assert r.metadata["nb_pauses"] >= 1                   # 2e incident à 50 min : pause opportuniste


def test_kpi_v2():
    k = calculer_kpi(run(pause={"actif": True, "mode": "fixe", "seuil_min": 240}))
    assert k["nb_pauses"] == 1 and k["depassements_amplitude"] == 0
    assert k["travail_max_sans_pause_h"] == pytest.approx(4.0)


def test_rotation_decale_les_prises_de_service():
    from crise.simulateur import groupes_rotation

    sites = [Site("S1", "V", 43.0, 1.0, 3)]
    eqs = [Equipe(f"S1_E{k}", "S1", 43.0, 1.0) for k in (1, 2, 3)]
    p = parametres_simulation(rotation={"actif": True, "groupes": 2, "decalage_min": 240})
    assert groupes_rotation(eqs, p) == {"S1_E1": 0, "S1_E2": 1, "S1_E3": 0}
    incs = [Incident(f"I{k}", f"P{k}", 0, 480, 480, "x", 50, False, 43.0, 1.0) for k in range(3)]
    r = simuler(sites, eqs, incs, PlusProcheFCFS(), p, trajet)
    act = r.activites
    astreinte = act[act["type"] == "astreinte"]
    assert list(astreinte["id_equipe"]) == ["S1_E2"] and astreinte["t_fin"].iloc[0] == 240
    assert r.incidents.set_index("id_equipe").loc["S1_E2", "t_affectation"] == 240
    k = calculer_kpi(r)
    assert k["depassements_amplitude"] == 0 and "heures_sans_equipe_active" in k


def test_rotation_sans_depassement_sur_vraie_crise():
    from crise.config import chemin_projet
    from crise.simulateur import simuler_crise

    if not (chemin_projet("data", "clean") / "incidents.parquet").exists():
        pytest.skip("lancer python -m crise.data.nettoyage")
    p = parametres_simulation(rotation={"actif": True, "groupes": 3, "decalage_min": 240}, expliquer=False)
    k = calculer_kpi(simuler_crise(5, PlusProcheFCFS(), p))
    assert k["depassements_amplitude"] == 0 and k["non_resolus"] == 0


def test_rotation_desactivee_par_defaut():
    a = run()
    b = run(rotation={"actif": False})
    assert a.metadata["clients_heures"] == b.metadata["clients_heures"]
    assert "astreinte" not in set(a.activites["type"])
