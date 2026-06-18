"""Country → continent mapping for literature comparison."""

CONTINENT_BY_COUNTRY: dict[str, str] = {
    # Africa
    "Kenya": "Africa",
    "Rwanda": "Africa",
    "Mauritania": "Africa",
    "Ethiopia": "Africa",
    "Tanzania": "Africa",
    "Uganda": "Africa",
    "Ghana": "Africa",
    "Nigeria": "Africa",
    "Cameroon": "Africa",
    "Madagascar": "Africa",
    "Mozambique": "Africa",
    "South Africa": "Africa",
    "Senegal": "Africa",
    "Burkina Faso": "Africa",
    "Mali": "Africa",
    "Niger": "Africa",
    # Americas
    "Brazil": "Americas",
    "Mexico": "Americas",
    "Ecuador": "Americas",
    "Colombia": "Americas",
    "Peru": "Americas",
    "Guyana": "Americas",
    "Trinidad y Tobago": "Americas",
    "Trinidad and Tobago": "Americas",
    "Costa Rica": "Americas",
    "Panama": "Americas",
    "Honduras": "Americas",
    "Guatemala": "Americas",
    "Nicaragua": "Americas",
    "Bolivia": "Americas",
    "Argentina": "Americas",
    "Chile": "Americas",
    "United States": "Americas",
    "USA": "Americas",
    # Asia
    "Philippines": "Asia",
    "Indonesia": "Asia",
    "Viet Nam": "Asia",
    "Vietnam": "Asia",
    "Thailand": "Asia",
    "India": "Asia",
    "China": "Asia",
    "Nepal": "Asia",
    "Myanmar": "Asia",
    "Cambodia": "Asia",
    "Laos": "Asia",
    "Malaysia": "Asia",
    "Sri Lanka": "Asia",
    # Europe
    "Portugal": "Europe",
    "Spain": "Europe",
    "Italy": "Europe",
    "France": "Europe",
    "Germany": "Europe",
    # Oceania
    "Australia": "Oceania",
    "Papua New Guinea": "Oceania",
    "Fiji": "Oceania",
}


def get_continent(country: str) -> str:
    if not country:
        return "Unknown"
    if country in CONTINENT_BY_COUNTRY:
        return CONTINENT_BY_COUNTRY[country]
    lower = country.lower()
    for name, continent in CONTINENT_BY_COUNTRY.items():
        if name.lower() == lower:
            return continent
    return "Unknown"
