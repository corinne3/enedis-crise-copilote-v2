"""Contrats d'interface — FIGÉS (voir docs/PLAN_EQUIPE_DEFI_ENEDIS.md §4).

Propriétaire : P1. Toute modification est annoncée à l'équipe avant d'être poussée.
Unités : temps en MINUTES depuis le début de la crise (int), distances en km, coordonnées WGS84.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class EtatEquipe(StrEnum):
    DISPONIBLE = "disponible"
    TRAJET = "trajet"
    CHANTIER = "chantier"
    RETOUR = "retour"          # retour base avant repos
    REPOS = "repos"
    HORS_SERVICE = "hors_service"


class EtatIncident(StrEnum):
    NON_APPARU = "non_apparu"
    EN_ATTENTE = "en_attente"
    AFFECTE = "affecte"        # équipe en route
    EN_COURS = "en_cours"      # chantier
    RESOLU = "resolu"


@dataclass
class Poste:
    id_poste: str
    commune: str
    departement: str
    lat: float
    lon: float
    nb_clients: int
    sensible: bool


@dataclass
class Site:
    id_site: str
    commune: str
    lat: float
    lon: float
    nb_equipes: int


@dataclass
class Incident:
    id_incident: str
    id_poste: str
    t_apparition: int          # min depuis début de crise
    duree_nominale: int        # min (120/240/480) — ce que voit la stratégie
    duree_reelle: int          # min — ce que joue le simulateur (= nominale sans Monte Carlo)
    cause: str
    nb_clients: int
    sensible: bool
    lat: float
    lon: float
    etat: EtatIncident = EtatIncident.NON_APPARU
    id_equipe: str | None = None
    t_affectation: int | None = None
    t_arrivee: int | None = None
    t_resolution: int | None = None


@dataclass
class Equipe:
    id_equipe: str             # ex "SITE_04_E2"
    id_site: str               # base de rattachement
    lat: float                 # position courante
    lon: float
    etat: EtatEquipe = EtatEquipe.DISPONIBLE
    t_debut_service: int = 0   # début de l'amplitude en cours
    t_libre: int = 0           # date où elle redevient disponible
    id_incident: str | None = None


@dataclass
class Affectation:
    id_equipe: str
    id_incident: str
    explication: dict = field(default_factory=dict)   # format §4.3


@dataclass
class EtatSimulation:
    """Ce que reçoit une stratégie à chaque décision."""
    t: int
    equipes_disponibles: list[Equipe]
    incidents_en_attente: list[Incident]
    toutes_equipes: list[Equipe]
    params: dict               # amplitude, repos, alpha, beta, vitesses…


# Colonnes attendues des 4 tables de SimResult (§4.4) — utilisées par les tests et les données factices.
COLONNES_SIMRESULT = {
    "incidents": [
        "id_incident", "id_poste", "lat", "lon", "nb_clients", "sensible", "commune", "departement",
        "t_apparition", "t_affectation", "t_arrivee", "t_resolution", "id_equipe", "duree_reelle",
    ],
    "activites": [
        "id_equipe", "type", "t_debut", "t_fin", "id_incident", "lat_dep", "lon_dep", "lat_arr", "lon_arr",
    ],
    "decisions": ["t", "id_equipe", "id_incident", "explication"],
    "serie": ["t", "clients_coupes", "incidents_attente", "equipes_occupees", "equipes_repos"],
}


def charger_scenario(numero_crise: str, params: dict | None = None):
    """T1.3 (P1) — renvoie (sites, equipes, incidents) pour une crise, depuis data/clean/*.parquet."""
    raise NotImplementedError("T1.3 — à implémenter par P1")
