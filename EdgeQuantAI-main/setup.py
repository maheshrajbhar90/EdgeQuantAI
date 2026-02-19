
from setuptools import setup, find_packages

setup(
    name='stock_analyzer',
    version='0.0.0.1',
    author='Mahesh Kumar',
    author_email='maheshrajbhar90@gmail.com',

    description='A Python library for comprehensive stock technical analysis.',
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type='text/markdown',
    url='https://github.com/maheshrajbhar90/stock_analyzer.git',  # Replace with your actual GitHub URL
    packages=find_packages(),
    install_requires=[
        'pandas',
        'yfinance',
        'TA-Lib',
        'requests',
        'tabulate',
        'openai'
    ],
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.8',
)



