# Calculadora de retenciones en la fuente (Colombia)

App en Python + Streamlit que determina **qué retenciones se le deben practicar a un proveedor**
según sus responsabilidades tributarias (RUT) y las de **tu empresa**, y calcula su valor
sobre una base con la **tabla de retención vigente**.

## Qué hace

- **Empresa parametrizable**: cada empresa se guarda en `datos/empresas/<clave>.json` con sus
  responsabilidades RUT (07 agente de retención en renta, 13 gran contribuyente, 09/23 agente
  de reteIVA, 47 SIMPLE, 48 responsable de IVA…), si es entidad estatal, si es agente de reteICA,
  municipio, bases mínimas de reteICA y tarifa de reteIVA. Puedes tener varias empresas y elegir
  la activa en la barra lateral.
- **Proveedores**: se registran con tipo de persona, responsabilidades RUT (04, 05, 06, 13, 15,
  46, 47, 48, 49), si es no residente, si (persona natural) no ha contratado 2+ trabajadores
  (art. 383 E.T.) y su tarifa de ICA por mil. La app muestra un resumen de qué retenciones le aplican.
- **Cálculo** de las tres retenciones con el motivo de cada decisión:
  - **Retención en la fuente a título de renta**: concepto, base mínima en UVT, tarifa según
    persona jurídica / natural declarante / no declarante, honorarios > 3.300 UVT, tramos de
    vivienda, pagos al exterior y tabla del art. 383 E.T.
  - **ReteIVA**: 15% del IVA cuando la empresa es gran contribuyente, entidad estatal o agente
    designado y el proveedor es responsable de IVA (sin retención entre grandes contribuyentes);
    100% en servicios prestados por no residentes.
  - **ReteICA**: según tarifa por mil del proveedor y bases mínimas del municipio configurado.
  - Total factura, total retenciones y **neto a pagar**.
- **Tabla vigente**: `datos/tablas/tabla_2026.json` — UVT 2026 $52.374 (Res. DIAN 000238/2025),
  bases y tarifas del Decreto 0572 de 2025 vigentes desde el 1 de julio de 2026. La app elige la
  tabla según la fecha del pago, así que para un año nuevo basta con agregar otro JSON en
  `datos/tablas/` con su `vigencia_desde`.
- **Responsabilidades RUT**: `datos/responsabilidades_rut.json` explica el efecto de cada código.

## Uso

```bash
cd retencion_fuente
pip install -r requirements.txt
streamlit run app.py      # interfaz web
python -m pytest          # pruebas del motor de cálculo
```

Uso programático:

```python
from retenciones import Empresa, Proveedor, calcular_retenciones
from retenciones.tablas import tabla_vigente

tabla = tabla_vigente()
empresa = Empresa(nombre="Mi SAS", gran_contribuyente=True)
prov = Proveedor(nombre="Servicios XYZ", tipo_persona="juridica", responsable_iva=True)
r = calcular_retenciones(empresa, prov, "servicios_generales", 1_000_000, tabla, iva=190_000)
for l in r.lineas:
    print(l.impuesto, l.aplica, l.valor, l.motivo)
print("Neto a pagar:", r.neto_a_pagar)
```

## Estructura

```
retencion_fuente/
├── app.py                       # interfaz Streamlit
├── retenciones/
│   ├── modelos.py               # Empresa, Proveedor y mapeo de códigos RUT
│   ├── motor.py                 # reglas y cálculo (renta, IVA, ICA, art. 383)
│   └── tablas.py                # carga de tablas/empresas JSON
├── datos/
│   ├── tablas/tabla_2026.json   # tabla de retención vigente (editable)
│   ├── responsabilidades_rut.json
│   └── empresas/mi_empresa.json # empresa de ejemplo con proveedores
└── tests/test_motor.py
```

## Advertencias

Herramienta de apoyo, no reemplaza el criterio del contador o revisor fiscal. Las bases y tarifas
pueden cambiar por decretos o fallos (por ejemplo, el Decreto 0572 de 2025 estuvo suspendido
entre el 8 de mayo y el 30 de junio de 2026). Las tarifas de reteICA dependen de cada municipio y
de la actividad CIIU del proveedor, por eso se configuran por proveedor.
