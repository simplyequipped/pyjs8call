import setuptools

with open('README.md', 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name='pyjs8call',
    version='0.2.1',
    author='Simply Equipped LLC',
    author_email='howard@simplyequipped.com',
    description='Python package for interfacing with the JS8Call API',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/simplyequipped/pyjs8call',
    packages=setuptools.find_packages(),
    install_requires=['psutil>=5.3'],
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX :: Linux',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: Microsoft :: Windows'
    ],
    python_requires='>=3.6.1'
)
