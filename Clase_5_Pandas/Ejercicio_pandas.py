import pandas as pd
# 1.Leer un archivo del formato de su elección sobre cualquier temática
Games = pd.read_csv('C:/Users/USER/Documents/Bootcamp/Bootcamp/Clase_5_Pandas/vgsales.csv')
print(Games.head())
print("")

# 2.Muestre la forma, información general y estadisticas descriptivas del dataset
print('Shape / Forma:', Games.shape)  # Forma del dataset (filas, columnas)
print("")
print("Estádisticas descriptivas\n",Games.describe()) # Estádisticas descriptivas de las columnas númericas
print("")

# 3.Genere un nuevo dataset aplicando un filtro sobre los datos originales
print("")
print("Los 10 juegos mas vendidos de Nintendo del 2000 en adelante:\n")
Games_Nintendo = Games.sort_values(by='Global_Sales', ascending=False)
Games_Nintendo['Global_Sales'] = Games_Nintendo['Global_Sales'].astype(int)
Games_Nintendo = Games_Nintendo.rename(columns={
    'Global_Sales': 'Global_Sales (Miles de Millones)'
})
Games_filter = Games_Nintendo[(Games_Nintendo['Publisher'] == 'Nintendo') & (Games_Nintendo['Year'] >= 2000)].reset_index(drop=True)
print(Games_filter[['Rank', 'Name', 'Platform', 'Genre', 'Global_Sales (Miles de Millones)']].head(10))

# 4.Genere un nuevo dataset aplicando un ordenamiento sobre los datos originales

print("")
print("Los 30 juegos mas vendidos en el mundo de 1980 - 2020:")
print("Ordenado por ventas globales (descendente):\n")
Games_ordenado = Games.sort_values(by='Global_Sales', ascending=False)
Games_ordenado['Global_Sales'] = Games_ordenado['Global_Sales'].astype(int)
Games_ordenado = Games_ordenado.rename(columns={
    'Global_Sales': 'Global_Sales (Miles de Millones)'
})
print(Games_ordenado[['Rank', 'Name', 'Platform', 'Genre', 'Publisher', 'Global_Sales (Miles de Millones)']].head(30))