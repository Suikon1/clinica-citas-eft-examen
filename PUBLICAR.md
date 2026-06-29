# Cómo publicar este repositorio (para el enlace del informe)

El repositorio ya está inicializado con Git (2 commits). Para obtener el **enlace**
que pide la rúbrica, publícalo en GitHub con una de estas dos vías.

## Opción A — con GitHub CLI (recomendada)
```bash
cd 03_Repositorio
gh auth login                       # si no estás autenticado
gh repo create clinica-citas-eft --public --source=. --remote=origin --push
```

## Opción B — manual
1. Crea un repositorio vacío en https://github.com/new (ej. `clinica-citas-eft`).
2. Luego:
```bash
cd 03_Repositorio
git remote add origin https://github.com/<tu-usuario>/clinica-citas-eft.git
git branch -M main
git push -u origin main
```

Pega la URL resultante en la portada del informe (sección de datos) y en la
sección 9. El `.gitignore` ya excluye claves y secretos.
