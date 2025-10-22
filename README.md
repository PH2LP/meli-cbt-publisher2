cat > README.md <<'EOF'
# 🧠 meli-cbt-publisher2

Automatización avanzada para publicar productos de **Amazon** en **Mercado Libre Global Selling (CBT)** utilizando IA y la API oficial de Mercado Libre.

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Mercado Libre API](https://img.shields.io/badge/Mercado%20Libre%20API-v1-yellow.svg)](https://developers.mercadolibre.com.ar/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o-green.svg)](https://platform.openai.com/)
[![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)](LICENSE)

---

## 🚀 Descripción

Este proyecto automatiza la **creación y publicación de listings globales (CBT)** en Mercado Libre a partir de productos obtenidos de Amazon SP-API o archivos JSON locales.

El flujo completo utiliza **IA (GPT-4o / GPT-4o-mini)** para generar:
- 🧾 Títulos y descripciones en español natural  
- 🏷️ Atributos y características técnicas  
- 📦 Dimensiones del paquete y peso  
- 💰 Precio con `global_net_proceeds` calculado automáticamente  
- 🌎 Replicación automática a marketplaces (MLM, MLC, MLB, MCO, etc.)

---

## ⚙️ Estructura principal