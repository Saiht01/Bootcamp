"""Carga y guardado de la información parametrizable (tablas, responsabilidades, empresas)."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from .modelos import Empresa

DATOS = Path(__file__).resolve().parent.parent / "datos"
DIR_TABLAS = DATOS / "tablas"
DIR_EMPRESAS = DATOS / "empresas"


def _leer(ruta: Path):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def listar_tablas() -> list[dict]:
    tablas = [_leer(p) | {"_archivo": p.name} for p in sorted(DIR_TABLAS.glob("*.json"))]
    return sorted(tablas, key=lambda t: t["vigencia_desde"])


def tabla_vigente(fecha: date | None = None) -> dict:
    """Devuelve la tabla cuya vigencia cubre la fecha (o la más reciente anterior)."""
    fecha = (fecha or date.today()).isoformat()
    tablas = listar_tablas()
    if not tablas:
        raise FileNotFoundError(f"No hay tablas de retención en {DIR_TABLAS}")
    candidatas = [t for t in tablas if t["vigencia_desde"] <= fecha]
    return candidatas[-1] if candidatas else tablas[0]


def responsabilidades_rut() -> list[dict]:
    return _leer(DATOS / "responsabilidades_rut.json")


def listar_empresas() -> list[str]:
    return sorted(p.stem for p in DIR_EMPRESAS.glob("*.json"))


def cargar_empresa(clave: str) -> Empresa:
    return Empresa.desde_dict(_leer(DIR_EMPRESAS / f"{clave}.json"))


def clave_empresa(nombre: str) -> str:
    clave = re.sub(r"[^a-z0-9]+", "_", nombre.lower()).strip("_")
    return clave or "empresa"


def guardar_empresa(empresa: Empresa, clave: str | None = None) -> str:
    clave = clave or clave_empresa(empresa.nombre)
    DIR_EMPRESAS.mkdir(parents=True, exist_ok=True)
    with open(DIR_EMPRESAS / f"{clave}.json", "w", encoding="utf-8") as f:
        json.dump(empresa.a_dict(), f, ensure_ascii=False, indent=2)
    return clave
