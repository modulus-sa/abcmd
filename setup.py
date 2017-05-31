import setuptools

setuptools.setup(
    name="abcmd",
    version="0.1.0",
    url="https://github.com/laerus/abcmd",

    author="Konstantinos Tsakiltzidis",
    author_email="laerusk@gmail.com",

    description="ABCs for wrapping command with static configuration",
    long_description=open('README.rst').read(),

    packages=setuptools.find_packages(),

    install_requires=[],

    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
)
