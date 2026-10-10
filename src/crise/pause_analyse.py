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


def params_mode(mode: str, pente: float, **surcharges) -> dict:
    """Paramètres de simulation pour un mode de pause et une pente de fatigue (fatigue active si pente > 0)."""
    return parametres_simulation(
        pause=MODES[mode], fatigue={"actif": pente > 0, "pente_par_h": pente}, expliquer=False, **surcharges)


def comparer(crises: list[int], pentes: list[float], strategie: str = "WSPT", n_jobs: int = -1) -> pd.DataFrame:
    cls = resoudre_strategie(strategie)
    lignes = []
    for pente in pentes:
        for mode in MODES:
            kpi, _ = lancer(crises, {strategie: cls}, params=params_mode(mode, pente), n_jobs=n_jobs)
            kpi["mode"], kpi["pente_fatigue"] = mode, pente
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
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("crise.simulateur").setLevel(logging.ERROR)
    df = comparer(parser_crises(args.crises), [float(x) for x in args.pentes.split(",")], args.strategie, args.jobs)
    dossier = chemin_projet(charger_config()["chemins"]["outputs"])
    dossier.mkdir(parents=True, exist_ok=True)
    df.to_csv(dossier / "pause_sensibilite.csv", index=False)
    print("\n=== Pause repas : moyennes par pente de fatigue et par mode ===")
    print(resumer(df).to_string())
    print(f"\nFichier écrit : {dossier / 'pause_sensibilite.csv'}")


if __name__ == "__main__":
    main()
