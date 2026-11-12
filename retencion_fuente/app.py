"""App Streamlit: calculadora de retenciones en la fuente para proveedores (Colombia).

Ejecutar:  streamlit run app.py
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from retenciones.modelos import (CODIGOS_EMPRESA, CODIGOS_PROVEEDOR, Empresa, Proveedor,
                                 atributos_desde_rut)
from retenciones.motor import calcular_retenciones, que_retenciones_aplican
from retenciones.tablas import (cargar_empresa, guardar_empresa, listar_empresas,
                                responsabilidades_rut, tabla_vigente)

st.set_page_config(page_title="Retenciones en la fuente", page_icon="🧾", layout="wide")

RESP = responsabilidades_rut()
NOMBRE_RESP = {r["codigo"]: f'{r["codigo"]} - {r["nombre"]}' for r in RESP}
TARIFAS_IVA = {"19%": 0.19, "5%": 0.05, "Exento / excluido (0%)": 0.0, "Valor manual": None}


def pesos(v: float) -> str:
    return f"${v:,.0f}".replace(",", ".")


def pct(v: float) -> str:
    return f"{v * 100:.2f}%".replace(".", ",")


# ---------------------------------------------------------------------------
# Barra lateral: empresa activa y tabla vigente
# ---------------------------------------------------------------------------
st.sidebar.title("🧾 Retenciones")
empresas = listar_empresas()
if not empresas:
    guardar_empresa(Empresa(nombre="Mi Empresa"), "mi_empresa")
    empresas = listar_empresas()
clave_empresa = st.sidebar.selectbox("Empresa (agente retenedor)", empresas,
                                     format_func=lambda c: cargar_empresa(c).nombre)
empresa = cargar_empresa(clave_empresa)

fecha_pago = st.sidebar.date_input("Fecha del pago / causación", value=date.today())
tabla = tabla_vigente(fecha_pago)
UVT = tabla["uvt"]
st.sidebar.metric("UVT", pesos(UVT))
st.sidebar.caption(f"**{tabla['nombre']}**  \nVigente desde {tabla['vigencia_desde']}  \n{tabla['norma_uvt']}")
with st.sidebar.expander("Nota de vigencia"):
    st.write(tabla.get("nota_vigencia", ""))

st.sidebar.divider()
st.sidebar.markdown(f"**{empresa.nombre}**  \nNIT {empresa.nit}")
st.sidebar.markdown(
    f"- Agente retención renta: {'✅' if empresa.agente_retencion_renta and not empresa.regimen_simple else '❌'}\n"
    f"- Agente reteIVA: {'✅' if empresa.es_agente_reteiva else '❌'}\n"
    f"- Agente reteICA: {'✅' if empresa.agente_reteica else '❌'} {empresa.municipio}")

tab_calc, tab_prov, tab_emp, tab_tabla, tab_rut = st.tabs(
    ["🧮 Calcular", "👥 Proveedores", "🏢 Mi empresa", "📋 Tabla vigente", "📖 Responsabilidades RUT"])


# ---------------------------------------------------------------------------
# Formulario reutilizable de proveedor
# ---------------------------------------------------------------------------
def formulario_proveedor(prefijo: str, base: Proveedor | None = None) -> Proveedor:
    base = base or Proveedor(nombre="", responsabilidades=["05", "48"])
    c1, c2, c3 = st.columns(3)
    nombre = c1.text_input("Nombre / razón social", base.nombre, key=f"{prefijo}_nombre")
    nit = c2.text_input("NIT / cédula", base.nit, key=f"{prefijo}_nit")
    tipo = c3.radio("Tipo de persona", ["juridica", "natural"], horizontal=True,
                    index=0 if base.tipo_persona == "juridica" else 1,
                    format_func=lambda t: "Jurídica" if t == "juridica" else "Natural", key=f"{prefijo}_tipo")

    codigos_validos = [c for c in NOMBRE_RESP if c in CODIGOS_PROVEEDOR or c == "49"]
    codigos = st.multiselect("Responsabilidades del RUT (casilla 53)", codigos_validos,
                             default=[c for c in base.responsabilidades if c in codigos_validos],
                             format_func=NOMBRE_RESP.get, key=f"{prefijo}_rut")
    attrs = atributos_desde_rut(codigos, CODIGOS_PROVEEDOR)

    c1, c2, c3, c4 = st.columns(4)
    no_residente = c1.checkbox("No residente (exterior)", base.no_residente, key=f"{prefijo}_ext")
    sin_dos = c2.checkbox("PN: no ha contratado 2+ trabajadores (art. 383)", base.sin_dos_trabajadores,
                          key=f"{prefijo}_383", disabled=tipo != "natural")
    sujeto_ica = c3.checkbox("Sujeto de reteICA", base.sujeto_reteica, key=f"{prefijo}_ica")
    tarifa_ica = c4.number_input("Tarifa ICA (por mil)", 0.0, 100.0, float(base.tarifa_ica_por_mil), 0.01,
                                 key=f"{prefijo}_tica", help="Según la actividad CIIU del proveedor en el municipio.")

    if "48" in codigos and "49" in codigos:
        st.warning("El proveedor no puede ser responsable (48) y no responsable (49) de IVA a la vez.")
    return Proveedor(
        nombre=nombre, nit=nit, tipo_persona=tipo,
        declarante=attrs["declarante"] or tipo == "juridica",
        responsable_iva=attrs["responsable_iva"], autorretenedor=attrs["autorretenedor"],
        gran_contribuyente=attrs["gran_contribuyente"], regimen_simple=attrs["regimen_simple"],
        regimen_especial=attrs["regimen_especial"], no_contribuyente=attrs["no_contribuyente"],
        iva_prestador_exterior=attrs["iva_prestador_exterior"], no_residente=no_residente,
        sin_dos_trabajadores=sin_dos and tipo == "natural", sujeto_reteica=sujeto_ica,
        tarifa_ica_por_mil=tarifa_ica, responsabilidades=codigos)


# ---------------------------------------------------------------------------
# Pestaña: calcular
# ---------------------------------------------------------------------------
with tab_calc:
    st.header("Calcular retenciones a un proveedor")
    proveedores = empresa.lista_proveedores()
    opciones = ["➕ Proveedor ocasional (sin guardar)"] + [f"{p.nombre} ({p.nit})" for p in proveedores]
    sel = st.selectbox("Proveedor", range(len(opciones)), format_func=lambda i: opciones[i])
    if sel == 0:
        with st.container(border=True):
            proveedor = formulario_proveedor("ocasional")
    else:
        proveedor = proveedores[sel - 1]
        resp = ", ".join(NOMBRE_RESP.get(c, c) for c in proveedor.responsabilidades) or "sin responsabilidades registradas"
        st.info(f"**{proveedor.descripcion_tipo()}** · RUT: {resp}"
                + (" · No residente" if proveedor.no_residente else "")
                + (f" · ICA {proveedor.tarifa_ica_por_mil}‰" if proveedor.sujeto_reteica else ""))

    conceptos = [c for c in tabla["conceptos"]
                 if (c.get("residencia") == "exterior") == proveedor.no_residente]
    grupos = list(dict.fromkeys(c["grupo"] for c in conceptos))
    c1, c2 = st.columns([1, 2])
    grupo = c1.selectbox("Grupo", grupos)
    en_grupo = [c for c in conceptos if c["grupo"] == grupo]
    concepto = c2.selectbox("Concepto de retención", en_grupo,
                            format_func=lambda c: f'{c["nombre"]} (base mín. {c["base_min_uvt"]} UVT)')

    c1, c2, c3 = st.columns(3)
    base = c1.number_input("Base del pago (antes de IVA)", min_value=0.0, value=1_000_000.0, step=10_000.0, format="%.0f")
    tarifa_iva_txt = c2.selectbox("IVA de la factura", list(TARIFAS_IVA),
                                  index=0 if proveedor.responsable_iva or proveedor.no_residente else 2)
    if TARIFAS_IVA[tarifa_iva_txt] is None:
        iva = c3.number_input("Valor del IVA", min_value=0.0, value=0.0, step=1_000.0, format="%.0f")
    else:
        iva = round(base * TARIFAS_IVA[tarifa_iva_txt])
        c3.metric("IVA", pesos(iva))

    opciones_renta = {}
    with st.expander("Opciones avanzadas (honorarios > 3.300 UVT, art. 383)"):
        opciones_renta["pagos_acumulados_anio"] = st.number_input(
            "Pagos acumulados al proveedor en el año / valor del contrato (antes de este pago)",
            min_value=0.0, value=0.0, step=100_000.0, format="%.0f",
            help=f"Si supera 3.300 UVT ({pesos(3300 * UVT)}) la tarifa de honorarios a personas naturales sube al 11%.")
        if proveedor.es_persona_natural and proveedor.sin_dos_trabajadores and concepto.get("aplica_383"):
            opciones_renta["usar_art_383"] = st.checkbox("Aplicar tabla del art. 383 E.T.", value=True)
            opciones_renta["aportes_obligatorios"] = st.number_input(
                "Aportes obligatorios a salud y pensión del periodo", min_value=0.0, value=0.0, format="%.0f")
            opciones_renta["deducciones_383"] = st.number_input(
                "Otras deducciones / rentas exentas soportadas", min_value=0.0, value=0.0, format="%.0f")
        else:
            st.caption("La tabla del art. 383 solo aplica a personas naturales que informen no haber contratado "
                       "2 o más trabajadores, en honorarios, servicios o consultoría.")

    resultado = calcular_retenciones(empresa, proveedor, concepto["id"], base, tabla, iva=iva, **opciones_renta)

    st.subheader("Resultado")
    m = st.columns(5)
    m[0].metric("Subtotal", pesos(resultado.base))
    m[1].metric("IVA", pesos(resultado.iva))
    m[2].metric("Total factura", pesos(resultado.total_factura))
    m[3].metric("Total retenciones", pesos(resultado.total_retenciones))
    m[4].metric("Neto a pagar", pesos(resultado.neto_a_pagar))

    df = pd.DataFrame([{
        "Impuesto": l.impuesto,
        "¿Aplica?": "✅ Sí" if l.aplica else "❌ No",
        "Base": pesos(l.base) if l.aplica else "—",
        "Tarifa": pct(l.tarifa) if l.aplica else "—",
        "Valor retenido": pesos(l.valor),
        "Motivo": l.motivo,
    } for l in resultado.lineas])
    st.dataframe(df, hide_index=True, width="stretch")

    for l in resultado.lineas:
        if l.detalle:
            with st.expander(f"Detalle del cálculo – {l.impuesto}"):
                for d in l.detalle:
                    st.write("• " + d)
    for a in resultado.advertencias:
        st.warning(a)
    st.caption(f"Norma del concepto: {concepto.get('norma', '')}")


# ---------------------------------------------------------------------------
# Pestaña: proveedores
# ---------------------------------------------------------------------------
with tab_prov:
    st.header(f"Proveedores de {empresa.nombre}")
    proveedores = empresa.lista_proveedores()
    if proveedores:
        filas = []
        for p in proveedores:
            resumen = que_retenciones_aplican(empresa, p, tabla)
            filas.append({"Proveedor": p.nombre, "NIT": p.nit, "Tipo": p.descripcion_tipo(),
                          "RUT": ", ".join(p.responsabilidades), **{r.split(":")[0]: r.split(":", 1)[1].strip() for r in resumen}})
        st.markdown("**¿Qué retenciones le aplican a cada proveedor?** (según la configuración de tu empresa)")
        st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")

    st.subheader("Agregar o editar proveedor")
    opciones = ["➕ Nuevo proveedor"] + [p.nombre for p in proveedores]
    idx = st.selectbox("Seleccione", range(len(opciones)), format_func=lambda i: opciones[i], key="edit_prov")
    actual = proveedores[idx - 1] if idx > 0 else None
    with st.form(f"form_prov_{idx}"):
        nuevo = formulario_proveedor(f"prov{idx}", actual)
        c1, c2 = st.columns(2)
        guardar = c1.form_submit_button("💾 Guardar proveedor", type="primary")
        eliminar = c2.form_submit_button("🗑️ Eliminar", disabled=actual is None)
    if guardar:
        if not nuevo.nombre.strip():
            st.error("El nombre es obligatorio.")
        else:
            lista = [p.a_dict() for p in proveedores]
            if actual is None:
                lista.append(nuevo.a_dict())
            else:
                lista[idx - 1] = nuevo.a_dict()
            empresa.proveedores = lista
            guardar_empresa(empresa, clave_empresa)
            st.success("Proveedor guardado.")
            st.rerun()
    if eliminar and actual is not None:
        empresa.proveedores = [p.a_dict() for i, p in enumerate(proveedores) if i != idx - 1]
        guardar_empresa(empresa, clave_empresa)
        st.rerun()


# ---------------------------------------------------------------------------
# Pestaña: empresa (parametrización)
# ---------------------------------------------------------------------------
with tab_emp:
    st.header("Parametrización de la empresa")
    st.caption("Estas responsabilidades determinan qué retenciones debe practicar la empresa. "
               "Cada empresa se guarda en `datos/empresas/<nombre>.json`.")
    with st.form("form_empresa"):
        c1, c2, c3 = st.columns(3)
        nombre = c1.text_input("Razón social", empresa.nombre)
        nit = c2.text_input("NIT", empresa.nit)
        tipo = c3.radio("Tipo de persona", ["juridica", "natural"], horizontal=True,
                        index=0 if empresa.tipo_persona == "juridica" else 1,
                        format_func=lambda t: "Jurídica" if t == "juridica" else "Natural")
        codigos_validos = [c for c in NOMBRE_RESP if c in CODIGOS_EMPRESA or c in ("05", "42", "49", "52", "14")]
        codigos = st.multiselect("Responsabilidades del RUT de la empresa (casilla 53)", codigos_validos,
                                 default=[c for c in empresa.responsabilidades if c in codigos_validos],
                                 format_func=NOMBRE_RESP.get)
        c1, c2 = st.columns(2)
        entidad_estatal = c1.checkbox("Es entidad estatal", empresa.entidad_estatal)
        agente_reteica = c2.checkbox("Es agente de reteICA en su municipio", empresa.agente_reteica)
        c1, c2, c3, c4 = st.columns(4)
        municipio = c1.text_input("Municipio (reteICA)", empresa.municipio)
        ica_bien = c2.number_input("Base mín. reteICA compras (UVT)", 0.0, value=float(empresa.reteica_base_min_uvt.get("bien", 27)))
        ica_serv = c3.number_input("Base mín. reteICA servicios (UVT)", 0.0, value=float(empresa.reteica_base_min_uvt.get("servicio", 4)))
        tarifa_reteiva = c4.number_input("Tarifa reteIVA", 0.0, 1.0, float(empresa.tarifa_reteiva), 0.01,
                                         help="General 15% del IVA (art. 437-1 E.T.).")
        c1, c2 = st.columns(2)
        guardar_actual = c1.form_submit_button("💾 Guardar cambios", type="primary")
        guardar_nueva = c2.form_submit_button("➕ Guardar como nueva empresa")

    if guardar_actual or guardar_nueva:
        attrs = atributos_desde_rut(codigos, CODIGOS_EMPRESA)
        nueva = Empresa(
            nombre=nombre, nit=nit, tipo_persona=tipo, entidad_estatal=entidad_estatal,
            agente_reteica=agente_reteica, municipio=municipio,
            reteica_base_min_uvt={"bien": ica_bien, "servicio": ica_serv, "otro": 0},
            tarifa_reteiva=tarifa_reteiva, responsabilidades=codigos,
            proveedores=[] if guardar_nueva else empresa.proveedores, **attrs)
        clave = guardar_empresa(nueva, None if guardar_nueva else clave_empresa)
        st.success(f"Empresa guardada ({clave}.json). Selecciónela en la barra lateral.")
        st.rerun()

    st.subheader("Qué retenciones practica esta empresa")
    st.markdown(
        f"- **Retención en renta:** {'Sí' if empresa.agente_retencion_renta and not empresa.regimen_simple else 'No'}"
        + (" (Régimen SIMPLE: solo pagos laborales)" if empresa.regimen_simple else "") + "\n"
        f"- **ReteIVA:** {'Sí, ' + pct(empresa.tarifa_reteiva) + ' del IVA a responsables de IVA' if empresa.es_agente_reteiva else 'No (solo 100% por servicios de no residentes, si es responsable de IVA)'}\n"
        f"- **ReteICA:** {'Sí, en ' + empresa.municipio if empresa.agente_reteica else 'No'}")


# ---------------------------------------------------------------------------
# Pestaña: tabla vigente
# ---------------------------------------------------------------------------
with tab_tabla:
    st.header(tabla["nombre"])
    st.caption(f"UVT {pesos(UVT)} · {tabla['norma_uvt']} · Vigente desde {tabla['vigencia_desde']}")
    filas = []
    for c in tabla["conceptos"]:
        t = c["tarifas"]
        filas.append({
            "Grupo": c["grupo"], "Concepto": c["nombre"], "Base mín. UVT": c["base_min_uvt"],
            "Base mín. $": pesos(c["base_min_uvt"] * UVT),
            "P. jurídica": pct(t["pj"]) if t["pj"] is not None else "N/A",
            "PN declarante": pct(t["pn_declarante"]) if t["pn_declarante"] is not None else "N/A",
            "PN no declarante": pct(t["pn_no_declarante"]) if t["pn_no_declarante"] is not None else "N/A",
            "Norma": c.get("norma", ""), "Nota": c.get("nota", "")})
    st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch", height=600)
    st.subheader("ReteIVA")
    riva = tabla["reteiva"]
    st.write(f"Tarifa general {pct(riva['tarifa_general'])} del IVA; servicios de no residentes {pct(riva['tarifa_no_residentes'])}. "
             f"Cuantías mínimas: compras {riva['base_min_uvt']['bien']} UVT ({pesos(riva['base_min_uvt']['bien'] * UVT)}), "
             f"servicios {riva['base_min_uvt']['servicio']} UVT ({pesos(riva['base_min_uvt']['servicio'] * UVT)}).")
    st.subheader("Tabla art. 383 E.T.")
    st.dataframe(pd.DataFrame([{
        "Desde (UVT)": r["desde_uvt"], "Hasta (UVT)": str(r["hasta_uvt"] or "En adelante"),
        "Tarifa marginal": pct(r["tarifa"]), "Más (UVT)": r["mas_uvt"]} for r in tabla["art_383"]["rangos"]]),
        hide_index=True)


# ---------------------------------------------------------------------------
# Pestaña: responsabilidades RUT
# ---------------------------------------------------------------------------
with tab_rut:
    st.header("Responsabilidades tributarias (RUT, casilla 53)")
    st.caption("Cómo influye cada responsabilidad en las retenciones que se practican o se sufren.")
    st.dataframe(pd.DataFrame([{"Código": r["codigo"], "Responsabilidad": r["nombre"], "Efecto en retenciones": r["efecto"]}
                               for r in RESP]), hide_index=True, width="stretch")
    st.markdown("""
