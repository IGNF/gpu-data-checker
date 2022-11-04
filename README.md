# Plugin d'assistance à la vérification des données produites pour le GPU

## Déploiement

* imagemagick
* pyrcc5

## Traitements

Deux traitements sont rendus disponibles par le plugin : 
* reprojection de la couche en coordonnées géographiques (WGS84, EPSG:4326) si celle-ci est en Lambert 93
* chaînage des vérifications des géométries de la couche correspondant à celles du validateur de GPU
Le préalable au lancement des vérifications est que la couche en entrée soit en coordonnées géographiques (CRS EPSG:4326)
Les traitements produisent une couche contenant les erreurs rencontrées.

## Couche de résultats

Nom de la couche : <nom_couche_en_entrée>_error
Modèle : 

| champ    | type                                        | description                                                                                                 |
|----------|---------------------------------------------|-------------------------------------------------------------------------------------------------------------|
| id       | integer                                     | identifiant de l'erreur (il peut y avoir plusieurs erreurs pour une géométrie)                              |
| fid      | integer                                     | identifiant de l'entité concernée (correspond à la valeur d'un champ "id" trouvée dans la couche en entrée) |
| level    | enum("WARNING", "ERROR")                    | niveau de l'erreur rencontrée ("ERROR" = non validé par le GPU)                                             |
| type     | enum("invalid", "complex", "duplicate") | type d'invalidité rencontrée                                                                                |
| message  | text                                        | message plus détaillée de l'invalidité rencontrée                                                           |
| geometry | geometry(4326)                              | Géométrie de l'erreur                                                                                       |

### Détail du contenu des champs `message` et ``geometry`

| type        | level   | message                                                      | geometry                       |
|-------------|---------|--------------------------------------------------------------|--------------------------------|
| invalid | ERROR   | Auto-intersection                                            | point au niveau de l'erreur    |
| invalid | ERROR   | Auto-intersection de l'anneau                                | point au niveau de l'erreur    |
| invalid | ERROR   | Trop peu de points dans la géométrie                         | point au niveau de l'erreur    |
| complex     | WARNING | Nombre de parties supérieur à 500                            | centroïde de l'entité complète |
| complex     | WARNING | Nombre de trous supérieur à 500                              | centroïde de l'entité complète |
| complex     | WARNING | Anneau avec plus de 50000 points et plus de 0.1 points/mètre | centroïde de l'anneau concerné |
| complex     | ERROR   | Nombre de sommets supérieur à 200000                         | centroïde de l'entité complète |
| complex     | ERROR   | Nombre de parties supérieur à 1000                           | centroïde de l'entité complète |
| complex     | ERROR   | Nombre de trous supérieur à 1000                             | centroïde de l'entité complète |
| complex     | ERROR   | Anneau avec plus de 50000 points et plus de 10 points/mètre  | centroïde de l'anneau concerné |
| duplicate   | ERROR   | Géométrie dupliquée                                          | centroïde de la géométrie      |

