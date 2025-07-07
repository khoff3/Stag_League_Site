from setuptools import setup, find_packages

setup(
    name="stag_league_site",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "beautifulsoup4",
        "selenium",
        "webdriver-manager",
        "python-dotenv",
        "requests"
    ],
    python_requires=">=3.8",
) 