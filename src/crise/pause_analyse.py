"""V2 — pause repas : comparaison « sans pause / pause fixe / pause intelligente » et sensibilité à la fatigue.

    python -m crise.pause_analyse                          # crises 1-30, pentes 0 à 10 %/h, stratégie WSPT
    python -m crise.pause_analyse --crises 1-100 --pentes 0,0.05,0.1 --jobs 2

Sorties : outputs/pause_sensibilite.csv (une ligne par crise × mode × pente) + résumé imprimé.

Hypothèse clé (à faire valider par Enedis) : au-delà de `seuil_h` heures de travail sans pause, chaque heure
supplémentaire allonge les dépannages de `pente` (ex. 0,05 = +5 %/h). Sans données réelles, on montre le
résultat pour plusieurs pentes : c'est la courbe de sensibilité.
"""
from __future__ import annotations

import argparse
import logging

import pandas as pd

from crise.benchmark import lancer, parser_crises, resoudre_strategie
from crise.config import charger_config, chemin_projet
from crise.simulateur import parametres_simulation

MODES = {
    "sans_pause": {"actif": False},
    "pause_fixe": {"actif": True, "mode": "fixe"},
    "pause_intelligente": {"actif": True, "mode": "intelligente"},
}


ROTATIONS = {
    "aucune": {"actif": False},
    "2 groupes, +4h": {"actif": True, "groupes": 2, "decalage_min": 240},
    "2 groupes, +6h": {"actif": True, "groupes": 2, "decalage_min": 360},
    "3 groupes, +4h": {"actif": True, "groupes": 3, "decalage_min": 240},
}


def params_mode(mode: str, pente: float, rotation: str = "aucune", **surcharges) -> dict:
    """Paramètres pour un mode de pause, une pente de fatigue (active si > 0) et une organisation de relève."""
    return parametres_simulation(
        pause=MODES[mode], fatigue={"actif": pente > 0, "pente_par_h": pente}, rotation=ROTATIONS[rotation],
        expliquer=False, **surcharges)


def comparer(crises: list[int], pentes: list[float], strategie: str = "WSPT", n_jobs: int = -1,
             rotation: str = "aucune") -> pd.DataFrame:
    cls = resoudre_strategie(strategie)
    lignes = []
    for pente in pentes:
        for mode in MODES:
            kpi, _ = lancer(crises, {strategie: cls}, params=params_mode(mode, pente, rotation), n_jobs=n_jobs)
            kpi["mode"], kpi["pente_fatigue"], kpi["rotation"] = mode, pente, rotation
            lignes.append(kpi)
    return pd.concat(lignes, ignore_index=True)


def comparer_rotations(crises: list[int], strategie: str = "WSPT", n_jobs: int = -1, pente: float = 0.05,
                       mode: str = "pause_fixe") -> pd.DataFrame:
    """Organisations de relève comparées (même pause, même fatigue)."""
    cls = resoudre_strategie(strategie)
    lignes = []
    for rot in ROTATIONS:
        kpi, _ = lancer(crises, {strategie: cls}, params=params_mode(mode, pente, rot), n_jobs=n_jobs)
        kpi["rotation"], kpi["mode"], kpi["pente_fatigue"] = rot, mode, pente
        lignes.append(kpi)
    return pd.concat(lignes, ignore_index=True)


def resumer(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["clients_heures", "attente_max_sensible_h", "nb_pauses", "travail_max_sans_pause_h",
            "fatigue_moyenne", "depassements_amplitude"]
    r = df.groupby(["pente_fatigue", "mode"])[cols].mean().round(2)
    base = r.xs("sans_pause", level="mode")["clients_heures"]
    r["gain_vs_sans_pause_pct"] = [
        round(100 * (1 - v / base.loc[p]), 2) for (p, _), v in r["clients_heures"].items()]
    return r


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="V2 — pause repas et fatigue")
    ap.add_argument("--crises", default="1-30")
    ap.add_argument("--pentes", default="0,0.02,0.05,0.08,0.1")
    ap.add_argument("--strategie", default="WSPT")
    ap.add_argument("--jobs", type=int, default=-1)
    ap.add_argument("--rotation", default="aucune", choices=list(ROTATIONS))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("crise.simulateur").setLevel(logging.ERROR)
    crises = parser_crises(args.crises)
    df = comparer(crises, [float(x) for x in args.pentes.split(",")], args.strategie, args.jobs, args.rotation)
    dossier = chemin_projet(charger_config()["chemins"]["outputs"])
    dossier.mkdir(parents=True, exist_ok=True)
    df.to_csv(dossier / "pause_sensibilite.csv", index=False)
    print("\n=== Pause repas : moyennes par pente de fatigue et par mode ===")
    print(resumer(df).to_string())
    rot = comparer_rotations(crises, args.strategie, args.jobs)
    rot.to_csv(dossier / "rotation_comparaison.csv", index=False)
    cols = ["clients_heures", "attente_max_sensible_h", "heures_sans_equipe_active", "fin_crise_h",
            "depassements_amplitude"]
    print("\n=== Relève des équipes (pause fixe, fatigue 5 %/h) ===")
    print(rot.groupby("rotation", sort=False)[cols].mean().round(2).to_string())
    print(f"\nFichiers écrits : {dossier / 'pause_sensibilite.csv'} et {dossier / 'rotation_comparaison.csv'}")


if __name__ == "__main__":
    main()
