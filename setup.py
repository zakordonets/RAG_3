from setuptools import setup, find_packages

setup(
    name="rag-system",
    version="2.3.0",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        # Dependencies will be installed from requirements.txt
    ],
    entry_points={
        'console_scripts': [
            'rag-telegram-bot=adapters.telegram_polling:main',
            'rag-api=wsgi:app',
        ],
    },
)
