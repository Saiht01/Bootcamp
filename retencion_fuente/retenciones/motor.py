"""Motor de cálculo de retenciones en la fuente (renta, IVA e ICA) para Colombia.

Toda la lógica es pura (sin interfaz) para poder probarla y reutilizarla.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .modelos import Empresa, Proveedor


@dataclass
class LineaRetencion:
    impuesto: str  # "Retención en la fuente (renta)" | "ReteIVA" | "ReteICA"
    aplica: bool
    motivo: str
    base: float = 0.0
    tarifa: float = 0.0  # proporción (0.04 = 4%)
    valor: float = 0.0
    detalle: list[str] = field(default_factory=list)


@dataclass
class ResultadoRetencion:
    concepto: dict
    base: float
    iva: float
    lineas: list[LineaRetencion]
    advertencias: list[str] = field(default_factory=list)

    @property
    def total_retenciones(self) -> float:
        return sum(l.valor for l in self.lineas if l.aplica)

    @property
    def total_factura(self) -> float:
        return self.base + self.iva

    @property
    def neto_a_pagar(self) -> float:
        return self.total_factura - self.total_retenciones

    def linea(self, impuesto_prefijo: str) -> LineaRetencion:
        for l in self.lineas:
            if l.impuesto.startswith(impuesto_prefijo):
                return l
        raise KeyError(impuesto_prefijo)


def redondear(valor: float) -> float:
    """Redondea a pesos enteros (mitad hacia arriba)."""
    return float(int(valor + 0.5)) if valor >= 0 else -float(int(-valor + 0.5))


def buscar_concepto(tabla: dict, concepto_id: str) -> dict:
    for c in tabla["conceptos"]:
        if c["id"] == concepto_id:
            return c
    raise KeyError(f"Concepto no encontrado: {concepto_id}")


# ---------------------------------------------------------------------------
# Retención en la fuente a título de renta
# ---------------------------------------------------------------------------

def calcular_art_383(base_mensual: float, tabla: dict, aportes_obligatorios: float = 0.0,
                     deducciones: float = 0.0) -> tuple[float, list[str]]:
    """Retención con la tabla del art. 383 E.T. (procedimiento 1, depuración simplificada).

    base_mensual: pago del mes.
    aportes_obligatorios: aportes obligatorios a salud y pensión (ingreso no constitutivo de renta).
    deducciones: deducciones/rentas exentas adicionales soportadas (dependientes, AFC, etc.).
    """
    uvt = tabla["uvt"]
    cfg = tabla["art_383"]
    detalle = []
    ingreso_neto = max(base_mensual - aportes_obligatorios, 0.0)
    detalle.append(f"Ingreso neto (pago − aportes obligatorios): ${ingreso_neto:,.0f}")

    limite_40 = min(ingreso_neto * cfg["limite_deducciones_pct"],
                    cfg["limite_deducciones_tope_uvt_anual"] / 12 * uvt)
    deducciones = min(deducciones, limite_40)
    subtotal = ingreso_neto - deducciones
    exenta_25 = min(subtotal * cfg["renta_exenta_pct"], cfg["renta_exenta_tope_uvt_anual"] / 12 * uvt)
    # La renta exenta del 25% también está sujeta al límite global del 40%.
    exenta_25 = min(exenta_25, max(limite_40 - deducciones, 0.0))
    base_depurada = max(subtotal - exenta_25, 0.0)
    detalle.append(f"Deducciones aceptadas: ${deducciones:,.0f}; renta exenta 25%: ${exenta_25:,.0f}")
    detalle.append(f"Base gravable depurada: ${base_depurada:,.0f} ({base_depurada / uvt:,.2f} UVT)")

    base_uvt = base_depurada / uvt
    for rango in cfg["rangos"]:
        hasta = rango["hasta_uvt"]
        if hasta is None or base_uvt <= hasta:
            ret_uvt = (base_uvt - rango["desde_uvt"]) * rango["tarifa"] + rango["mas_uvt"]
            ret_uvt = max(ret_uvt, 0.0)
            detalle.append(
                f"Rango > {rango['desde_uvt']} UVT: ({base_uvt:,.2f} − {rango['desde_uvt']}) × "
                f"{rango['tarifa']:.0%} + {rango['mas_uvt']} UVT = {ret_uvt:,.2f} UVT")
            return redondear(ret_uvt * uvt), detalle
    return 0.0, detalle  # pragma: no cover


def retencion_renta(empresa: Empresa, proveedor: Proveedor, concepto: dict, base: float, tabla: dict,
                    pagos_acumulados_anio: float = 0.0, usar_art_383: bool = False,
                    aportes_obligatorios: float = 0.0, deducciones_383: float = 0.0) -> LineaRetencion:
    imp = "Retención en la fuente (renta)"
    uvt = tabla["uvt"]

    # 1. ¿La empresa está obligada a retener?
    if empresa.regimen_simple:
        return LineaRetencion(imp, False, "La empresa pertenece al Régimen SIMPLE: no es agente de retención en renta (salvo pagos laborales).")
    if not empresa.agente_retencion_renta:
        return LineaRetencion(imp, False, "La empresa no está configurada como agente de retención en renta (RUT 07).")
    if concepto["id"] == "tarjetas":
        return LineaRetencion(imp, False, "En pagos con tarjeta la retención la practica la entidad emisora/adquirente, no la empresa.")

    # 2. ¿El proveedor es sujeto de retención?
    es_exterior = concepto.get("residencia") == "exterior"
    if proveedor.no_residente and not es_exterior:
        return LineaRetencion(imp, False, "El proveedor es no residente: use un concepto de 'Pagos al exterior'.")
    if es_exterior and not proveedor.no_residente:
        return LineaRetencion(imp, False, "El concepto es de pagos al exterior pero el proveedor está marcado como residente.")
    if proveedor.no_contribuyente:
        return LineaRetencion(imp, False, "El proveedor es no contribuyente de renta (RUT 06): no se le practica retención.")
    if proveedor.autorretenedor:
        return LineaRetencion(imp, False, "El proveedor es autorretenedor (RUT 15): se autorretiene, no se le practica retención en renta.")
    if proveedor.regimen_simple:
        return LineaRetencion(imp, False, "El proveedor pertenece al Régimen SIMPLE (RUT 47): no es sujeto de retención en renta.")
    if proveedor.regimen_especial and not concepto.get("rendimiento_financiero"):
        return LineaRetencion(imp, False, "El proveedor es del Régimen Tributario Especial (RUT 04): no se le retiene salvo por rendimientos financieros.")

    # 3. Retención con la tabla del art. 383 (independientes sin 2 trabajadores)
    if (usar_art_383 and concepto.get("aplica_383") and proveedor.es_persona_natural
            and proveedor.sin_dos_trabajadores and not proveedor.no_residente):
        valor, detalle = calcular_art_383(base, tabla, aportes_obligatorios, deducciones_383)
        tarifa_ef = valor / base if base else 0.0
        return LineaRetencion(imp, valor > 0,
                              "Tabla del art. 383 E.T. (persona natural que no ha contratado 2 o más trabajadores)."
                              if valor > 0 else "Base depurada inferior a 95 UVT según art. 383 E.T.: retención $0.",
                              base, tarifa_ef, valor, detalle)

    # 4. Tarifa según tipo de proveedor
    clave = proveedor.clave_tarifa()
    tarifa = concepto["tarifas"].get(clave)
    if tarifa is None:
        return LineaRetencion(imp, False, f"El concepto no aplica para {proveedor.descripcion_tipo().lower()}.")
    detalle = [f"Tarifa para {proveedor.descripcion_tipo().lower()}: {tarifa:.2%}"]

    tope_3300 = concepto.get("tarifa_pn_mayor_3300_uvt")
    if tope_3300 is not None and proveedor.es_persona_natural:
        if pagos_acumulados_anio + base > 3300 * uvt:
            tarifa = tope_3300
            detalle.append(f"Pagos/contrato del año superan 3.300 UVT (${3300 * uvt:,.0f}): tarifa {tarifa:.2%}")

    # 5. Base mínima
    base_min = concepto.get("base_min_uvt", 0) * uvt
    if base < base_min:
        return LineaRetencion(imp, False,
                              f"La base (${base:,.0f}) es inferior a la base mínima de {concepto['base_min_uvt']} UVT (${base_min:,.0f}).",
                              base, tarifa, 0.0, detalle)
    if base_min:
        detalle.append(f"Base mínima {concepto['base_min_uvt']} UVT = ${base_min:,.0f} → supera la base mínima")

    # 6. Cálculo (con tramos si existen)
    tramos = concepto.get("tramos_uvt")
    if tramos:
        desde, valor = 0.0, 0.0
        for t in tramos:
            limite = t["hasta_uvt"] * uvt if t["hasta_uvt"] is not None else base
            porcion = max(min(base, limite) - desde, 0.0)
            if porcion > 0:
                valor += porcion * t["tarifa"]
                detalle.append(f"Tramo hasta {t['hasta_uvt'] or '∞'} UVT: ${porcion:,.0f} × {t['tarifa']:.2%}")
            desde = limite
            if desde >= base:
                break
        valor = redondear(valor)
        tarifa_ef = valor / base if base else 0.0
        return LineaRetencion(imp, True, "Aplica retención por tramos.", base, tarifa_ef, valor, detalle)

    valor = redondear(base * tarifa)
    return LineaRetencion(imp, True, f"Aplica: {concepto['nombre']}.", base, tarifa, valor, detalle)


# ---------------------------------------------------------------------------
# Retención de IVA
# ---------------------------------------------------------------------------

def retencion_iva(empresa: Empresa, proveedor: Proveedor, concepto: dict, base: float, iva: float,
                  tabla: dict) -> LineaRetencion:
    imp = "ReteIVA"
    uvt = tabla["uvt"]
    cfg = tabla["reteiva"]

    if iva <= 0:
        return LineaRetencion(imp, False, "La operación no tiene IVA.")

    # Servicios prestados desde el exterior: retención del 100% (art. 437-2 num. 3)
    if proveedor.no_residente:
        if concepto.get("tipo") != "servicio":
            return LineaRetencion(imp, False, "Compras al exterior: el IVA se liquida en la importación (aduana).")
        if proveedor.iva_prestador_exterior:
            return LineaRetencion(imp, False, "El prestador del exterior está inscrito (RUT 46) y declara el IVA directamente.")
        if not empresa.responsable_iva:
            return LineaRetencion(imp, False, "La empresa no es responsable de IVA: no aplica la retención del 100% por servicios del exterior.")
        valor = redondear(iva * cfg["tarifa_no_residentes"])
        return LineaRetencion(imp, True, "Servicio prestado por no residente: retención del 100% del IVA (art. 437-2 num. 3 E.T.).",
                              iva, cfg["tarifa_no_residentes"], valor)

    if not empresa.es_agente_reteiva:
        return LineaRetencion(imp, False, "La empresa no es agente de retención de IVA (no es gran contribuyente, entidad estatal ni agente designado).")
    if not proveedor.responsable_iva:
        return LineaRetencion(imp, False, "El proveedor no es responsable de IVA (RUT 49).")
    if proveedor.gran_contribuyente and not empresa.entidad_estatal:
        return LineaRetencion(imp, False, "El proveedor es gran contribuyente: entre grandes contribuyentes / agentes designados no se practica reteIVA.")

    base_min = cfg["base_min_uvt"].get(concepto.get("tipo", "otro"), 0) * uvt
    if base < base_min:
        return LineaRetencion(imp, False, f"La base (${base:,.0f}) es inferior a la cuantía mínima de ${base_min:,.0f}.")

    tarifa = empresa.tarifa_reteiva or cfg["tarifa_general"]
    valor = redondear(iva * tarifa)
    return LineaRetencion(imp, True, f"Aplica {tarifa:.0%} sobre el IVA facturado.", iva, tarifa, valor,
                          [f"IVA ${iva:,.0f} × {tarifa:.0%}"])


# ---------------------------------------------------------------------------
# Retención de ICA (municipal, parametrizable por empresa)
# ---------------------------------------------------------------------------

def retencion_ica(empresa: Empresa, proveedor: Proveedor, concepto: dict, base: float, tabla: dict) -> LineaRetencion:
    imp = "ReteICA"
    uvt = tabla["uvt"]
    if not empresa.agente_reteica:
        return LineaRetencion(imp, False, "La empresa no está configurada como agente de reteICA.")
    if proveedor.no_residente:
        return LineaRetencion(imp, False, "Proveedor no residente: no realiza actividad gravada con ICA en el municipio.")
    if concepto.get("tipo") == "otro":
        return LineaRetencion(imp, False, "Concepto no sujeto a reteICA (financieros/otros).")
    if proveedor.regimen_simple:
        return LineaRetencion(imp, False, "El proveedor pertenece al SIMPLE: el ICA está integrado al impuesto unificado.")
    if not proveedor.sujeto_reteica or proveedor.tarifa_ica_por_mil <= 0:
        return LineaRetencion(imp, False, "El proveedor no es sujeto de reteICA o no tiene tarifa ICA configurada.")

    base_min = empresa.reteica_base_min_uvt.get(concepto.get("tipo", "otro"), 0) * uvt
    if base < base_min:
        return LineaRetencion(imp, False, f"La base (${base:,.0f}) es inferior a la base mínima municipal de ${base_min:,.0f}.")
    tarifa = proveedor.tarifa_ica_por_mil / 1000
    valor = redondear(base * tarifa)
    return LineaRetencion(imp, True, f"Aplica reteICA ({empresa.municipio or 'municipio configurado'}): {proveedor.tarifa_ica_por_mil} por mil.",
                          base, tarifa, valor)


# ---------------------------------------------------------------------------
# Orquestador
# ---------------------------------------------------------------------------

def calcular_retenciones(empresa: Empresa, proveedor: Proveedor, concepto_id: str, base: float, tabla: dict,
                         iva: float = 0.0, **opciones_renta) -> ResultadoRetencion:
    if base < 0:
        raise ValueError("La base no puede ser negativa.")
    concepto = buscar_concepto(tabla, concepto_id)
    lineas = [
        retencion_renta(empresa, proveedor, concepto, base, tabla, **opciones_renta),
        retencion_iva(empresa, proveedor, concepto, base, iva, tabla),
        retencion_ica(empresa, proveedor, concepto, base, tabla),
    ]
    advertencias = []
    if concepto.get("nota"):
        advertencias.append(concepto["nota"])
    if proveedor.es_persona_natural and proveedor.sin_dos_trabajadores and concepto.get("aplica_383") \
            and not opciones_renta.get("usar_art_383"):
        advertencias.append("El proveedor informó que no ha contratado 2 o más trabajadores: por ley se le aplica la tabla del art. 383 E.T.")
    if iva > 0 and not proveedor.responsable_iva and not proveedor.no_residente:
        advertencias.append("Se registró IVA pero el proveedor está marcado como NO responsable de IVA. Verifique la factura o el RUT.")
    return ResultadoRetencion(concepto, base, iva, lineas, advertencias)


def que_retenciones_aplican(empresa: Empresa, proveedor: Proveedor, tabla: dict) -> list[str]:
    """Resumen cualitativo de qué retenciones le aplican a un proveedor (sin monto)."""
    resumen = []
    ficticio = 10_000 * tabla["uvt"]  # base alta para no tropezar con mínimos
    for imp, concepto_id, iva in (("Renta (compras)", "compras_generales", 1.0),
                                  ("Renta (servicios)", "servicios_generales", 1.0),
                                  ("Renta (honorarios)", "honorarios", 1.0)):
        if proveedor.no_residente:
            concepto_id = "ext_servicios_generales"
        r = calcular_retenciones(empresa, proveedor, concepto_id, ficticio, tabla, iva=ficticio * 0.19)
        renta = r.linea("Retención")
        resumen.append(f"{imp}: " + (f"SÍ – tarifa {renta.tarifa:.2%}" if renta.aplica else f"NO – {renta.motivo}"))
        if proveedor.no_residente:
            break
    r = calcular_retenciones(empresa, proveedor, "servicios_generales" if not proveedor.no_residente else "ext_servicios_generales",
                             ficticio, tabla, iva=ficticio * 0.19)
    for prefijo in ("ReteIVA", "ReteICA"):
        l = r.linea(prefijo)
        resumen.append(f"{prefijo}: " + (f"SÍ – {l.tarifa:.2%}" if l.aplica else f"NO – {l.motivo}"))
    return resumen
