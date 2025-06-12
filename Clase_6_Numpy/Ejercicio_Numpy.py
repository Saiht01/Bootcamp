import numpy as np
from PIL import Image
import matplotlib.pyplot as plt

# 1. Crea un arreglo 5x3 de números aleatorios entre 0 y 100

A = np.random.randint(0,101, size=(5,3))
print("Arreglo\n",A)

# 2. ¿Cuál es la suma total de los valores del arreglo?
print("")
print(f"Sumatoria de los valores del arreglo: {np.sum(A)}")

# 3. ¿Cúal es el promedio de cada columna del arreglo?
print("")
print(f"Promedio de los valores del arreglo por columna: {np.mean(A, axis=0)}")

# 4. Crea una matriz 10x10 de enteros aleatorios (0-9).
print("")
B = np.random.randint(0,9, size=(10,10))
print("Matriz\n",B)

# 5. Pon en -1 todos los valores > 5
print("")
B[ B > 5 ] = -1
print(B)
# 6. Abre una imagen, muestra shape, min, max y promedio de cada canal

  ## Uso de la libreria Pillow
print("")
img = Image.open('C:/Users/USER/Documents/Bootcamp/Bootcamp/Clase_6_Numpy/skyrim-2914856.JPG').convert('RGB')
img_array = np.array(img)
print(img_array)
print("")
print("Forma de la imagen (alto, ancho, canales):\n", img_array.shape)

# Separar canales
R = img_array[:, :, 0]
G = img_array[:, :, 1]
B = img_array[:, :, 2]

# Mostrar shape, min, max y promedio de cada canal
for canal, nombre in zip([R, G, B], ['Rojo', 'Verde', 'Azul']):
    print(f"\nCanal {nombre}:")
    print(f"  Mínimo: {np.min(canal)}")
    print(f"  Máximo: {np.max(canal)}")
    print(f"  Promedio: {np.mean(canal):.2f}")
plt.imshow(img_array)
plt.axis('off')
plt.title("Imagen")
plt.show()