**Reglas que aplica la app**

| Situación | Renta | ReteIVA | ReteICA |
|---|---|---|---|
| Empresa sin responsabilidad 07 o en SIMPLE (47) | No retiene | — | — |
| Empresa gran contribuyente (13), entidad estatal o agente designado (09/23) | — | Retiene 15% del IVA a responsables (48) | — |
| Proveedor autorretenedor (15) | No se le retiene | Sí | Sí |
| Proveedor SIMPLE (47) | No se le retiene | Sí, si es responsable de IVA | No |
| Proveedor no contribuyente (06) | No se le retiene | Según IVA | Según municipio |
| Proveedor régimen especial (04) | Solo rendimientos financieros | Según IVA | Según municipio |
| Proveedor gran contribuyente (13) | Sí | No, si la empresa es GC o agente designado | Sí |
| Proveedor no responsable de IVA (49) | Sí | No | Sí |
| Proveedor no residente | Tarifas de pagos al exterior | 100% del IVA en servicios (salvo RUT 46) | No |
| Persona natural no declarante | Tarifas mayores (compras 3,5%, servicios 6%) | — | — |
""")
    st.info("Herramienta de apoyo. Verifique siempre con su contador/revisor fiscal y la normativa vigente; "
            "las tablas son editables en `datos/tablas/` y `datos/responsabilidades_rut.json`.")
