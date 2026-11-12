import pytest

from retenciones.modelos import Empresa, Proveedor
from retenciones.motor import calcular_art_383, calcular_retenciones
from retenciones.tablas import tabla_vigente

TABLA = tabla_vigente()
UVT = TABLA["uvt"]


def empresa(**kw):
    base = dict(nombre="Test SAS", agente_retencion_renta=True, agente_reteica=True,
                reteica_base_min_uvt={"bien": 27, "servicio": 4, "otro": 0})
    base.update(kw)
    return Empresa(**base)


def proveedor(**kw):
    base = dict(nombre="Prov", tarifa_ica_por_mil=9.66)
    base.update(kw)
    return Proveedor(**base)


def test_uvt_2026():
    assert UVT == 52374


def test_compras_pj_declarante():
    r = calcular_retenciones(empresa(), proveedor(), "compras_generales", 1_000_000, TABLA)
    renta = r.linea("Retención")
    assert renta.aplica and renta.tarifa == 0.025 and renta.valor == 25_000


def test_compras_bajo_base_minima():
    r = calcular_retenciones(empresa(), proveedor(), "compras_generales", 10 * UVT - 1, TABLA)
    assert not r.linea("Retención").aplica


def test_servicios_pn_no_declarante_6pct():
    p = proveedor(tipo_persona="natural", declarante=False, responsable_iva=False)
    r = calcular_retenciones(empresa(), p, "servicios_generales", 200_000, TABLA)
    assert r.linea("Retención").valor == 12_000


def test_honorarios_pn_supera_3300_uvt():
    p = proveedor(tipo_persona="natural", declarante=True)
    r = calcular_retenciones(empresa(), p, "honorarios", 5_000_000, TABLA, pagos_acumulados_anio=3300 * UVT)
    assert r.linea("Retención").tarifa == 0.11
    r = calcular_retenciones(empresa(), p, "honorarios", 5_000_000, TABLA)
    assert r.linea("Retención").tarifa == 0.10


@pytest.mark.parametrize("flag", ["autorretenedor", "regimen_simple", "no_contribuyente"])
def test_proveedor_no_sujeto_renta(flag):
    r = calcular_retenciones(empresa(), proveedor(**{flag: True}), "servicios_generales", 5_000_000, TABLA)
    assert not r.linea("Retención").aplica


def test_rte_solo_rendimientos():
    p = proveedor(regimen_especial=True)
    assert not calcular_retenciones(empresa(), p, "servicios_generales", 5_000_000, TABLA).linea("Retención").aplica
    assert calcular_retenciones(empresa(), p, "rendimientos_financieros", 5_000_000, TABLA).linea("Retención").aplica


def test_empresa_simple_no_retiene():
    r = calcular_retenciones(empresa(regimen_simple=True), proveedor(), "servicios_generales", 5_000_000, TABLA)
    assert not r.linea("Retención").aplica


def test_vivienda_por_tramos():
    base = 12_000 * UVT
    r = calcular_retenciones(empresa(), proveedor(), "bienes_raices_vivienda", base, TABLA)
    esperado = round(10_000 * UVT * 0.01 + 2_000 * UVT * 0.025)
    assert r.linea("Retención").valor == esperado


def test_reteiva_gran_contribuyente():
    e = empresa(gran_contribuyente=True)
    r = calcular_retenciones(e, proveedor(), "servicios_generales", 1_000_000, TABLA, iva=190_000)
    assert r.linea("ReteIVA").valor == 28_500
    # Entre grandes contribuyentes no hay reteIVA
    r = calcular_retenciones(e, proveedor(gran_contribuyente=True), "servicios_generales", 1_000_000, TABLA, iva=190_000)
    assert not r.linea("ReteIVA").aplica


def test_reteiva_empresa_no_agente():
    r = calcular_retenciones(empresa(), proveedor(), "servicios_generales", 1_000_000, TABLA, iva=190_000)
    assert not r.linea("ReteIVA").aplica


def test_reteiva_no_residente_100():
    p = proveedor(no_residente=True)
    r = calcular_retenciones(empresa(), p, "ext_servicios_generales", 1_000_000, TABLA, iva=190_000)
    assert r.linea("ReteIVA").valor == 190_000
    assert r.linea("Retención").valor == 200_000
    assert not r.linea("ReteICA").aplica


def test_reteica():
    r = calcular_retenciones(empresa(), proveedor(), "servicios_generales", 1_000_000, TABLA)
    assert r.linea("ReteICA").valor == 9_660
    r = calcular_retenciones(empresa(), proveedor(), "servicios_generales", 4 * UVT - 1, TABLA)
    assert not r.linea("ReteICA").aplica


def test_neto_a_pagar():
    e = empresa(gran_contribuyente=True)
    r = calcular_retenciones(e, proveedor(), "servicios_generales", 1_000_000, TABLA, iva=190_000)
    assert r.neto_a_pagar == 1_190_000 - 40_000 - 28_500 - 9_660


def test_art_383_bajo_95_uvt():
    valor, _ = calcular_art_383(4_000_000, TABLA)
    assert valor == 0


def test_art_383_rango_19():
    # 10M sin aportes: subtotal 10M, exenta 25% = 2.5M (tope 790/12 UVT ≈ 3.45M) → base 7.5M
    valor, _ = calcular_art_383(10_000_000, TABLA)
    base_uvt = 7_500_000 / UVT
    esperado = round((base_uvt - 95) * 0.19 * UVT)
    assert abs(valor - esperado) <= 1


def test_art_383_desde_motor():
    p = proveedor(tipo_persona="natural", sin_dos_trabajadores=True)
    r = calcular_retenciones(empresa(), p, "honorarios", 10_000_000, TABLA, usar_art_383=True)
    assert r.linea("Retención").aplica and r.linea("Retención").valor > 0
