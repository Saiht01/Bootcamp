"""Modelos de datos: empresa (agente retenedor) y proveedor (beneficiario del pago)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields


def _desde_dict(cls, datos: dict):
    """Crea una instancia ignorando claves desconocidas (tolerante a JSON viejos)."""
    nombres = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in datos.items() if k in nombres})


@dataclass
class Proveedor:
    nombre: str
    nit: str = ""
    tipo_persona: str = "juridica"  # "juridica" | "natural"
    declarante: bool = True  # solo relevante para personas naturales
    responsable_iva: bool = True  # RUT 48 (False = RUT 49)
    autorretenedor: bool = False  # RUT 15
    gran_contribuyente: bool = False  # RUT 13
    regimen_simple: bool = False  # RUT 47
    regimen_especial: bool = False  # RUT 04 (ESAL del RTE)
    no_contribuyente: bool = False  # RUT 06
    no_residente: bool = False  # proveedor del exterior
    iva_prestador_exterior: bool = False  # RUT 46
    sin_dos_trabajadores: bool = False  # PN que informa no haber vinculado 2+ trabajadores (art. 383 E.T.)
    sujeto_reteica: bool = True
    tarifa_ica_por_mil: float = 0.0
    responsabilidades: list = field(default_factory=list)  # códigos RUT casilla 53

    @property
    def es_persona_natural(self) -> bool:
        return self.tipo_persona == "natural"

    def clave_tarifa(self) -> str:
        if not self.es_persona_natural:
            return "pj"
        return "pn_declarante" if self.declarante else "pn_no_declarante"

    def descripcion_tipo(self) -> str:
        if not self.es_persona_natural:
            return "Persona jurídica"
        return "Persona natural declarante" if self.declarante else "Persona natural no declarante"

    @classmethod
    def desde_dict(cls, datos: dict) -> "Proveedor":
        return _desde_dict(cls, datos)

    def a_dict(self) -> dict:
        return asdict(self)


@dataclass
class Empresa:
    nombre: str
    nit: str = ""
    tipo_persona: str = "juridica"
    agente_retencion_renta: bool = True  # RUT 07
    regimen_simple: bool = False  # RUT 47
    gran_contribuyente: bool = False  # RUT 13
    agente_reteiva_designado: bool = False  # RUT 09 / 23 designado por la DIAN
    entidad_estatal: bool = False
    responsable_iva: bool = True  # RUT 48
    autorretenedor: bool = False  # RUT 15 (no cambia lo que retiene a terceros)
    agente_reteica: bool = False
    municipio: str = ""
    reteica_base_min_uvt: dict = field(default_factory=lambda: {"bien": 27, "servicio": 4, "otro": 0})
    tarifa_reteiva: float = 0.15
    responsabilidades: list = field(default_factory=list)  # códigos RUT casilla 53
    proveedores: list = field(default_factory=list)

    @property
    def es_agente_reteiva(self) -> bool:
        return self.entidad_estatal or self.gran_contribuyente or self.agente_reteiva_designado

    def lista_proveedores(self) -> list[Proveedor]:
        return [Proveedor.desde_dict(p) for p in self.proveedores]

    @classmethod
    def desde_dict(cls, datos: dict) -> "Empresa":
        return _desde_dict(cls, datos)

    def a_dict(self) -> dict:
        return asdict(self)


# Códigos RUT (casilla 53) que activan cada atributo.
CODIGOS_PROVEEDOR = {
    "04": "regimen_especial", "05": "declarante", "06": "no_contribuyente", "13": "gran_contribuyente",
    "15": "autorretenedor", "46": "iva_prestador_exterior", "47": "regimen_simple", "48": "responsable_iva",
}
CODIGOS_EMPRESA = {
    "07": "agente_retencion_renta", "09": "agente_reteiva_designado", "23": "agente_reteiva_designado",
    "13": "gran_contribuyente", "15": "autorretenedor", "47": "regimen_simple", "48": "responsable_iva",
}


def atributos_desde_rut(codigos: list[str], mapa: dict) -> dict:
    """Convierte la lista de responsabilidades del RUT en los atributos booleanos del modelo."""
    attrs = {campo: False for campo in set(mapa.values())}
    for c in codigos:
        if c in mapa:
            attrs[mapa[c]] = True
    return attrs
