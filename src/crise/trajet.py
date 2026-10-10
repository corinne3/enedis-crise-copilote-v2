"""Temps de trajet : haversine × coefficient de détour, vitesse plaine/montagne (selon la destination).

Tâche(s) : T1.4 — propriétaire : P1.
Voir docs/PLAN_EQUIPE_DEFI_ENEDIS.md.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crise.models import Equipe, Incident


def distance_haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcule la distance orthodromique (vol d'oiseau) en kilomètres entre deux coordonnées WGS84."""
    if math.isclose(lat1, lat2, abs_tol=1e-7) and math.isclose(lon1, lon2, abs_tol=1e-7):
        return 0.0
    radius = 6371.0  # Rayon terrestre moyen en km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    )
    # Protection contre d'éventuelles imprécisions flottantes > 1.0
    a = min(1.0, max(0.0, a))
    return 2.0 * radius * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def calculer_trajet_min(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    coef_detour: float = 1.3,
    vitesse_plaine_kmh: float = 55.0,
    vitesse_montagne_kmh: float = 35.0,
    lat_seuil_montagne: float = 43.05,
    multiplicateur_zone: float = 1.0,
) -> float:
    """Calcule la durée de trajet routier en minutes selon les règles du §5.2.

    Si lat2 < lat_seuil_montagne, la destination est en montagne (35 km/h).
    Sinon, elle est en plaine (55 km/h).
    Le multiplicateur_zone permet d'appliquer un ralentissement (ex: routes coupées / stress).
    """
    if multiplicateur_zone <= 0:
        raise ValueError(f"multiplicateur_zone doit être strictement positif, reçu: {multiplicateur_zone}")

    d_vol = distance_haversine_km(lat1, lon1, lat2, lon2)
    if d_vol == 0.0:
        return 0.0

    d_route = d_vol * coef_detour
    vitesse_base = vitesse_montagne_kmh if lat2 < lat_seuil_montagne else vitesse_plaine_kmh
    vitesse_effective = max(1.0, vitesse_base / multiplicateur_zone)
    return (d_route / vitesse_effective) * 60.0


def trajet_min(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Signature standard conforme au contrat Policy.decide."""
    return calculer_trajet_min(lat1, lon1, lat2, lon2)


def matrice_trajet_vectorisee(
    equipes: Sequence[Equipe],
    incidents: Sequence[Incident],
    coef_detour: float = 1.3,
    vitesse_plaine_kmh: float = 55.0,
    vitesse_montagne_kmh: float = 35.0,
    lat_seuil_montagne: float = 43.05,
    multiplicateur_zone: float = 1.0,
):
    """Calcul vectorisé numpy (§5.2) de la matrice des temps de trajet en minutes.

    Opération en bloc (len(equipes) x len(incidents)) par diffusion (broadcasting) numpy.
    """
    import numpy as np

    if multiplicateur_zone <= 0:
        raise ValueError(f"multiplicateur_zone doit être strictement positif, reçu: {multiplicateur_zone}")

    n_eq = len(equipes)
    n_inc = len(incidents)
    if n_eq == 0 or n_inc == 0:
        return np.zeros((n_eq, n_inc), dtype=float)

    lats_eq = np.radians(np.array([eq.lat for eq in equipes], dtype=float))[:, np.newaxis]
    lons_eq = np.radians(np.array([eq.lon for eq in equipes], dtype=float))[:, np.newaxis]
    lats_inc = np.radians(np.array([inc.lat for inc in incidents], dtype=float))[np.newaxis, :]
    lons_inc = np.radians(np.array([inc.lon for inc in incidents], dtype=float))[np.newaxis, :]

    dphi = lats_inc - lats_eq
    dlambda = lons_inc - lons_eq

    a = np.sin(dphi / 2.0) ** 2 + np.cos(lats_eq) * np.cos(lats_inc) * np.sin(dlambda / 2.0) ** 2
    a = np.clip(a, 0.0, 1.0)
    d_vol = 2.0 * 6371.0 * np.arcsin(np.sqrt(a))

    d_route = d_vol * coef_detour
    lats_inc_deg = np.array([inc.lat for inc in incidents], dtype=float)[np.newaxis, :]
    vitesses_base = np.where(lats_inc_deg < lat_seuil_montagne, vitesse_montagne_kmh, vitesse_plaine_kmh)
    vitesses_eff = np.maximum(1.0, vitesses_base / multiplicateur_zone)

    return (d_route / vitesses_eff) * 60.0


def matrice_trajet(
    equipes: Sequence[Equipe],
    incidents: Sequence[Incident],
    trajet_func=calculer_trajet_min,
) -> list[list[float]]:
    """Génère la matrice des temps de trajet (len(equipes) x len(incidents)) en minutes."""
    if trajet_func is calculer_trajet_min:
        try:
            return matrice_trajet_vectorisee(equipes, incidents).tolist()
        except ImportError:
            pass
    return [
        [trajet_func(eq.lat, eq.lon, inc.lat, inc.lon) for inc in incidents]
        for eq in equipes
    ]
